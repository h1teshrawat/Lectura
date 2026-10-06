# LectureLens

AI-powered YouTube/lecture summariser and quiz generator: smart notes with clickable timestamps, flashcards, MCQ quizzes and "chat with the lecture" (RAG). Supports English, Hindi and Hinglish.

> 🚧 Work in progress. The full README (architecture, setup, evaluation, deployment) is written in Phase (j).

## Progress

- [x] **Phase a:** transcription (YouTube captions → Groq Whisper → local faster-whisper)
- [x] **Phase b:** LLM layer (Groq / Gemini) + notes (chunking, map-reduce, JSON validation)
- [x] **Phase c:** flashcards + MCQ question bank with quality checks
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
python -m cli.notes data\transcripts\aircAruvnKk.json
python -m cli.study data\transcripts\aircAruvnKk.json --play
```

Requires Python 3.11, ffmpeg (`winget install Gyan.FFmpeg`) and Node.js (used by yt-dlp for YouTube downloads).
