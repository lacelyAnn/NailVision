"""NailVision offline SD service (GPU if available, else CPU). Port of generate_five from the Colab notebook.

Run:  .venv\\Scripts\\python -m uvicorn server:app --port 8000
Env:  GEN_BACKEND (cloudflare|local, default cloudflare), GEN_FALLBACK_LOCAL=true (local SD when Cloudflare fails),
      CF_ACCOUNT_ID, CF_API_TOKEN, DEVICE (cuda|mps|cpu, default: best available),
      MODEL_DIR (default models/sd15-inpainting), MOCK=1 (skip SD, returns the colour seed)
"""
import asyncio
import base64
import io
import logging
import os
import random
import threading
import time
import uuid

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps
from dotenv import load_dotenv

import nv_utils as nv
from generation import cloudflare_client as cf

# local runs; on Render the file is absent, and real env vars always win over it
load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))
MODEL_DIR = os.environ.get("MODEL_DIR") or os.path.join(os.path.dirname(__file__), "models", "sd15-inpainting")
MOCK = os.environ.get("MOCK") == "1"
GEN_BACKEND = os.environ.get("GEN_BACKEND", "cloudflare")
if GEN_BACKEND not in ("cloudflare", "local"):
    raise SystemExit(f"GEN_BACKEND must be cloudflare or local, not {GEN_BACKEND!r}")
FALLBACK_LOCAL = os.environ.get("GEN_FALLBACK_LOCAL", "").lower() == "true"
try:
    import torch
except ImportError:  # the deploy image ships without the local SD stack (requirements-local.txt)
    torch = None
    if not MOCK and (GEN_BACKEND == "local" or FALLBACK_LOCAL):
        raise SystemExit("GEN_BACKEND=local and GEN_FALLBACK_LOCAL=true need torch: pip install -r requirements-local.txt")
DEVICE = os.environ.get("DEVICE") or ("cpu" if torch is None else
    "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
DEVICE_NAME = torch.cuda.get_device_name(0) if DEVICE == "cuda" else DEVICE.upper()
CONCURRENCY = 3  # Cloudflare requests in flight per job
log = logging.getLogger("nailvision")

app = FastAPI()
ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]  # e.g. https://nailvision.vercel.app
API_TOKEN = os.environ.get("API_TOKEN")  # optional; visible to anyone holding the frontend bundle

_pipe = None
_pipe_lock = threading.Lock()
_run_lock = threading.Lock()
_job_slot = threading.Semaphore(1)  # one job at a time: two big jobs measured 436 MB of Render's 512 MB
jobs: dict = {}
MAX_PIXELS = 50_000_000  # bigger uploads would not fit in Render's 512 MB


def get_pipe():
    global _pipe
    with _pipe_lock:
        if _pipe is None:
            from diffusers import DPMSolverMultistepScheduler, StableDiffusionInpaintPipeline

            if not os.path.exists(os.path.join(MODEL_DIR, "model_index.json")):
                from huggingface_hub import snapshot_download

                snapshot_download("stable-diffusion-v1-5/stable-diffusion-inpainting", local_dir=MODEL_DIR,
                                  allow_patterns=["*.json", "*.txt", "*.fp16.safetensors"])

            p = StableDiffusionInpaintPipeline.from_pretrained(
                MODEL_DIR, variant="fp16", torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32, safety_checker=None,
                requires_safety_checker=False,
            )
            p.scheduler = DPMSolverMultistepScheduler.from_config(p.scheduler.config, use_karras_sigmas=True)
            p.to(DEVICE)
            p.set_progress_bar_config(disable=True)
            _pipe = p
        return _pipe


def jpeg_b64(img, q=92):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=q)
    return base64.b64encode(b.getvalue()).decode()


def match_color(out, cmask, ref, rmask):
    """Shift out's nail colours (LAB mean/std) onto ref's so every nail of a design shares one palette."""
    o = nv.rgb2lab(np.asarray(out.convert("RGB"), np.float32) / 255)
    f = nv.rgb2lab(np.asarray(ref.convert("RGB"), np.float32) / 255)
    om, os_ = o[cmask].mean(0), o[cmask].std(0) + 1e-3
    fm, fs = f[rmask].mean(0), f[rmask].std(0) + 1e-3
    o[cmask] = (o[cmask] - om) / os_ * fs + fm
    return Image.fromarray((nv.lab2rgb(o) * 255).clip(0, 255).astype(np.uint8))


def open_image(data, what):
    try:
        img = Image.open(io.BytesIO(data))  # reads only the header, nothing decoded yet
    except Exception:
        raise HTTPException(400, f"{what} is not an image.")
    if img.width * img.height > MAX_PIXELS:
        raise HTTPException(413, f"{what} is too large (max 50 megapixels).")
    img.draft("RGB", (2048, 2048))  # JPEG decodes straight at 1/2, 1/4 or 1/8 size
    return img


def png_bytes(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def local_inpaint(prompt, seed_img, mask_img, seed, steps, strength, guidance, on_step):
    pipe = get_pipe()
    with _run_lock:  # one diffusers call at a time; the pipeline is not thread-safe
        g = torch.Generator("cpu").manual_seed(seed)
        return pipe(prompt=prompt, negative_prompt=nv.NEGATIVE_PROMPT, image=seed_img,
                    mask_image=mask_img, height=512, width=512, strength=strength,
                    guidance_scale=guidance, num_inference_steps=steps, generator=g,
                    callback_on_step_end=on_step).images[0]


async def run_job(job, photo, nail_masks, client_hex, seed, steps, strength, guidance):
    """5 designs. Each design is painted on every selected nail (up to 5) and counts as one."""
    try:
        client = [nv.parse_color(c) for c in client_hex]
        rng = random.Random(seed)
        styles = rng.sample(list(nv.STYLES), 5)
        slots = []
        for i in range(3):
            pal = client[i:] + client[:i]
            slots.append(dict(slot=i + 1, kind="palette", palette=pal, target=client, style=styles[i],
                              label=f"Palette {i+1} · {nv.color_name(pal[0])} base"))
        for j in range(2):
            pal, scheme = nv.random_palette(rng)
            slots.append(dict(slot=4 + j, kind="random", palette=pal, target=pal, style=styles[3 + j],
                              label=f"Random {j+1} · {scheme}"))
        for s in slots:  # drawn in slot order, same seeds as the old sequential loop
            s["prompt"] = nv.build_prompt(s["style"], s["palette"], use_trigger=False)
            s["seed"] = rng.randint(0, 2**31 - 1)

        # per nail: crop, masks, paste mask (independent of the design)
        prep = []
        for nail_mask in nail_masks:
            box = nv.square_crop_box(nail_mask, photo.size)
            crop, cmask = nv.crop_to(photo, nail_mask, box, 512)
            inpaint_mask = nv.dilate(cmask, 4)
            prep.append(dict(
                box=box, crop=crop, cmask=cmask, inpaint_mask=inpaint_mask,
                mask_img=Image.fromarray(inpaint_mask.astype(np.uint8) * 255),
                paste_mask=nv.dilate(nail_mask, max(2, round(4 * (box[2] - box[0]) / 512)))))
        # region shown in the result card: all selected nails together
        ux0, uy0 = min(p["box"][0] for p in prep), min(p["box"][1] for p in prep)
        ux1, uy1 = max(p["box"][2] for p in prep), max(p["box"][3] for p in prep)

        job["status"] = "running"
        total, done = len(slots) * len(prep), [0.0]
        sem = asyncio.Semaphore(CONCURRENCY)
        finishing = asyncio.Lock()  # one full-size paste at a time: keeps peak RAM inside Render's 512 MB

        def bump(n):  # the app shows finished designs + `progress` % of one more, so spread all requests over that
            done[0] += n
            job["progress"] = max(0, min(100, round(100 * (len(slots) * done[0] / total - len(job["designs"])))))

        async def cloudflare_design(s, seeds):
            async def one(p, seed_img):
                async with sem:
                    t = time.perf_counter()
                    out = await cf.inpaint(png_bytes(seed_img), png_bytes(p["mask_img"]), s["prompt"],
                                           nv.NEGATIVE_PROMPT, s["seed"])
                    ms = (time.perf_counter() - t) * 1000
                counted[0] += 1
                bump(1)
                return Image.open(io.BytesIO(out)).convert("RGB"), ms

            counted = [0]
            try:
                async with asyncio.TaskGroup() as tg:  # first failure cancels the other nails
                    tasks = [tg.create_task(one(p, si)) for p, si in zip(prep, seeds)]
            except BaseException:
                bump(-counted[0])  # the fallback repaints these nails
                raise
            return [t.result() for t in tasks]

        def local_design(s, seeds):
            outs = []
            for p, seed_img in zip(prep, seeds):
                def on_step(pp, i, _t, kw):
                    bump(1 / pp.num_timesteps)
                    return kw
                t = time.perf_counter()
                out = local_inpaint(s["prompt"], seed_img, p["mask_img"], s["seed"], steps, strength, guidance, on_step)
                outs.append((out, (time.perf_counter() - t) * 1000))
            return outs

        def finish(s, outs, backend, t):
            full, deltas, ref = photo, [], None
            for p, (out, _ms) in zip(prep, outs):
                if ref is None:
                    ref = (out, p["cmask"])  # first nail sets the colours for the rest
                else:
                    out = match_color(out, p["cmask"], *ref)
                deltas.append(nv.color_adherence(out, p["cmask"], s["target"]))
                full = nv.paste_back(full, out, p["box"], p["paste_mask"])
            zoom = full.crop((max(0, ux0), max(0, uy0), min(full.width, ux1), min(full.height, uy1)))
            job["designs"].append(dict(
                slot=s["slot"], kind=s["kind"], label=s["label"], style=s["style"],
                palette_hex=[nv.rgb_to_hex(c) for c in s["palette"]], prompt=s["prompt"], seed=s["seed"],
                backend=backend, latency_ms=round(sum(ms for _, ms in outs)),
                delta_e=sum(d["mean_delta_e"] for d in deltas) / len(deltas),
                on_palette=sum(d["coverage"] for d in deltas) / len(deltas), seconds=time.time() - t,
                full_jpeg_b64=jpeg_b64(full), zoom_jpeg_b64=jpeg_b64(zoom)))
            bump(0)

        async def design(s):
            t = time.time()
            # same prompt, palette and seed on every nail = one design
            seeds = [nv.make_palette_seed(p["crop"], p["inpaint_mask"], s["palette"], random.Random(s["seed"]),
                                          layout=nv.STYLE_LAYOUT.get(s["style"])) for p in prep]
            if MOCK:
                outs, backend = [(img, 0.0) for img in seeds], "mock"
                bump(len(prep))
            elif GEN_BACKEND == "cloudflare":
                try:
                    outs, backend = await cloudflare_design(s, seeds), "cloudflare"
                except Exception as e:
                    e = e.exceptions[0] if isinstance(e, ExceptionGroup) else e
                    if not FALLBACK_LOCAL:
                        raise e
                    log.warning("Design %d: Cloudflare failed (%s: %s), using the local pipeline",
                                s["slot"], type(e).__name__, e)
                    outs, backend = await asyncio.to_thread(local_design, s, seeds), "local"
            else:
                outs, backend = await asyncio.to_thread(local_design, s, seeds), "local"
            async with finishing:
                await asyncio.to_thread(finish, s, outs, backend, t)

        async with asyncio.TaskGroup() as tg:
            for s in slots:
                tg.create_task(design(s))
        job["status"] = "done"
    except Exception as e:  # surfaced to the client via GET /jobs/{id}
        e = e.exceptions[0] if isinstance(e, ExceptionGroup) else e
        job["status"], job["error"] = "failed", f"{type(e).__name__}: {e}"


def run_queued(*args):
    with _job_slot:
        asyncio.run(run_job(*args))


@app.middleware("http")
async def token_guard(request, call_next):
    open_path = request.method == "OPTIONS" or request.url.path == "/health"
    if API_TOKEN and not open_path and request.headers.get("x-api-token") != API_TOKEN:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


# added after token_guard so CORS wraps it: a 401 must reach the browser as 401, not "Failed to fetch"
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    if MOCK:
        mode, device = "mock", DEVICE_NAME
    elif GEN_BACKEND == "cloudflare":
        mode, device = "cloudflare", "Cloudflare Workers AI"
    else:
        mode, device = DEVICE, DEVICE_NAME
    return {"status": "ok", "mode": mode, "device": device, "model_dir": os.path.abspath(MODEL_DIR)}


@app.post("/jobs")
async def create_job(photo: UploadFile = File(...), masks: list[UploadFile] = File(...), colors: str = Form(...),
                     seed: int | None = Form(None), steps: int = Form(30), strength: float = Form(0.9),
                     guidance: float = Form(7.5)):
    hexes = [c.strip() for c in colors.split(",")]
    if len(hexes) != 3:
        raise HTTPException(400, "Exactly 3 colours are required.")
    img = ImageOps.exif_transpose(open_image(await photo.read(), "Photo")).convert("RGB")
    if max(img.size) > 2048:
        img.thumbnail((2048, 2048), Image.LANCZOS)
    if not 1 <= len(masks) <= 5:
        raise HTTPException(400, "Send 1 to 5 nail masks.")
    nails = []
    for mk in masks:
        m = open_image(await mk.read(), "Nail mask").convert("L").resize(img.size, Image.NEAREST)
        nail = np.asarray(m) > 127
        if nail.sum() == 0:
            raise HTTPException(400, "Empty nail mask.")
        nails.append(nail)
    seed = random.randint(0, 2**31 - 1) if seed is None else seed
    jid = uuid.uuid4().hex[:12]
    job = jobs[jid] = dict(status="queued", designs=[], seed=seed, error=None, progress=0)
    for old in list(jobs)[:-20]:
        jobs.pop(old, None)
    threading.Thread(target=run_queued, args=(job, img, nails, hexes, seed, steps, strength, guidance),
                     daemon=True).start()
    return {"job_id": jid, "status": "queued"}


@app.get("/jobs/{jid}")
def get_job(jid: str):
    if jid not in jobs:
        raise HTTPException(404, "Unknown job.")
    return jobs[jid]
