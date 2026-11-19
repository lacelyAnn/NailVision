"""Run from backend:  python -m unittest discover tests"""
import asyncio
import io
import unittest
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

import server


def hand(nails=3, size=(1600, 1000)):
    photo = Image.new("RGB", size, (226, 190, 160))
    masks = []
    for i in range(nails):
        box = (250 + i * 400, 300, 400 + i * 400, 560)
        ImageDraw.Draw(photo).ellipse(box, fill=(240, 205, 190))
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).ellipse(box, fill=255)
        masks.append(np.asarray(m) > 127)
    return photo, masks


class GroupBoxTest(unittest.TestCase):
    def test_covers_every_nail_and_sends_a_valid_size(self):
        photo, masks = hand()
        (x0, y0, x1, y1), (w, h) = server.group_box(masks, photo.size)
        for m in masks:
            bx0, by0, bx1, by1 = server.nv.mask_to_box(m)
            self.assertTrue(x0 <= bx0 and y0 <= by0 and bx1 <= x1 and by1 <= y1)
        self.assertEqual(max(w, h), server.GROUP_SIDE)
        self.assertTrue(w % 64 == 0 and h % 64 == 0 and w <= 1024 and h <= 1024)
        self.assertAlmostEqual(w / h, (x1 - x0) / (y1 - y0), delta=0.15)  # little stretching

    def test_stays_inside_the_photo(self):
        photo, masks = hand(nails=1, size=(300, 600))
        masks.append(np.zeros_like(masks[0]))
        masks[1][0:40, 0:40] = True  # a nail in the corner
        box, _ = server.group_box(masks, photo.size)
        self.assertEqual(box[:2], (0, 0))
        self.assertTrue(box[2] <= 300 and box[3] <= 600)


class OneRequestPerDesignTest(unittest.TestCase):
    def test_three_nails_five_designs_five_requests(self):
        photo, masks = hand()
        sizes = []

        async def fake_inpaint(image, mask_png, prompt, negative, seed, steps, guidance, width, height):
            img, mask = Image.open(io.BytesIO(image)), Image.open(io.BytesIO(mask_png))
            self.assertEqual(img.size, (width, height))
            self.assertEqual(mask.size, (width, height))
            sizes.append((width, height))
            b = io.BytesIO()
            Image.new("RGB", (width, height), (200, 0, 40)).save(b, "PNG")
            return b.getvalue()

        job = dict(status="queued", designs=[], seed=1, error=None, progress=0)
        with mock.patch.object(server, "MOCK", False), mock.patch.object(server, "GEN_BACKEND", "replicate"), \
                mock.patch.object(server, "GROUP_NAILS", True), \
                mock.patch.object(server.rep, "inpaint", side_effect=fake_inpaint) as inpaint:
            asyncio.run(server.run_job(job, photo, masks, ["#C8102E", "#F5F5F2", "#D4AF37"], 1, 30, 0.9, 7.5))
        self.assertEqual(job["status"], "done", job["error"])
        self.assertEqual(len(job["designs"]), 5)
        self.assertEqual(inpaint.await_count, 5)  # not 15
        self.assertEqual(len(set(sizes)), 1)
        self.assertEqual({d["backend"] for d in job["designs"]}, {"replicate"})


if __name__ == "__main__":
    unittest.main()
