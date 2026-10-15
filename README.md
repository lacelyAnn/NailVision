# NailVision

Vue 3 + Vite frontend (nail detection runs in the browser via ONNX) and a Python Stable Diffusion service (`sd-server/`) that generates nail designs.

## Requirements

- Node.js 20+ (24 recommended) and npm
- Python 3.12 (only if you run `sd-server` locally)
- ~2 GB free disk for the SD weights (only for real generation; not needed with `MOCK=1`)

## Run the frontend

```sh
npm install
cp .env.example .env     # set VITE_SD_URL (default http://localhost:8000)
npm run dev
```

Other scripts: `npm run build`, `npm run lint`.

## Run the SD server locally

```sh
cd sd-server
python -m venv .venv
.venv\Scripts\activate                     # macOS/Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Quick test without Stable Diffusion (fast fake output):

```sh
# PowerShell: $env:MOCK = "1"      bash: export MOCK=1
python -m uvicorn server:app --port 8000
```

Real generation: unset `MOCK`. The first job downloads the model (~2 GB) into `MODEL_DIR` (default `../gpu/sd15-inpainting`) and is slow on CPU.

Check it is up: <http://localhost:8000/health>

## Deploy

- **sd-server → Render**: Docker service from `sd-server/` (see `Dockerfile`). Mount a persistent disk at `/models` or the weights re-download on every restart. Env vars: see `sd-server/.env.example`.
- **frontend → Vercel**: set `VITE_SD_URL` (your Render URL) and optionally `VITE_SD_TOKEN` (see `.env.example`). Set `ALLOWED_ORIGINS` on Render to your Vercel URL.

CPU generation on Render is slow by design; the frontend polls the job until the designs are ready.
