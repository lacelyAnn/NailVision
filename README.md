# 💅 NailVision

**Capture · Choose · Get your perfect look.**
Upload a photo of your hand, pick up to three polish colors, and NailVision paints **5 nail designs** on your own nails.

| | |
|---|---|
| 🖼️ **Frontend** | Vue 3 + Vite. Finds your nails right in the browser. |
| 🎨 **Design service** | A Python Stable Diffusion server (`sd-server/`) that paints the designs. It uses your **GPU** when there is one, otherwise your **CPU**. |

---

## 📖 Table of contents

1. [How to use NailVision](#-how-to-use-nailvision)
2. [Quick start](#-quick-start)
3. [Pages at a glance](#-pages-at-a-glance)
4. [Settings explained](#-settings-explained)
5. [Troubleshooting](#-troubleshooting)
6. [Deploy](#-deploy)

---

## 🌸 How to use NailVision

Follow these steps in the **Studio** page.

### 1️⃣ 📸 Add a hand photo
Click **Choose a photo** and pick a picture of your hand.
> 💡 Tip: nails facing the camera in even light give the best result.

### 2️⃣ 🔍 Check the detected nails
NailVision finds each nail and numbers it from left to right. Up to **5 nails** are used.
- Nail missing? ⬇️ Lower the **Detection confidence** slider.
- Something that is not a nail got picked up? ⬆️ Raise it.

### 3️⃣ 🎨 Choose your polishes
Click any of the **3 color swatches** to pick a color. The strip above them shows your whole palette at once.
The first three designs use your colors. The other two are suggestions picked for you.

### 4️⃣ ⚙️ Pick the design quality

| Option | Best for |
|---|---|
| ⚡ **Quick** | A fast preview. Looks a bit rougher. |
| ✅ **Balanced** | Recommended for most photos. |
| 💎 **Best** | The finest result. Slowest. |

### 5️⃣ ✨ Press **Generate 5 designs**
- 📊 A progress bar shows how far along you are and about how long is left.
- 🖼️ Each design appears **as soon as it is finished**. You do not have to wait for all five.
- 🔀 You can visit other pages while it runs. It keeps going.

### 6️⃣ ⭐ Rate and save your favorites
- Click the **stars** under a design to rate it. Click the same star again to clear it.
- 🔎 Click a design image to view it **full screen** (press `Esc` to close).
- ⬇️ Use the download icon to save the full photo.
- 💾 Every design is saved automatically in your browser. Find them under **Previous designs**.

---

## 🚀 Quick start

### ✅ You need
- 🟢 **Node.js** 22 or newer, with npm
- 🐍 **Python** 3.12 (only to run the design service on your computer)
- 💽 About **2 GB** of free disk for the model (not needed in test mode)

### 🖥️ Step 1 · Start the app

```sh
npm install
npm run dev
```

Open the address it prints (usually <http://localhost:5173>).

> The app talks to the design service at `VITE_SD_URL`. For local use create a `.env` file with:
> `VITE_SD_URL=http://localhost:8000`

### 🎨 Step 2 · Start the design service

Open a **second terminal**:

```powershell
cd sd-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m uvicorn server:app --port 8000
```

> 🍎🐧 On macOS or Linux use `source .venv/bin/activate` instead of the `Activate.ps1` line.
>
> ⚡ Have an NVIDIA GPU? Install the CUDA build of PyTorch from <https://pytorch.org> instead of the CPU one. The server picks the GPU by itself.

✅ **Check it works:** open <http://localhost:8000/health>. The top bar of the app should say **Design service ready** and show **GPU** or **CPU**.

### 🧪 Just want to try it quickly? Use test mode
Test mode skips Stable Diffusion and returns fast placeholder designs.

```powershell
$env:MOCK = "1"
python -m uvicorn server:app --port 8000
```

(macOS/Linux: `export MOCK=1`.) Remove it for real designs. The first real run downloads the model (~2 GB).

---

## 🧭 Pages at a glance

| Page | What it is for |
|---|---|
| 🏠 **Dashboard** | Your overview: designs made, average rating, recent designs, how you rate designs, and service status. |
| 🎨 **Studio** | Upload a photo, choose polishes, and generate designs. |
| 🗂️ **Previous designs** | Every design you saved. Rate, filter (All / Rated / Unrated), view full screen, delete, and browse by page. |

---

## 🎛️ Settings explained

| Setting | Where | What it does |
|---|---|---|
| `VITE_SD_URL` | `.env` | Address of the design service. |
| `VITE_SD_TOKEN` | `.env` | Optional password. Must match `API_TOKEN` on the server. |
| `MOCK=1` | server | Test mode, no Stable Diffusion. |
| `DEVICE` | server | Force `cuda`, `mps` or `cpu`. Normally leave it empty. |
| `MODEL_DIR` | server | Where the model is stored. |
| `ALLOWED_ORIGINS` | server | Websites allowed to use the server (comma separated). |

More examples are in `.env.example` and `sd-server/.env.example`.

---

## 🛠️ Troubleshooting

**🔴 "Design service offline" in the top bar**
The design service is not running. Start it (Step 2) and click the status pill to recheck.

**🔒 PowerShell says running scripts is disabled when I activate the venv**
Run this first, then activate again:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```
Or skip activation and run Python directly:
```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --port 8000
```

**❓ `python server.py` does nothing**
`server.py` is a web app. Start it with `python -m uvicorn server:app --port 8000`.

**🐢 Designs take minutes**
That is normal on a CPU. A GPU is much faster. You can also pick **Quick** quality.

**🙈 My saved designs disappeared**
Designs are stored in your browser, and only the latest **30** are kept. Clearing the browser's site data removes them.

---

## ☁️ Deploy

- 🐳 **Design service → Render:** a Docker service from `sd-server/` (see its `Dockerfile`). Mount a persistent disk at `/models`, or the model downloads again on every restart. Environment variables: see `sd-server/.env.example`.
- ▲ **Frontend → Vercel:** set `VITE_SD_URL` to your Render address, and optionally `VITE_SD_TOKEN`. On Render, set `ALLOWED_ORIGINS` to your Vercel address.

> ⏱️ A CPU on Render is slow by design. The app keeps checking the job until the designs are ready.

---

Made with 💖 for nail lovers. Questions or ideas? Open an issue.
