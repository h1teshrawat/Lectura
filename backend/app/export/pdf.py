"""Export smart notes as a clean, printable PDF (with clickable timestamps)."""

import logging

from fpdf import FPDF

from app.export.fonts import FontSet, find_fonts
from app.generators.schemas import LectureNotes
from app.transcription.models import format_timestamp

logger = logging.getLogger(__name__)
# fontTools prints harmless "MERG NOT subset" warnings while embedding fonts.
logging.getLogger("fontTools").setLevel(logging.ERROR)

_PLAIN_CHARACTERS = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "−": "-",  # hyphen variants, minus
    " ": " ", " ": " ", " ": " ", "​": "",    # special spaces
})

ACCENT = (75, 75, 195)
INK = (28, 28, 26)
MUTED = (102, 101, 95)
SOFT_BG = (238, 240, 255)
LINE_HEIGHT = 5.6


class _NotesPDF(FPDF):
    body_family = "helvetica"  # replaced by "body" when a Unicode font is registered

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(self.body_family, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"LectureLens  ·  page {self.page_no()}", align="C")


def _timestamp_link(video_url: str | None, seconds: float) -> str:
    if not video_url:
        return ""
    separator = "&" if "?" in video_url else "?"
    return f"{video_url}{separator}t={int(seconds)}s"


class _Writer:
    """Small helpers that keep the layout code readable."""

    def __init__(self, pdf: _NotesPDF, unicode_ok: bool) -> None:
        self.pdf = pdf
        self.unicode_ok = unicode_ok
        self.family = pdf.body_family

    def text(self, value: str) -> str:
        # LLMs like typographic characters (non-breaking hyphens, thin spaces)
        # that many fonts lack; use plain equivalents so nothing disappears.
        value = value.translate(_PLAIN_CHARACTERS)
        if self.unicode_ok:
            return value
        # Built-in PDF fonts only know Latin-1: replace anything else.
        return value.encode("latin-1", "replace").decode("latin-1")

    def font(self, style: str = "", size: float = 10.5, color: tuple[int, int, int] = INK) -> None:
        self.pdf.set_font(self.family, style, size)
        self.pdf.set_text_color(*color)

    def heading(self, value: str, size: float = 13) -> None:
        self.pdf.ln(3)
        self.font("B", size)
        self.pdf.multi_cell(0, 7, self.text(value), new_x="LMARGIN", new_y="NEXT", align="L")
        self.pdf.ln(1)

    def paragraph(self, value: str, color: tuple[int, int, int] = INK) -> None:
        self.font("", 10.5, color)
        self.pdf.multi_cell(0, LINE_HEIGHT, self.text(value), new_x="LMARGIN", new_y="NEXT", align="L")
        self.pdf.ln(1.5)

    def bullets(self, items: list[str]) -> None:
        bullet = "•" if self.unicode_ok else "-"
        for item in items:
            self.font("", 10.5)
            self.pdf.set_x(self.pdf.l_margin + 2)
            self.pdf.cell(5, LINE_HEIGHT, bullet)
            self.pdf.multi_cell(self.pdf.epw - 7, LINE_HEIGHT, self.text(item), new_x="LMARGIN", new_y="NEXT", align="L")
            self.pdf.ln(0.8)
        self.pdf.ln(1)

    def definition(self, term: str, meaning: str) -> None:
        self.pdf.set_fill_color(*SOFT_BG)
        self.font("B", 10)
        # write() flows inline text and wraps it within the margins.
        self.pdf.write(LINE_HEIGHT, self.text(term) + ": ")
        self.font("", 10)
        self.pdf.write(LINE_HEIGHT, self.text(meaning))
        self.pdf.ln(LINE_HEIGHT + 1.5)


def _register_fonts(pdf: _NotesPDF, fonts: FontSet) -> bool:
    """Register Unicode fonts if available. Returns True if Unicode text is supported."""
    if not fonts.has_unicode:
        logger.warning("No Unicode font found: PDF will use a basic font (non-Latin text replaced).")
        pdf.body_family = "helvetica"
        return False

    pdf.add_font("body", "", str(fonts.regular.path), collection_font_number=fonts.regular.collection_index)
    pdf.add_font("body", "B", str(fonts.bold.path), collection_font_number=fonts.bold.collection_index)
    pdf.body_family = "body"
    if fonts.devanagari:
        for style in ("", "B"):
            pdf.add_font(
                "devanagari", style, str(fonts.devanagari.path),
                collection_font_number=fonts.devanagari.collection_index,
            )
        # Characters missing from the main font (e.g. Hindi) are taken from this one.
        pdf.set_fallback_fonts(["devanagari"], exact_match=False)
    try:
        # Text shaping joins Devanagari letters correctly (needs the uharfbuzz package).
        pdf.set_text_shaping(True)
    except Exception:  # noqa: BLE001 - shaping is an enhancement, not a requirement
        logger.warning("Text shaping unavailable: install uharfbuzz for correct Hindi rendering.")
    return True


def notes_to_pdf(
    notes: LectureNotes,
    lecture_title: str,
    video_url: str | None = None,
    subtitle: str | None = None,
) -> bytes:
    """Render notes as a PDF and return the file contents."""
    pdf = _NotesPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=18)
    pdf.set_title(notes.title)
    pdf.set_author("LectureLens")
    unicode_ok = _register_fonts(pdf, find_fonts())
    w = _Writer(pdf, unicode_ok)
    pdf.add_page()

    # Title block
    w.font("B", 20)
    pdf.multi_cell(0, 9, w.text(notes.title), new_x="LMARGIN", new_y="NEXT", align="L")
    w.font("", 9.5, MUTED)
    source = lecture_title if not subtitle else f"{lecture_title}  ·  {subtitle}"
    pdf.multi_cell(0, 5, w.text(source), new_x="LMARGIN", new_y="NEXT", link=video_url or "", align="L")
    pdf.ln(3)
    pdf.set_draw_color(225, 224, 217)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)

    w.heading("Overview")
    w.paragraph(notes.overview)
    w.heading("Key takeaways")
    w.bullets(notes.key_takeaways)

    for section in notes.sections:
        pdf.ln(2)
        stamp = format_timestamp(section.start_seconds)
        w.font("B", 12.5, ACCENT)
        pdf.write(7, f"[{stamp}] ", link=_timestamp_link(video_url, section.start_seconds))
        w.font("B", 12.5)
        pdf.write(7, w.text(section.title))
        pdf.ln(9)
        w.paragraph(section.summary, color=(60, 60, 56))
        w.bullets(section.key_points)
        for definition in section.definitions:
            w.definition(definition.term, definition.definition)

    if notes.glossary:
        w.heading("Glossary")
        for definition in notes.glossary:
            w.definition(definition.term, definition.definition)

    return bytes(pdf.output())
