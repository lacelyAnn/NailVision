"""Replicate client for SD inpainting (HTTP API), model stability-ai/stable-diffusion-inpainting.

Env: REPLICATE_API_TOKEN (required), REPLICATE_MODEL_VERSION (optional, overrides VERSION).
The token stays on the server; it is never logged, sent to the app, or sent to the image download host.
"""
import asyncio
import base64
import logging
import os
import random
import re

import httpx

API = "https://api.replicate.com/v1"
VERSION = "95b7223104132402a9ae91cc677285bc5eb997834bd2349fa486f53910fd68b3"
RETRIES = 6  # extra attempts after the first, on 429 and 5xx
MAX_WAIT = 30  # seconds between retries, at most
POLL_EVERY = 1.0  # seconds between status checks once Prefer: wait has run out
TIMEOUT = 300  # seconds per prediction, a cold start included
MAX_STEPS = 60  # Replicate bills per second of GPU time, so the steps are capped
DONE = ("succeeded", "failed", "canceled")
log = logging.getLogger(__name__)


class ReplicateError(RuntimeError):
    pass


def _wait(attempt: int, r: httpx.Response) -> float:
    """Retry-After, or the "resets in ~10s" of a throttled request, else 1, 2, 4, 8, 16, 30 s. The jitter
    keeps the concurrent requests of one job from all retrying in the same instant."""
    after = r.headers.get("retry-after", "")
    resets = re.search(r"resets in ~?(\d+)s", r.text) if r.status_code == 429 else None
    base = float(after) if after.isdigit() else float(resets[1]) if resets else 2 ** attempt
    return min(base, MAX_WAIT) + random.uniform(0, 1)


def _data_uri(data: bytes) -> str:
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _detail(r: httpx.Response) -> str:
    try:
        j = r.json()
        return str(j.get("detail") or j.get("title") or j)[:300]
    except ValueError:
        return r.text[:300]


async def _send(client: httpx.AsyncClient, method: str, url: str, **kw) -> httpx.Response:
    for attempt in range(RETRIES + 1):
        r = await client.request(method, url, **kw)
        if (r.status_code == 429 or r.status_code >= 500) and attempt < RETRIES:
            wait = _wait(attempt, r)
            log.warning("Replicate %s, retry %d/%d in %.1fs", r.status_code, attempt + 1, RETRIES, wait)
            await asyncio.sleep(wait)
            continue
        if r.status_code >= 400:
            log.error("Replicate %s: %s", r.status_code, r.text[:2000])
            hint = {401: " (check REPLICATE_API_TOKEN)", 402: " (add billing or credit on replicate.com)"}
            raise ReplicateError(f"Replicate returned {r.status_code}{hint.get(r.status_code, '')}: {_detail(r)}")
        return r
    raise AssertionError("unreachable")


async def inpaint(image: bytes, mask_png: bytes, prompt: str, negative_prompt: str, seed: int,
                  steps: int = 25, guidance: float = 7.5, width: int = 512, height: int = 512,
                  client: httpx.AsyncClient | None = None) -> bytes:
    """Inpaint the white area of `mask_png` in `image` (same size, width x height: multiples of 64 up to 1024;
    image PNG or JPEG). Returns the image bytes."""
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise ReplicateError("REPLICATE_API_TOKEN must be set.")
    auth = {"Authorization": f"Bearer {token}"}
    body = {
        "version": os.environ.get("REPLICATE_MODEL_VERSION") or VERSION,
        "input": dict(prompt=prompt, negative_prompt=negative_prompt, image=_data_uri(image), mask=_data_uri(mask_png),
                      width=width, height=height, num_outputs=1, num_inference_steps=max(1, min(MAX_STEPS, int(steps))),
                      guidance_scale=guidance, seed=seed,
                      disable_safety_checker=True),  # close-ups of hands get flagged as NSFW now and then
    }
    own = client is None
    client = client or httpx.AsyncClient(timeout=120)  # longer than Prefer: wait=60
    try:
        r = await _send(client, "POST", f"{API}/predictions", json=body, headers={**auth, "Prefer": "wait=60"})
        p = r.json()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + TIMEOUT
        while p.get("status") not in DONE:  # still starting (cold start) or processing
            if loop.time() > deadline:
                raise ReplicateError(f"Replicate prediction {p.get('id')} took longer than {TIMEOUT}s.")
            await asyncio.sleep(POLL_EVERY)
            p = (await _send(client, "GET", f"{API}/predictions/{p['id']}", headers=auth)).json()
        if p["status"] != "succeeded":
            log.error("Replicate prediction %s %s: %s", p.get("id"), p["status"], p.get("error"))
            raise ReplicateError(f"Replicate prediction {p['status']}: {p.get('error') or 'no reason given'}")
        out = p.get("output")
        url = out[0] if isinstance(out, list) and out else out
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ReplicateError(f"Replicate returned no image (output: {str(out)[:200]}).")
        img = await _send(client, "GET", url)  # no auth header: the file host is public
        if not img.content:
            raise ReplicateError("Replicate image download was empty.")
        return img.content
    finally:
        if own:
            await client.aclose()
