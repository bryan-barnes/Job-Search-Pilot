"""Small, careful edits to jobs.js, shared by the board server, ingest-alerts.py, and prep.

jobs.js keeps one job per block, written like this (2-space block indent, 4-space fields,
one field per line, values are JSON strings or numbers):

  {
    id: "some-job",
    status: "new",
    ...
  },

These helpers find a block by id and change single fields in place, so hand-written notes and
field order survive. They never rewrite the whole file from parsed data.

Works on macOS, Linux, and Windows. All files are read and written as UTF-8.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
JOBS = HOME / "jobs.js"

STATUSES = {"new", "found", "applying", "applied", "screen", "interview", "offer",
            "rejected", "closed", "passed", "expired"}
REMOTE = {"yes", "no", "unknown"}


def utf8_stdio() -> None:
    """Print UTF-8 even where the console or a redirected log defaults to something else
    (Windows). Call once at the start of each script."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


@contextmanager
def locked():
    """Hold an exclusive lock while reading, changing, and writing jobs.js."""
    with open(HOME / ".jobs.lock", "a+", encoding="utf-8") as fh:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)


def update(change) -> str:
    """Apply change(text) -> text under the lock and write the result. Returns the new text."""
    with locked():
        text = change(read())
        write(text)
        return text


def read() -> str:
    return JOBS.read_text(encoding="utf-8")


def write(text: str) -> None:
    """Atomic replace, so the browser or another script never sees a half-written file."""
    fd, tmp = tempfile.mkstemp(dir=JOBS.parent, prefix=".jobs-", suffix=".js")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    for attempt in range(20):
        try:
            os.replace(tmp, JOBS)
            return
        except PermissionError:  # Windows: another process has jobs.js open for a moment
            if attempt == 19:
                raise
            time.sleep(0.1)


def _span(text: str, job_id: str) -> tuple[int, int]:
    m = re.search(r"^    id:\s*" + re.escape(json.dumps(job_id)) + r",\s*$", text, re.M)
    if not m:
        raise KeyError(job_id)
    start = text.rfind("\n  {", 0, m.start()) + 1
    end = text.find("\n  },", m.end())
    if start <= 0 or end == -1:
        raise ValueError(f"Block for {job_id} is not in the expected format")
    return start, end + len("\n  },")


def ids(text: str) -> list[str]:
    return re.findall(r'^    id:\s*"([^"]+)",\s*$', text, re.M)


def get(text: str, job_id: str, key: str):
    s, e = _span(text, job_id)
    m = re.search(rf"^    {re.escape(key)}:\s*(.*?),\s*$", text[s:e], re.M)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return m.group(1)


def set_field(text: str, job_id: str, key: str, value) -> str:
    """Set (or with value None, remove) one field in one job's block."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        raise ValueError(f"Bad field name {key!r}")
    s, e = _span(text, job_id)
    block = text[s:e]
    pat = re.compile(rf"^    {re.escape(key)}:.*,[ \t]*\n", re.M)
    line = "" if value is None else f"    {key}: {json.dumps(value, ensure_ascii=False)},\n"
    if pat.search(block):
        block = pat.sub(lambda _: line, block, count=1)
    elif line:
        # New fields go just before `added:` if present, else at the end of the block.
        m = re.search(r"^    added:", block, re.M)
        at = m.start() if m else block.rfind("  },")
        block = block[:at] + line + block[at:]
    return text[:s] + block + text[e:]


def add_note(text: str, job_id: str, note: str) -> str:
    old = get(text, job_id, "notes")
    old = old if isinstance(old, str) else ""
    return set_field(text, job_id, "notes", (old.rstrip() + " " + note).strip())


def touch(text: str, today: str) -> str:
    return re.sub(r'window\.JOBS_UPDATED = "[^"]*";', f'window.JOBS_UPDATED = "{today}";', text)


def ascii_fold(s: str) -> str:
    """'Zoë Coöp' -> 'Zoe Coop' (drops accents; other non-ASCII letters are removed later)."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ascii_fold(s).lower()).strip("-")[:60]


def unique_id(text: str, base: str, suffix: str = "") -> str:
    """A job id not already used in jobs.js: base, else base-<suffix>, else base-2, -3, ..."""
    taken = set(re.findall(r'\bid:\s*"([^"]+)"', text))
    base = base or "job"
    if base not in taken:
        return base
    if suffix and f"{base}-{suffix}" not in taken:
        return f"{base}-{suffix}"
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def add_job(text: str, fields: dict) -> str:
    """Append one job block (fields in the given order, `id` first) before the closing `];`."""
    if "id" not in fields:
        raise ValueError("A job needs an id")
    lines = []
    for k, v in [("id", fields["id"])] + [(k, v) for k, v in fields.items() if k != "id"]:
        if v is None or v == "":
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
            raise ValueError(f"Bad field name {k!r}")
        lines.append(f"    {k}: {json.dumps(v, ensure_ascii=False)},")
    block = "  {\n" + "\n".join(lines) + "\n  },\n"
    m = re.search(r"^\];", text, re.M)
    if not m:
        raise ValueError("Could not find the end of window.JOBS (a line starting with `];`) "
                         "in jobs.js")
    return text[:m.start()] + block + text[m.start():]
