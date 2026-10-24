"""Run from backend:  python -m unittest discover tests"""
import json
import os
import unittest
from unittest import mock

import httpx

from generation import cloudflare_client as cf

PNG = b"\x89PNG\r\n\x1a\nfake"


def client_for(*responses):
    calls = []

    def handler(request):
        calls.append(request)
        return responses[len(calls) - 1]

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


@mock.patch.dict(os.environ, {"CF_ACCOUNT_ID": "acc123", "CF_API_TOKEN": "secret-token"})
@mock.patch("generation.cloudflare_client.asyncio.sleep", new_callable=mock.AsyncMock)
class InpaintTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_returns_png_and_sends_schema(self, sleep):
        client, calls = client_for(httpx.Response(200, content=PNG, headers={"content-type": "image/png"}))
        out = await cf.inpaint(b"img", b"msk", "red nails", "blurry", 42, client=client)
        self.assertEqual(out, PNG)
        req = calls[0]
        self.assertEqual(str(req.url), f"https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/{cf.MODEL}")
        self.assertEqual(req.headers["authorization"], "Bearer secret-token")
        body = json.loads(req.content)
        self.assertEqual(body["image"], list(b"img"))
        self.assertEqual(body["mask"], list(b"msk"))
        self.assertEqual((body["width"], body["height"], body["num_steps"], body["guidance"], body["strength"],
                          body["seed"]), (512, 512, 20, 7.5, 1.0, 42))
        sleep.assert_not_awaited()

    async def test_429_then_success_retries(self, sleep):
        client, calls = client_for(httpx.Response(429, text="slow down"), httpx.Response(200, content=PNG))
        self.assertEqual(await cf.inpaint(b"i", b"m", "p", "n", 1, client=client), PNG)
        self.assertEqual(len(calls), 2)
        sleep.assert_awaited_once_with(1)

    async def test_400_raises_and_logs_body_not_token(self, sleep):
        client, calls = client_for(httpx.Response(400, text='{"errors":[{"message":"bad mask"}]}'))
        with self.assertLogs("generation.cloudflare_client", "ERROR") as logs, \
                self.assertRaisesRegex(cf.CloudflareError, "400"):
            await cf.inpaint(b"i", b"m", "p", "n", 1, client=client)
        self.assertEqual(len(calls), 1)
        self.assertIn("bad mask", logs.output[0])
        self.assertNotIn("secret-token", "".join(logs.output))

    async def test_5xx_gives_up_after_3_retries(self, sleep):
        client, calls = client_for(*[httpx.Response(503, text="down")] * 4)
        with self.assertRaises(cf.CloudflareError), self.assertLogs("generation.cloudflare_client"):
            await cf.inpaint(b"i", b"m", "p", "n", 1, client=client)
        self.assertEqual(len(calls), 4)
        self.assertEqual([c.args[0] for c in sleep.await_args_list], [1, 2, 4])


if __name__ == "__main__":
    unittest.main()
