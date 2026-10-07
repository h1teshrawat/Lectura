# Lectura backend, FULL mode (local Whisper + local embeddings; needs >= 2 GB RAM).
# For the free 512 MB cloud plan use Dockerfile.lite instead (see docs/DEPLOYMENT.md).
#
# Build context = the backend/ folder:
#   docker build -t lectura-backend backend
#   docker run -p 7860:7860 -e GROQ_API_KEY=... lectura-backend

FROM python:3.11-slim

# ffmpeg: audio conversion. fonts-noto-core: Latin + Devanagari fonts for PDF export.
# nodejs: JavaScript runtime that yt-dlp uses for YouTube downloads.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-core nodejs \
    && rm -rf /var/lib/apt/lists/*

# Run as a normal user, not root (a security best practice for containers).
RUN useradd --create-home --uid 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface
# Create the app folder as `user`, so the app can write its database and caches.
RUN mkdir -p /home/user/app/data
WORKDIR /home/user/app

# Install the CPU-only build of PyTorch first: the default Linux build includes
# CUDA libraries (several GB) that a CPU server can't use.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

# Listens on $PORT if the host sets it (Render does), otherwise 7860.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
