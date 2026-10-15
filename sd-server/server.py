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


def run_job(job, photo, nail_masks, client_hex, seed, steps, strength, guidance):
    """One design per nail mask (max 5), appended to job["designs"] as each finishes."""
    try:
        client = [nv.parse_color(c) for c in client_hex]
        rng = random.Random(seed)
        styles = rng.sample(list(nv.STYLES), len(nail_masks))
        pipe = None if MOCK else get_pipe()
        job["status"] = "running"
        for i, nail_mask in enumerate(nail_masks):
            t = time.time()
            box = nv.square_crop_box(nail_mask, photo.size)
            crop, cmask = nv.crop_to(photo, nail_mask, box, 512)
            inpaint_mask = nv.dilate(cmask, 4)
            mask_img = Image.fromarray(inpaint_mask.astype(np.uint8) * 255)
            paste_mask = nv.dilate(nail_mask, max(2, round(4 * (box[2] - box[0]) / 512)))

            pal = client[i % 3:] + client[:i % 3]
            style = styles[i]
            prompt = nv.build_prompt(style, pal, use_trigger=False)
            slot_seed = rng.randint(0, 2**31 - 1)
            seed_img = nv.make_palette_seed(crop, inpaint_mask, pal, random.Random(slot_seed),
                                            layout=nv.STYLE_LAYOUT.get(style))
            if pipe is None:
                out = seed_img
            else:
                g = torch.Generator("cpu").manual_seed(slot_seed)
                out = pipe(prompt=prompt, negative_prompt=nv.NEGATIVE_PROMPT, image=seed_img, mask_image=mask_img,
                           height=512, width=512, strength=strength, guidance_scale=guidance,
                           num_inference_steps=steps, generator=g).images[0]
            adh = nv.color_adherence(out, cmask, pal)
            photo = nv.paste_back(photo, out, box, paste_mask)  # later nails build on earlier ones
            job["designs"].append(dict(
                slot=i + 1, kind="palette", label=f"Nail {i+1}", style=style,
                palette_hex=[nv.rgb_to_hex(c) for c in pal], prompt=prompt, seed=slot_seed,
                delta_e=adh["mean_delta_e"], on_palette=adh["coverage"], seconds=time.time() - t,
                full_jpeg_b64=jpeg_b64(photo), zoom_jpeg_b64=jpeg_b64(out)))
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
