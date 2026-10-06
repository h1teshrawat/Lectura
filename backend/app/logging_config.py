"""Logging setup shared by the API server and the CLI scripts."""

import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with a readable, timestamped format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # These libraries are very chatty at INFO level.
    for noisy in ("httpx", "httpcore", "faster_whisper", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
