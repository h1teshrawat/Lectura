"""Calibrate RAG_MIN_SIMILARITY for an embedding provider.

Different embedding models produce different similarity ranges (with the
local MiniLM model, unrelated questions score ~0.0-0.15; Gemini embeddings
typically score higher). This tool measures it on one of your lectures:

  - on-topic questions  = the lecture's own flashcard questions
  - off-topic questions = general-knowledge questions unrelated to any lecture

and suggests a threshold between the two groups.

Usage (from backend/ with the venv active):
    python -m cli.calibrate_rag 13ee135b564a                       # provider from .env
    python -m cli.calibrate_rag 13ee135b564a --provider gemini     # needs GEMINI_API_KEY
"""

import argparse
import json
import sqlite3
import sys

from app.config import BACKEND_DIR, get_settings
from app.db.session import DB_FILENAME
from app.errors import LecturaError
from app.rag.embedder import GeminiEmbedder, SentenceTransformerEmbedder
from app.rag.service import RAGService
from app.rag.vector_store import ChromaVectorStore
from app.transcription.models import Transcript

OFF_TOPIC = [
    "Who won the cricket world cup in 2011?",
    "What is the capital of France?",
    "How do I bake a chocolate cake?",
    "What is the price of gold today?",
    "Who wrote the novel Pride and Prejudice?",
    "How many players are in a football team?",
    "भारत की राजधानी क्या है?",
    "Best places to visit in Goa?",
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Calibrate the RAG similarity threshold")
    parser.add_argument("lecture_id", help="A processed lecture (ID from the browser address bar)")
    parser.add_argument("--provider", choices=["local", "gemini"], help="Override EMBEDDING_PROVIDER")
    args = parser.parse_args()

    settings = get_settings()
    connection = sqlite3.connect(BACKEND_DIR / "data" / DB_FILENAME)
    row = connection.execute(
        "SELECT title, transcript_json, flashcards_json FROM lecture WHERE id = ?", (args.lecture_id,)
    ).fetchone()
    connection.close()
    if not row or not row[1] or not row[2]:
        print("Lecture not found or not fully processed.")
        return 1
    title, transcript = row[0], Transcript.model_validate_json(row[1])
    on_topic = [card["question"] for card in json.loads(row[2])["cards"]][:12]

    provider = args.provider or settings.embedding_provider
    embedder = (
        GeminiEmbedder(settings.gemini_api_key, settings.gemini_embedding_model)
        if provider == "gemini"
        else SentenceTransformerEmbedder(settings.embedding_model)
    )
    rag = RAGService(ChromaVectorStore(None), embedder, lambda: None, settings)  # in-memory index

    print(f"\nCalibrating '{provider}' embeddings on: {title}")
    try:
        rag.index_transcript("calibration", transcript)
        def best(question: str) -> float:
            return rag.retrieve("calibration", question)[0].similarity
        on_scores = [best(q) for q in on_topic]
        off_scores = [best(q) for q in OFF_TOPIC]
    except LecturaError as exc:
        print(f"ERROR: {exc.message}  {exc.hint}")
        return 1

    print("\nOn-topic (the lecture's flashcard questions):")
    for q, s in zip(on_topic, on_scores):
        print(f"  {s:.2f}  {q[:80]}")
    print("\nOff-topic (unrelated questions):")
    for q, s in zip(OFF_TOPIC, off_scores):
        print(f"  {s:.2f}  {q}")

    low_on, high_off = min(on_scores), max(off_scores)
    print(f"\nLowest on-topic: {low_on:.2f}   Highest off-topic: {high_off:.2f}")
    if low_on > high_off:
        print(f"Suggested RAG_MIN_SIMILARITY = {(low_on + high_off) / 2:.2f}  (halfway between the groups)")
    else:
        print(f"The groups overlap. Suggested RAG_MIN_SIMILARITY = {high_off + 0.02:.2f}: unrelated "
              "questions are still caught by the LLM's 'not covered' rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
