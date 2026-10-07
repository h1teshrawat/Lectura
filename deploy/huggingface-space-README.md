---
title: Lectura API
emoji: 🎓
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: AI lecture notes, flashcards, quizzes and RAG chat (backend)
---

# Lectura backend

FastAPI backend of [Lectura](https://github.com/YOUR-USERNAME/lectura): turns lectures into
notes, flashcards, quizzes and a grounded chat. Interactive API docs: `/docs`.

Secrets to set in **Settings → Variables and secrets**: `GROQ_API_KEY` (and optionally
`GEMINI_API_KEY`). Variable: `CORS_ORIGINS` = `["https://your-app.vercel.app"]`.
