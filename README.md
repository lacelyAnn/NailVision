# 💅 NailVision

**Capture · Choose · Get your perfect look.**
Upload a photo of your hand, pick up to three polish colors, and NailVision paints **5 nail designs** on your own nails.

| | |
|---|---|
| 🖼️ **Frontend** | Vue 3 + Vite. Finds your nails right in the browser. |
| 🎨 **Design service** | A Python Stable Diffusion server (`sd-server/`) that paints the designs. It uses your **GPU** when there is one, otherwise your **CPU**. |

---

## 📖 Table of contents

1. [Get the code (clone)](#-get-the-code-clone)
2. [How to use NailVision](#-how-to-use-nailvision)
3. [Quick start](#-quick-start)
4. [Pages at a glance](#-pages-at-a-glance)
5. [Settings explained](#-settings-explained)
6. [Troubleshooting](#-troubleshooting)
7. [Deploy](#-deploy)

---

## 📥 Get the code (clone)

### 🧰 Before you start
Install **Git** from <https://git-scm.com/downloads> and check it works:

```sh
git --version
```

### 📋 Clone it

```sh
git clone https://github.com/nikopolistico/NailVision.git
cd NailVision
```

This creates a `NailVision` folder with the whole project. Then continue with the [Quick start](#-quick-start).

### 🔄 Get the latest updates later
Run this inside the `NailVision` folder:

```sh
git pull
npm install
```

(`npm install` picks up any new packages.)

### 📦 What you do **not** get from the clone
These are too big or private, so they are not in the repository:

| Missing | What to do |
|---|---|
| `node_modules/` | Run `npm install`. |
| The Python environment (`.venv`) | Create it in [Quick start → Step 2](#-step-2--start-the-design-service). |
| The Stable Diffusion model (~2 GB) | It downloads by itself the first time you generate a real design. |
| Your `.env` file | Create one next to `package.json` with `VITE_SD_URL=http://localhost:8000`. |

> 🔐 Never commit real passwords or tokens. Keep them in `.env`, not in the code.

### 🍴 Want your own copy to change?
Click **Fork** on GitHub first, then clone **your** fork's address instead:

```sh
git clone https://github.com/<your-username>/NailVision.git
```

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

> The app talks to the design service at
> For local use create a `.env` file with:
> `VITE_SD_URL=http://localhost:8000`
> `VITE_SUPABASE_URL: = `
> `VITE_SUPABASE_ANON_KEY: = ` 

> ### 🎨 Step 2 · Start the design service

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
| 🗂️ **Previous designs** | Every design you saved. Rate, filter (All / Rated / Unrated), view full screen, delete, and browse by page. **Book at a salon** sends a design to a company. |
| 📅 **My bookings** (client) | Designs you sent to a salon, their status, and the technician's rating and advice. |
| 💼 **Design reviews** (technician) | Bookings for your company. Set the status, rate if the design is worth it, and leave advice. |

Clients use pages under `#/client`, nail technicians under `#/tech`. Each account only sees its own area.

### 🔐 Accounts (Supabase)

1. Create a free project at <https://supabase.com>.
2. Open **SQL Editor**, paste [`supabase/schema.sql`](supabase/schema.sql), and run it. It creates the tables and the security rules. Accounts live in the app's own `credentials` table (passwords stored as bcrypt hashes), so Supabase Auth, its emails and its rate limits are not used. [`supabase/reset.sql`](supabase/reset.sql) removes everything again.
3. Copy **Project Settings → API** values into `.env`:
   ```sh
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_ANON_KEY=your-anon-key
   ```
4. Sign up twice with a username and password: once as **Client**, once as **Nail technician** (type your salon's name and address). Each technician sign-up adds that salon to the list clients book from.

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

## 📱 Mobile app (Android)

NailVision is wrapped with [Capacitor](https://capacitorjs.com). The Android project lives in `android/`.

1. Install [Android Studio](https://developer.android.com/studio) (it brings the Android SDK and Java).
2. Make sure `.env` points `VITE_SD_URL` at a public **https** design service. `localhost` on your PC is not reachable from the phone.
3. Run:
   ```sh
   npm run android
   ```
   It builds the web app, copies it into `android/`, and opens Android Studio. Press ▶ Run to install on a phone or emulator.

Run `npm run android` again after every code change. iOS needs a Mac (`npm i @capacitor/ios && npx cap add ios`).

---

## ☁️ Deploy

- 🐳 **Design service → Render:** a Docker service from `sd-server/` (see its `Dockerfile`). Mount a persistent disk at `/models`, or the model downloads again on every restart. Environment variables: see `sd-server/.env.example`.
- ▲ **Frontend → Vercel:** set `VITE_SD_URL` to your Render address, and optionally `VITE_SD_TOKEN`. On Render, set `ALLOWED_ORIGINS` to your Vercel address.

> ⏱️ A CPU on Render is slow by design. The app keeps checking the job until the designs are ready.

---

Made with 💖 for nail lovers. Questions or ideas? Open an issue.
