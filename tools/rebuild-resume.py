#!/usr/bin/env python3
"""Rebuild the one-page master resume (.docx + .pdf) from resume/master.md and report the
page count. Works on Mac and Windows.

Usage:  python3 tools/rebuild-resume.py        (Windows: python tools\\rebuild-resume.py)

The files are named after the resume's first line, e.g. "# Alex Q. Doe" -> Alex-Q-Doe-Resume.pdf.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent  # noqa: E402
import documents  # noqa: E402
import jobsfile  # noqa: E402


def main() -> None:
    jobsfile.utf8_stdio()
    cfg = agent.load_config()
    master = agent.HOME / Path(cfg.get("resume_master") or "resume/master.md").expanduser()
    if not master.read_text(encoding="utf-8-sig").startswith("# "):
        sys.exit(f"The first line of {master} must be '# Your Name'.")
    stem = documents.file_stem(cfg, master)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        try:
            pages = documents.build_resume(master, tmp, cfg["chrome_path"], stem)
        except RuntimeError as exc:
            sys.exit(str(exc))
        for ext in ("pdf", "docx"):
            shutil.copy(tmp / f"{stem}-Resume.{ext}", master.parent / f"{stem}-Resume.{ext}")
    print(f"Pages: {pages}" + ("" if pages == 1 else "  <- it must be one page; trim master.md"))
    print(f"Saved to {master.parent / (stem + '-Resume.pdf')} and {stem}-Resume.docx")
    sys.exit(0 if pages == 1 else 1)


if __name__ == "__main__":
    main()
