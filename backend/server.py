"""Start the Lectura API with uvicorn (used by hosting platforms).

Hugging Face *Gradio* Spaces (free) simply run `python server.py` after
installing requirements.txt and the system packages in packages.txt, and
expect a web server on port 7860. We don't use Gradio's UI at all: this just
starts our FastAPI app on that port.

Locally you don't need this file: use `uvicorn app.main:app --reload` or start.bat.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
