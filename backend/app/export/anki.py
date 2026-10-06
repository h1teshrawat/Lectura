"""Export flashcards as a CSV file that Anki can import directly.

Anki (a popular free spaced-repetition app) reads special header lines:
  #separator:comma   -> fields are separated by commas
  #html:true         -> fields may contain HTML (we add a timestamp link)
  #tags column:3     -> the third column holds tags
In Anki: File -> Import -> choose the .csv, select the "Basic" note type.
"""

import csv
import html
import io
import re

from app.generators.schemas import Flashcard
from app.transcription.models import format_timestamp


def anki_tag(title: str) -> str:
    """'But what is a neural network?' -> 'Lectura::but-what-is-a-neural-network'."""
    slug = re.sub(r"[^\w]+", "-", title.lower(), flags=re.UNICODE).strip("-")[:60] or "lecture"
    return f"Lectura::{slug}"


def flashcards_to_anki_csv(cards: list[Flashcard], lecture_title: str, video_url: str | None = None) -> str:
    output = io.StringIO()
    output.write("#separator:comma\n#html:true\n#tags column:3\n")
    writer = csv.writer(output, lineterminator="\n")
    tag = anki_tag(lecture_title)
    for card in cards:
        stamp = format_timestamp(card.start_seconds)
        if video_url:
            separator = "&" if "?" in video_url else "?"
            link = f'<a href="{html.escape(video_url)}{separator}t={int(card.start_seconds)}s">&#9654; {stamp}</a>'
        else:
            link = f"({stamp})"
        back = f"{html.escape(card.answer)}<br><small>{link}</small>"
        writer.writerow([html.escape(card.question), back, tag])
    return output.getvalue()
