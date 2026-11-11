"""Build the resume and cover letter files: Markdown -> .docx + .html (Node), .html -> .pdf
(headless Chrome), and count the PDF's pages. Shared by prep-application.py,
rebuild-resume.py, and the setup wizard. Works on macOS and Windows.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def doc_stem(name: str) -> str:
    """'Alex Q. Doe' -> 'Alex-Q-Doe'; the builders make <stem>-Resume and <stem>-Cover-Letter."""
    # Keep in step with the builders' JavaScript: NFKD, drop accents, then the same regex.
    name = re.sub("[\u0300-\u036f]", "", unicodedata.normalize("NFKD", name))
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-") or "Your-Name"


def file_stem(cfg: dict, master: Path) -> str:
    """The name on the PDF and Word files: config.json's document_name if set, else the resume's
    first line. An all-caps name ("ALEX DOE") is title-cased, since employers see the file name."""
    name = str(cfg.get("document_name") or "").strip() or master_name(master)
    if name.isupper():
        name = name.title()
    return doc_stem(name)


def master_name(master: Path) -> str:
    for line in Path(master).read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Your Name"


def pdf_pages(pdf: Path) -> int:
    """Page count of a PDF Chrome printed (0 if it isn't there or can't be read)."""
    try:
        data = Path(pdf).read_bytes()
    except OSError:
        return 0
    counts = [int(n) for n in re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", data, re.S)]
    counts += [int(n) for n in re.findall(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", data, re.S)]
    if counts:
        return max(counts)
    pages = len(re.findall(rb"/Type\s*/Page\b(?!s)", data))
    if pages:
        return pages
    if shutil.which("pdfinfo"):  # compressed object streams: fall back to poppler if present
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        m = re.search(r"Pages:\s+(\d+)", out)
        if m:
            return int(m.group(1))
    return 0


def to_pdf(html: Path, pdf: Path, chrome: str) -> int:
    """Print an HTML file to PDF with headless Chrome. Returns the page count."""
    if not chrome or not Path(chrome).exists():
        raise RuntimeError("Google Chrome wasn't found, so the PDFs can't be printed. Install it, "
                           "or set chrome_path in config.json to where chrome lives.")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--no-first-run", "--no-default-browser-check",
                    f"--print-to-pdf={Path(pdf).resolve()}", Path(html).resolve().as_uri()],
                   capture_output=True, timeout=120)
    if not Path(pdf).exists():
        raise RuntimeError(f"Chrome didn't produce {Path(pdf).name}. Check chrome_path in config.json.")
    return pdf_pages(pdf)


def node_build(script: str, *args) -> None:
    """Run a builder. The last argument is always the file stem, so Python decides file names."""
    if not shutil.which("node"):
        raise RuntimeError("Node.js isn't installed, so the documents can't be built. Run "
                           "tools/setup-wizard.py; it tells you how to install it.")
    if not (TOOLS / "node_modules" / "docx").is_dir():
        raise RuntimeError("The docx package isn't installed. In the tools folder, run: npm install")
    r = subprocess.run(["node", str(TOOLS / script), *map(str, args)], cwd=TOOLS,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{script} failed: {(r.stderr or r.stdout).strip()[-400:]}")


def build_resume(md: Path, out_dir: Path, chrome: str, stem: str) -> int:
    """resume .md -> <stem>-Resume.docx/.html/.pdf in out_dir. Returns the PDF's page count."""
    node_build("build-resume.js", md, out_dir, stem)
    return to_pdf(out_dir / f"{stem}-Resume.html", out_dir / f"{stem}-Resume.pdf", chrome)


def build_letter(md: Path, master: Path, out_dir: Path, chrome: str, stem: str) -> int:
    """cover letter .md -> <stem>-Cover-Letter.docx/.html/.pdf. Returns the PDF's page count."""
    node_build("build-letter.js", md, master, out_dir, stem)
    return to_pdf(out_dir / f"{stem}-Cover-Letter.html", out_dir / f"{stem}-Cover-Letter.pdf", chrome)
