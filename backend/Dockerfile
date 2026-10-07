# Lectura backend: container image for Hugging Face Spaces (Docker) or Render.
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

# Hugging Face Spaces run containers as user 1000; use the same user everywhere.
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

# Hugging Face Spaces expect port 7860; Render passes its port in $PORT.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
