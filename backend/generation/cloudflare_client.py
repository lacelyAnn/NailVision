"""Cloudflare Workers AI client for SD 1.5 inpainting (REST API).

Env: CF_ACCOUNT_ID, CF_API_TOKEN. The token stays on the server; it is never logged or sent to the app.
"""
import asyncio
import logging
import os

import httpx

MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
RETRIES = 3  # extra attempts after the first, on 429 and 5xx
log = logging.getLogger(__name__)


class CloudflareError(RuntimeError):
    pass


async def inpaint(image_png: bytes, mask_png: bytes, prompt: str, negative_prompt: str, seed: int,
                  client: httpx.AsyncClient | None = None) -> bytes:
    """Inpaint the white area of `mask_png` in `image_png` (both 512x512 PNG). Returns PNG bytes."""
    account, token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not account or not token:
        raise CloudflareError("CF_ACCOUNT_ID and CF_API_TOKEN must be set.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}"
    body = dict(prompt=prompt, negative_prompt=negative_prompt, image=list(image_png), mask=list(mask_png),
                width=512, height=512, num_steps=20, guidance=7.5, strength=1.0, seed=seed)
    own = client is None
    client = client or httpx.AsyncClient(timeout=120)
    try:
        for attempt in range(RETRIES + 1):
            r = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
            if (r.status_code == 429 or r.status_code >= 500) and attempt < RETRIES:
                log.warning("Cloudflare %s, retry %d/%d", r.status_code, attempt + 1, RETRIES)
                await asyncio.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                log.error("Cloudflare %s: %s", r.status_code, r.text[:2000])
                raise CloudflareError(f"Cloudflare returned {r.status_code}: {r.text[:300]}")
            if not r.content.startswith(b"\x89PNG"):  # errors can come back as JSON with status 200
                log.error("Cloudflare sent no PNG: %s", r.text[:2000])
                raise CloudflareError("Cloudflare response was not a PNG image.")
            return r.content
    finally:
        if own:
            await client.aclose()
