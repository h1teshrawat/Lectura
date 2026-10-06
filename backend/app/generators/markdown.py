"""Render notes as Markdown (used by the CLI now and the export feature later)."""

from app.generators.schemas import LectureNotes
from app.transcription.models import format_timestamp


def notes_to_markdown(notes: LectureNotes, video_url: str | None = None) -> str:
    """Convert notes to Markdown. Timestamps become YouTube links when a URL is given."""

    def stamp(seconds: float) -> str:
        label = format_timestamp(seconds)
        if video_url:
            separator = "&" if "?" in video_url else "?"
            return f"[{label}]({video_url}{separator}t={int(seconds)}s)"
        return f"[{label}]"

    lines = [f"# {notes.title}", "", notes.overview, "", "## Key takeaways", ""]
    lines += [f"- {point}" for point in notes.key_takeaways]
    lines.append("")

    for section in notes.sections:
        lines += [f"## {stamp(section.start_seconds)} {section.title}", "", section.summary, ""]
        lines += [f"- {point}" for point in section.key_points]
        if section.definitions:
            lines.append("")
            lines += [f"> **{d.term}**: {d.definition}" for d in section.definitions]
        if section.key_terms:
            lines += ["", "*Key terms:* " + ", ".join(f"`{t}`" for t in section.key_terms)]
        lines.append("")

    if notes.glossary:
        lines += ["## Glossary", ""]
        lines += [f"- **{d.term}**: {d.definition}" for d in notes.glossary]
        lines.append("")

    return "\n".join(lines)
