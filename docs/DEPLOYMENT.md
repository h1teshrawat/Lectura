# Deploying Lectura (free)

| Part | Where | Why |
|---|---|---|
| Backend (FastAPI + Whisper + embeddings) | **Hugging Face Spaces**, *Gradio* SDK, free *CPU basic* (2 vCPU, 16 GB RAM) | Enough memory for PyTorch, the embedding model and local Whisper |
| Frontend (React) | **Vercel**, free *Hobby* plan | Static site + global CDN, deploys from GitHub |
| Alternative backend | Render (Docker) | Free instances have only 512 MB RAM: use the paid *starter* plan |

> **Why the Gradio SDK?** Hugging Face's *Docker* Spaces are a paid feature, but *Gradio*
> Spaces are free. We use the Gradio SDK only as a Python runtime: it installs
> `requirements.txt` and the system tools in `packages.txt` (ffmpeg, fonts, Node.js), then
> runs `server.py`, which starts the FastAPI app on port 7860. Gradio's own UI is not used.
> `server.py` was tested locally; the Space build itself runs in the cloud, so if it fails,
> the **Logs** tab shows the exact step.

Order: **1. GitHub → 2. backend → 3. frontend → 4. connect them (CORS).**

---

## 1. Put the code on GitHub

1. Create an account at <https://github.com>, then **New repository** → name `lectura` → **Create**
   (leave "Add a README" unticked: the project already has one).
2. In PowerShell:

```powershell
cd C:\Projects\LectureLens
git remote add origin https://github.com/YOUR-USERNAME/lectura.git
git push -u origin main
```

`backend\.env` (your keys), the database and the virtual environment are in `.gitignore`,
so they are **not** uploaded. Check on GitHub that no `.env` file appears.

---

## 2. Backend on Hugging Face Spaces

1. Create an account at <https://huggingface.co>.
2. **New → Space**: name `lectura-api`, SDK **Gradio** → *Blank* (Docker is paid; Gradio is free),
   hardware **CPU basic (free)**, visibility *Public* (a *Private* Space can't be called by the
   frontend without a token, so keep it Public).
3. Copy the backend files into the Space's git repository:

```powershell
# One-time: a Hugging Face access token with "write" permission is needed for git push:
# huggingface.co -> Settings -> Access Tokens -> New token (type: Write).
cd $env:USERPROFILE
git clone https://huggingface.co/spaces/YOUR-HF-USERNAME/lectura-api
robocopy C:\Projects\LectureLens\backend lectura-api /E /XD .venv data __pycache__ .pytest_cache tests /XF .env Dockerfile .dockerignore
Copy-Item C:\Projects\LectureLens\deploy\huggingface-space-README.md lectura-api\README.md -Force
cd lectura-api
git add .
git commit -m "Deploy Lectura backend"
git push      # username = your HF username, password = the access token
```

4. In the Space: **Settings → Variables and secrets**
   - **Secret** `GROQ_API_KEY` = your Groq key (optionally also `GEMINI_API_KEY`)
   - **Variable** `CORS_ORIGINS` = `["https://your-app.vercel.app"]` (update after step 3)
5. The first build takes ~10 minutes (PyTorch). The Space page may show an empty frame
   instead of a Gradio app: that's expected. When the status is **Running**, open
   `https://YOUR-HF-USERNAME-lectura-api.hf.space/docs`: you should see the API docs, and
   `/api/health` should show `"groq_configured": true`.

**Good to know**
- Free Spaces **sleep** after ~48 h without visitors and wake up on the next request (slow first load).
- The free disk is **not persistent**: lectures are lost when the Space restarts. Fine for a demo;
  persistent storage is a paid add-on.
- YouTube often **blocks downloads and captions from cloud servers**. On the deployed version,
  uploading an MP3/MP4 is the reliable path; locally, YouTube links work normally.
- The embedding and Whisper models download on first use (a few hundred MB, done once per start).

---

## 3. Frontend on Vercel

1. Sign in at <https://vercel.com> with GitHub → **Add New… → Project** → import `lectura`.
2. **Root Directory**: `frontend` (Vercel detects Vite automatically).
3. **Environment Variables**: `VITE_API_URL` = `https://YOUR-HF-USERNAME-lectura-api.hf.space`
   (no trailing slash). It is built into the site, so redeploy after changing it.
4. **Deploy**. You get a URL like `https://lectura-xyz.vercel.app`.

`frontend/vercel.json` sends every path to `index.html`, so links like `/library` work after a refresh.

---

## 4. Connect them (CORS)

Browsers only let a website call an API on another domain if the API allows that website
(**CORS**: Cross-Origin Resource Sharing). In the Space settings set:

```
CORS_ORIGINS = ["https://lectura-xyz.vercel.app"]
```

then **Restart** the Space. Open your Vercel URL: the yellow "backend isn't running" banner
should not appear, and the sample lectures should work.

---

## Alternative: backend on Render

`render.yaml` is a Render *Blueprint*: Dashboard → **New → Blueprint** → choose the GitHub repo.
Set `GROQ_API_KEY` in the dashboard and `CORS_ORIGINS` to your Vercel URL.
Render's **free** instance (512 MB RAM) is too small for PyTorch + the models, so the blueprint
uses the *starter* plan; on the free plan expect out-of-memory restarts.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser console: "blocked by CORS policy" | `CORS_ORIGINS` must contain the exact Vercel URL (https, no trailing slash); restart the backend |
| Yellow "backend isn't running" banner on Vercel | Check `VITE_API_URL`, then redeploy the frontend; check the Space is *Running* |
| `/api/health` shows `groq_configured: false` | Add the `GROQ_API_KEY` **secret** and restart the Space |
| Space build fails | Open **Logs**; most issues are a typo in a copied file or a missing `requirements.txt` |
| YouTube link fails on the deployed app | Expected on cloud IPs; upload the audio/video file instead |

## Security notes

- API keys live only in the backend's secrets, never in the frontend or in git.
- There is **no login**: anyone with the URL can process lectures using your free API quota.
  Share the link only with people you trust (adding authentication is listed under future scope).
