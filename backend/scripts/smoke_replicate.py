"""Send one real inpainting request to Replicate and save the result (costs a fraction of a cent).

Run from backend (needs REPLICATE_API_TOKEN, in the environment or backend/.env):
    python -m scripts.smoke_replicate                        # synthetic finger + nail
    python -m scripts.smoke_replicate image.png mask.png    # your own 512x512 pair, white = repaint
Writes smoke_out.png (and smoke_in.png / smoke_mask.png for the synthetic case).
"""
import asyncio
import io
import sys
import time

from dotenv import load_dotenv
from PIL import Image, ImageDraw

import nv_utils as nv
from generation import replicate_client as rep


def png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def synthetic():
    img = Image.new("RGB", (512, 512), (226, 190, 160))  # skin
    ImageDraw.Draw(img).ellipse((186, 120, 326, 400), fill=(240, 205, 190))  # bare nail
    mask = Image.new("L", (512, 512), 0)
    ImageDraw.Draw(mask).ellipse((186, 120, 326, 400), fill=255)
    img.save("smoke_in.png")
    mask.save("smoke_mask.png")
    return img, mask


async def main():
    for f in (".env.local", ".env"):
        load_dotenv(f)
    if len(sys.argv) == 3:
        img, mask = Image.open(sys.argv[1]).convert("RGB"), Image.open(sys.argv[2]).convert("L")
    else:
        img, mask = synthetic()
    prompt = nv.build_prompt("french tip", ["#C8102E", "#F5F5F2", "#D4AF37"])
    t = time.perf_counter()
    out = await rep.inpaint(png(img), png(mask), prompt, nv.NEGATIVE_PROMPT, seed=1234, steps=25)
    Image.open(io.BytesIO(out)).save("smoke_out.png")
    print(f"OK in {time.perf_counter() - t:.1f}s, {len(out)} bytes -> smoke_out.png")


if __name__ == "__main__":
    asyncio.run(main())
