# LectureLens

AI-powered YouTube/lecture summariser and quiz generator: smart notes with clickable timestamps, flashcards, MCQ quizzes and "chat with the lecture" (RAG). Supports English, Hindi and Hinglish.

> 🚧 Work in progress. The full README (architecture, setup, evaluation, deployment) is written in Phase (j).

## Progress

- [x] **Phase a:** transcription (YouTube captions → Groq Whisper → local faster-whisper)
- [ ] Phase b: LLM layer + notes (chunking, map-reduce)
- [ ] Phase c: flashcards + MCQs with validation
- [ ] Phase d: FastAPI, background jobs, SSE, SQLite cache
- [ ] Phase e: React frontend (home, processing, notes)
- [ ] Phase f: flashcards + quiz UI
- [ ] Phase g: RAG chat
- [ ] Phase h: library, stats, export
- [ ] Phase i: evaluation
- [ ] Phase j: polish, README, deployment

## Quick start (backend, Windows PowerShell)

```powershell
cd C:\Projects\LectureLens\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # then add your API keys (optional for Phase a)
python -m pytest
python -m cli.transcribe https://www.youtube.com/watch?v=aircAruvnKk
```

Requires Python 3.11, ffmpeg (`winget install Gyan.FFmpeg`) and Node.js (used by yt-dlp for YouTube downloads).
