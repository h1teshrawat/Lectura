"""Export processed lectures as demo lectures for the live (cloud) version.

Examples (run from backend/ with the venv active):
    python -m cli.export_demo                      # list your finished lectures
    python -m cli.export_demo 13ee135b564a 738d1c97d9d7

Files are written to demo_lectures/ (commit them). The cloud server loads
them on startup when SEED_DEMO_LECTURES=true.
"""

import argparse
import sys

from sqlmodel import Session, select

from app.config import get_settings
from app.db.demo import export_lecture
from app.db.models import Lecture
from app.db.session import create_db_engine, resolve_db_path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Export lectures as bundled demo lectures")
    parser.add_argument("ids", nargs="*", help="Lecture IDs to export (none = list finished lectures)")
    args = parser.parse_args()

    engine = create_db_engine(resolve_db_path(get_settings().data_path))
    with Session(engine) as session:
        if not args.ids:
            for lecture in session.exec(select(Lecture).where(Lecture.status == "done")):
                print(f"{lecture.id}  {lecture.source_id:<14} {lecture.title}")
            return 0
        for lecture_id in args.ids:
            lecture = session.get(Lecture, lecture_id)
            if lecture is None:
                print(f"No lecture with ID {lecture_id}")
                return 1
            print(f"Saved {export_lecture(lecture)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
