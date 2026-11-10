"""Small, careful edits to jobs.js, shared by the board server and ingest-alerts.py.

jobs.js keeps one job per block, written like this (2-space block indent, 4-space fields,
one field per line, values are JSON strings or numbers):

  {
    id: "some-job",
    status: "new",
    ...
  },

These helpers find a block by id and change single fields in place, so hand-written notes and
field order survive. They never rewrite the whole file from parsed data.
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
import re
import tempfile
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
JOBS = HOME / "jobs.js"

STATUSES = {"new", "found", "applying", "applied", "screen", "interview", "offer",
            "rejected", "closed", "passed", "expired"}
REMOTE = {"yes", "no", "unknown"}


@contextmanager
def locked():
    """Hold an exclusive lock while reading, changing, and writing jobs.js."""
    with open(HOME / ".jobs.lock", "w") as fh:
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
    return JOBS.read_text()


def write(text: str) -> None:
    """Atomic replace, so the browser or another script never sees a half-written file."""
    fd, tmp = tempfile.mkstemp(dir=JOBS.parent, prefix=".jobs-", suffix=".js")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, JOBS)


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
