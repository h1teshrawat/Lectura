---
title: Lectura API
emoji: 🎓
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 6.29.1
python_version: "3.11"
app_file: server.py
app_port: 7860
pinned: false
short_description: AI lecture notes, flashcards, quizzes and RAG chat (backend)
---

# Lectura backend

FastAPI backend of Lectura: turns lectures into notes, flashcards, quizzes and a grounded
chat. Interactive API docs: `/docs`.

This Space uses the free **Gradio** SDK only as a Python runtime: `server.py` starts the
FastAPI app on port 7860 (system packages come from `packages.txt`).

Secrets to set in **Settings → Variables and secrets**: `GROQ_API_KEY` (and optionally
`GEMINI_API_KEY`). Variable: `CORS_ORIGINS` = `["https://your-app.vercel.app"]`.
