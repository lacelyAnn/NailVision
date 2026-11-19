"""Run from backend:  python -m unittest discover tests"""
import base64
import json
import os
import unittest
from unittest import mock

import httpx

from generation import replicate_client as rep

PNG = b"\x89PNG\r\n\x1a\nfake"
OUT_URL = "https://replicate.delivery/pbxt/abc/out-0.png"
PRED = f"{rep.API}/predictions"


def pred(status, output=None, error=None, pid="p1"):
    return httpx.Response(201, json=dict(id=pid, status=status, output=output, error=error))


def client_for(*responses):
    calls = []

    def handler(request):
        calls.append(request)
        return responses[len(calls) - 1]

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


@mock.patch.dict(os.environ, {"REPLICATE_API_TOKEN": "secret-token"})
@mock.patch("generation.replicate_client.random.uniform", return_value=0)
@mock.patch("generation.replicate_client.asyncio.sleep", new_callable=mock.AsyncMock)
class InpaintTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_sends_schema_and_downloads_without_token(self, sleep, _rand):
        client, calls = client_for(pred("succeeded", [OUT_URL]), httpx.Response(200, content=PNG))
        out = await rep.inpaint(PNG, b"\x89PNGmask", "red nails", "blurry", 42, steps=30, guidance=7.5, client=client)
        self.assertEqual(out, PNG)
        create, download = calls
        self.assertEqual(str(create.url), PRED)
        self.assertEqual(create.headers["authorization"], "Bearer secret-token")
        self.assertEqual(create.headers["prefer"], "wait=60")
        body = json.loads(create.content)
        self.assertEqual(body["version"], rep.VERSION)
        inp = body["input"]
        self.assertEqual(inp["image"], "data:image/png;base64," + base64.b64encode(PNG).decode())
        self.assertTrue(inp["mask"].startswith("data:image/png;base64,"))
        self.assertEqual((inp["width"], inp["height"], inp["num_inference_steps"], inp["guidance_scale"], inp["seed"],
                          inp["prompt"], inp["negative_prompt"]), (512, 512, 30, 7.5, 42, "red nails", "blurry"))
        self.assertEqual(str(download.url), OUT_URL)
        self.assertNotIn("authorization", download.headers)
        sleep.assert_not_awaited()

    async def test_jpeg_image_gets_jpeg_data_uri(self, sleep, _rand):
        client, calls = client_for(pred("succeeded", [OUT_URL]), httpx.Response(200, content=PNG))
        await rep.inpaint(b"\xff\xd8\xffjpeg", PNG, "p", "n", 1, client=client)
        self.assertTrue(json.loads(calls[0].content)["input"]["image"].startswith("data:image/jpeg;base64,"))

    async def test_steps_are_capped(self, sleep, _rand):
        client, calls = client_for(pred("succeeded", [OUT_URL]), httpx.Response(200, content=PNG))
        await rep.inpaint(PNG, PNG, "p", "n", 1, steps=500, client=client)
        self.assertEqual(json.loads(calls[0].content)["input"]["num_inference_steps"], rep.MAX_STEPS)

    async def test_polls_until_done(self, sleep, _rand):
        client, calls = client_for(pred("starting"), pred("processing"), pred("succeeded", [OUT_URL]),
                                   httpx.Response(200, content=PNG))
        self.assertEqual(await rep.inpaint(PNG, PNG, "p", "n", 1, client=client), PNG)
        self.assertEqual([str(c.url) for c in calls[1:3]], [f"{PRED}/p1"] * 2)
        self.assertEqual(calls[1].headers["authorization"], "Bearer secret-token")
        self.assertEqual(sleep.await_count, 2)

    async def test_failed_prediction_raises_with_reason(self, sleep, _rand):
        client, _ = client_for(pred("failed", error="CUDA out of memory"))
        with self.assertLogs("generation.replicate_client", "ERROR"), \
                self.assertRaisesRegex(rep.ReplicateError, "CUDA out of memory"):
            await rep.inpaint(PNG, PNG, "p", "n", 1, client=client)

    async def test_429_then_success_retries(self, sleep, _rand):
        client, calls = client_for(httpx.Response(429, text="slow down"), pred("succeeded", [OUT_URL]),
                                   httpx.Response(200, content=PNG))
        self.assertEqual(await rep.inpaint(PNG, PNG, "p", "n", 1, client=client), PNG)
        self.assertEqual(len(calls), 3)
        sleep.assert_awaited_once_with(1)

    async def test_429_honours_retry_after(self, sleep, _rand):
        client, _ = client_for(httpx.Response(429, headers={"retry-after": "5"}), pred("succeeded", [OUT_URL]),
                               httpx.Response(200, content=PNG))
        await rep.inpaint(PNG, PNG, "p", "n", 1, client=client)
        sleep.assert_awaited_once_with(5)

    async def test_throttle_message_sets_the_wait(self, sleep, _rand):
        msg = {"detail": "Request was throttled. Your rate limit for creating predictions is reduced to 6 requests "
                         "per minute with a burst of 1 requests. Your rate limit resets in ~10s."}
        client, _ = client_for(httpx.Response(429, json=msg), pred("succeeded", [OUT_URL]),
                               httpx.Response(200, content=PNG))
        await rep.inpaint(PNG, PNG, "p", "n", 1, client=client)
        sleep.assert_awaited_once_with(10)

    async def test_sends_width_and_height(self, sleep, _rand):
        client, calls = client_for(pred("succeeded", [OUT_URL]), httpx.Response(200, content=PNG))
        await rep.inpaint(PNG, PNG, "p", "n", 1, width=768, height=384, client=client)
        inp = json.loads(calls[0].content)["input"]
        self.assertEqual((inp["width"], inp["height"]), (768, 384))

    async def test_5xx_gives_up_after_6_retries_capped_at_30s(self, sleep, _rand):
        client, calls = client_for(*[httpx.Response(503, text="down")] * 7)
        with self.assertRaises(rep.ReplicateError), self.assertLogs("generation.replicate_client"):
            await rep.inpaint(PNG, PNG, "p", "n", 1, client=client)
        self.assertEqual(len(calls), 7)
        self.assertEqual([c.args[0] for c in sleep.await_args_list], [1, 2, 4, 8, 16, 30])

    async def test_402_explains_billing_and_logs_no_token(self, sleep, _rand):
        client, calls = client_for(httpx.Response(402, json={"detail": "You have insufficient credit"}))
        with self.assertLogs("generation.replicate_client", "ERROR") as logs, \
                self.assertRaisesRegex(rep.ReplicateError, "402.*billing.*insufficient credit"):
            await rep.inpaint(PNG, PNG, "p", "n", 1, client=client)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("secret-token", "".join(logs.output))

    async def test_missing_token_raises(self, sleep, _rand):
        with mock.patch.dict(os.environ, {"REPLICATE_API_TOKEN": ""}), \
                self.assertRaisesRegex(rep.ReplicateError, "REPLICATE_API_TOKEN"):
            await rep.inpaint(PNG, PNG, "p", "n", 1)


if __name__ == "__main__":
    unittest.main()
