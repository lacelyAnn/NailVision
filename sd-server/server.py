"""NailVision offline SD service (CPU). Port of generate_five from the Colab notebook.

Run:  .venv\\Scripts\\python -m uvicorn server:app --port 8000
Env:  MODEL_DIR (default ../gpu/sd15-inpainting), MOCK=1 (skip SD, returns the colour seed)
"""
import base64
import io
import os
import random
import threading
import time
import uuid

import numpy as np
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

import nv_utils as nv

MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "gpu", "sd15-inpainting"))
MOCK = os.environ.get("MOCK") == "1"

app = FastAPI()
ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]  # e.g. https://nailvision.vercel.app
API_TOKEN = os.environ.get("API_TOKEN")  # optional; visible to anyone holding the frontend bundle
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])

_pipe = None
_pipe_lock = threading.Lock()
jobs: dict = {}


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
                MODEL_DIR, variant="fp16", torch_dtype=torch.float32, safety_checker=None,
                requires_safety_checker=False,
            )
            p.scheduler = DPMSolverMultistepScheduler.from_config(p.scheduler.config, use_karras_sigmas=True)
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


def run_job(job, photo, nail_masks, client_hex, seed, steps, strength, guidance):
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

        pipe = None if MOCK else get_pipe()
        job["status"] = "running"
        for s in slots:
            t = time.time()
            prompt = nv.build_prompt(s["style"], s["palette"], use_trigger=False)
            slot_seed = rng.randint(0, 2**31 - 1)
            full, deltas, ref = photo, [], None
            for p in prep:  # same prompt, palette and seed on every nail = one design
                seed_img = nv.make_palette_seed(p["crop"], p["inpaint_mask"], s["palette"],
                                                random.Random(slot_seed),
                                                layout=nv.STYLE_LAYOUT.get(s["style"]))
                if pipe is None:
                    out = seed_img
                else:
                    g = torch.Generator("cpu").manual_seed(slot_seed)
                    out = pipe(prompt=prompt, negative_prompt=nv.NEGATIVE_PROMPT, image=seed_img,
                               mask_image=p["mask_img"], height=512, width=512, strength=strength,
                               guidance_scale=guidance, num_inference_steps=steps, generator=g).images[0]
                if ref is None:
                    ref = (out, p["cmask"])  # first nail sets the colours for the rest
                else:
                    out = match_color(out, p["cmask"], *ref)
                deltas.append(nv.color_adherence(out, p["cmask"], s["target"]))
                full = nv.paste_back(full, out, p["box"], p["paste_mask"])
            zoom = full.crop((max(0, ux0), max(0, uy0), min(full.width, ux1), min(full.height, uy1)))
            job["designs"].append(dict(
                slot=s["slot"], kind=s["kind"], label=s["label"], style=s["style"],
                palette_hex=[nv.rgb_to_hex(c) for c in s["palette"]], prompt=prompt, seed=slot_seed,
                delta_e=sum(d["mean_delta_e"] for d in deltas) / len(deltas),
                on_palette=sum(d["coverage"] for d in deltas) / len(deltas), seconds=time.time() - t,
                full_jpeg_b64=jpeg_b64(full), zoom_jpeg_b64=jpeg_b64(zoom)))
        job["status"] = "done"
    except Exception as e:  # surfaced to the client via GET /jobs/{id}
        job["status"], job["error"] = "failed", f"{type(e).__name__}: {e}"


@app.middleware("http")
async def token_guard(request, call_next):
    open_path = request.method == "OPTIONS" or request.url.path == "/health"
    if API_TOKEN and not open_path and request.headers.get("x-api-token") != API_TOKEN:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "mock" if MOCK else "cpu", "model_dir": os.path.abspath(MODEL_DIR)}


@app.post("/jobs")
async def create_job(photo: UploadFile = File(...), masks: list[UploadFile] = File(...), colors: str = Form(...),
                     seed: int | None = Form(None), steps: int = Form(30), strength: float = Form(0.9),
                     guidance: float = Form(7.5)):
    hexes = [c.strip() for c in colors.split(",")]
    if len(hexes) != 3:
        raise HTTPException(400, "Exactly 3 colours are required.")
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(await photo.read()))).convert("RGB")
    if max(img.size) > 2048:
        img.thumbnail((2048, 2048), Image.LANCZOS)
    if not 1 <= len(masks) <= 5:
        raise HTTPException(400, "Send 1 to 5 nail masks.")
    nails = []
    for mk in masks:
        m = Image.open(io.BytesIO(await mk.read())).convert("L").resize(img.size, Image.NEAREST)
        nail = np.asarray(m) > 127
        if nail.sum() == 0:
            raise HTTPException(400, "Empty nail mask.")
        nails.append(nail)
    seed = random.randint(0, 2**31 - 1) if seed is None else seed
    jid = uuid.uuid4().hex[:12]
    job = jobs[jid] = dict(status="queued", designs=[], seed=seed, error=None)
    for old in list(jobs)[:-20]:
        jobs.pop(old, None)
    threading.Thread(target=run_job, args=(job, img, nails, hexes, seed, steps, strength, guidance), daemon=True).start()
    return {"job_id": jid, "status": "queued"}


@app.get("/jobs/{jid}")
def get_job(jid: str):
    if jid not in jobs:
        raise HTTPException(404, "Unknown job.")
    return jobs[jid]
