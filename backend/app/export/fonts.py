"""Find Unicode fonts for PDF export (Latin + Devanagari), without bundling any.

PDF's 14 built-in fonts only cover Western European characters, so Hindi
needs a real TrueType font. We look for fonts that are already installed:

- Windows: Arial (Latin) and Nirmala UI (Devanagari, ships with Windows 8+)
- Linux / Docker: Noto Sans + Noto Sans Devanagari (`apt install fonts-noto-core`)
  or DejaVu Sans as a Latin fallback

You can also drop .ttf files into backend/fonts/ to override them:
  Regular.ttf, Bold.ttf, Devanagari.ttf
"""

from dataclasses import dataclass
from pathlib import Path

from app.config import BACKEND_DIR

WINDOWS_FONTS = Path("C:/Windows/Fonts")
NOTO = Path("/usr/share/fonts/truetype/noto")
DEJAVU = Path("/usr/share/fonts/truetype/dejavu")
CUSTOM = BACKEND_DIR / "fonts"


@dataclass
class FontFile:
    path: Path
    collection_index: int = 0  # for .ttc files that contain several fonts


@dataclass
class FontSet:
    regular: FontFile | None
    bold: FontFile | None
    devanagari: FontFile | None

    @property
    def has_unicode(self) -> bool:
        return self.regular is not None


def _first_existing(*candidates: FontFile) -> FontFile | None:
    return next((c for c in candidates if c.path.is_file()), None)


def find_fonts() -> FontSet:
    regular = _first_existing(
        FontFile(CUSTOM / "Regular.ttf"),
        FontFile(WINDOWS_FONTS / "arial.ttf"),
        FontFile(NOTO / "NotoSans-Regular.ttf"),
        FontFile(DEJAVU / "DejaVuSans.ttf"),
    )
    bold = _first_existing(
        FontFile(CUSTOM / "Bold.ttf"),
        FontFile(WINDOWS_FONTS / "arialbd.ttf"),
        FontFile(NOTO / "NotoSans-Bold.ttf"),
        FontFile(DEJAVU / "DejaVuSans-Bold.ttf"),
    )
    devanagari = _first_existing(
        FontFile(CUSTOM / "Devanagari.ttf"),
        FontFile(WINDOWS_FONTS / "Nirmala.ttc", collection_index=0),
        FontFile(NOTO / "NotoSansDevanagari-Regular.ttf"),
    )
    return FontSet(regular=regular, bold=bold or regular, devanagari=devanagari)
