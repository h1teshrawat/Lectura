# Deploying Lectura (free)

| Part | Where | Notes |
|---|---|---|
| Backend | **Render**, free web service, Docker, *lite mode* | 512 MB RAM: no local models; Groq Whisper for speech-to-text, Gemini API for chat embeddings |
| Frontend | **Vercel**, free *Hobby* plan | Static site on a global CDN, deploys from GitHub |

**Why "lite mode"?** The full backend (PyTorch + local Whisper + local embedding model) needs over
1 GB of RAM. Free hosts give 512 MB, so the cloud version uses APIs instead of local models.
It's the same code, switched by two settings (already set in `backend/Dockerfile.lite`):

```
LOCAL_WHISPER_ENABLED=false   # speech-to-text only via Groq Whisper (YouTube captions still used first)
EMBEDDING_PROVIDER=gemini     # chat search uses Gemini embeddings instead of a local model
```

Measured locally in lite mode: **~150 MB idle, ~185 MB peak** while processing an 18-minute lecture.

> *Hugging Face Spaces?* Until 2026 its free CPU tier could run the full backend, but new free
> accounts can now only create ZeroGPU Spaces (with tight daily limits), and Docker Spaces are paid.
> `backend/Dockerfile` (full mode) still works on any host with ≥ 2 GB RAM.

Order: **1. API keys → 2. GitHub → 3. Render (backend) → 4. Vercel (frontend) → 5. connect them.**

---

## 1. API keys

- **Groq** (you already have it): transcription + notes/quiz generation.
- **Gemini** (free, needed online for the chat): <https://aistudio.google.com> → **Get API key** →
  **Create API key** → copy it.

## 2. Put the code on GitHub

1. <https://github.com> → **New repository** → name `lectura` → *Public* → don't add a README → **Create**.
2. In PowerShell:

```powershell
cd C:\Projects\LectureLens
git remote add origin https://github.com/YOUR-USERNAME/lectura.git
git push -u origin main
```

Your keys (`backend\.env`), the database and the virtual environment are git-ignored and are
**not** uploaded. Check on GitHub that no `.env` file appears (only `.env.example`).

## 3. Backend on Render (free)

1. Sign up at <https://render.com> with **GitHub**.
2. **New → Blueprint** → connect/select the `lectura` repository. Render reads `render.yaml`.
3. It asks for the secret values: paste your **GROQ_API_KEY** and **GEMINI_API_KEY**. Leave
   `CORS_ORIGINS` as it is for now. Click **Apply** / **Deploy Blueprint**.
4. The first build takes ~5–10 minutes. When the service shows **Live**, copy its URL
   (like `https://lectura-backend.onrender.com`) and open `…/api/health`. You should see
   `"groq_configured": true`, `"gemini_configured": true`, `"embedding_provider": "gemini"`.

*Manual alternative (instead of the Blueprint):* **New → Web Service** → your repo →
Root Directory `backend` → Language **Docker** → Dockerfile Path `./Dockerfile.lite` →
Instance type **Free** → add the environment variables `GROQ_API_KEY`, `GEMINI_API_KEY`, `CORS_ORIGINS`.

## 4. Frontend on Vercel (free)

1. <https://vercel.com> → **Sign up with GitHub** → **Add New… → Project** → import `lectura`.
2. **Root Directory** → **Edit** → `frontend`.
3. **Environment Variables**: `VITE_API_URL` = your Render URL, e.g. `https://lectura-backend.onrender.com`
   (no `/` at the end). It is built into the site, so redeploy after changing it.
4. **Deploy** → copy the address, e.g. `https://lectura-abc.vercel.app`.

`frontend/vercel.json` sends every path to `index.html`, so links like `/library` survive a refresh.

## 5. Connect them (CORS)

Browsers only allow a website to call an API on another domain if the API lists that website
(**CORS**). In Render → your service → **Environment** → edit `CORS_ORIGINS`:

```
["https://lectura-abc.vercel.app"]
```

**Save Changes** (Render redeploys automatically). Open your Vercel URL: no yellow
"backend isn't running" banner, and uploading a short MP3/MP4 works end to end.

## Optional: tune the chat threshold for Gemini embeddings

Each embedding model has its own similarity range. On your PC (with `GEMINI_API_KEY` in `backend\.env`):

```powershell
cd C:\Projects\LectureLens\backend
.\.venv\Scripts\Activate.ps1
python -m cli.calibrate_rag 13ee135b564a --provider gemini
```

It prints scores for on-topic and off-topic questions and suggests a value. Add it in Render as
`RAG_MIN_SIMILARITY` (default 0.20; with the local model the suggestion was 0.41).

---

## What to expect on the free plan

| Behaviour | Why / what to do |
|---|---|
| First visit after a break takes ~1 minute | Free services **sleep after 15 minutes** without traffic; refresh once it wakes |
| Lectures disappear after the service sleeps or redeploys | The free disk is **temporary**. Process a lecture and use it in the same session (fine for demos) |
| YouTube links often fail online | YouTube blocks many cloud-server requests. **Upload the audio/video file** instead (works locally too) |
| No offline fallback for transcription | Lite mode has no local Whisper: if Groq is rate-limited, wait a minute and retry |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser console: "blocked by CORS policy" | `CORS_ORIGINS` must contain the exact Vercel URL (https, no trailing slash) |
| Yellow "backend isn't running" banner | Backend asleep (wait ~1 min and refresh) or wrong `VITE_API_URL` (fix it and redeploy Vercel) |
| `/api/health` shows `groq_configured: false` | Add `GROQ_API_KEY` in Render → Environment |
| Chat says "GEMINI_API_KEY is not set" | Add `GEMINI_API_KEY` in Render → Environment |
| Render build fails | Open **Logs**, send the last ~30 lines for help |

## Security notes

- API keys live only in Render's environment settings, never in the frontend or in git.
- There is **no login**: anyone with the URL can process lectures with your free API quota.
  Share the link with people you trust; authentication is listed under future scope.
