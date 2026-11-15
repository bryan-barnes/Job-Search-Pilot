"""Spot jobs that are already on the board under a slightly different title or company.

Two checks, used by ingest-alerts.py on top of its exact ones (same LinkedIn job ID, or same
company and title):

- Same company, nearly the same posting text. Employers often post one opening twice with a
  slightly different title ("Strategy Director" and "Strategy Director, Web"). Postings are
  compared as overlapping three-word phrases; two separate roles at one company share some
  boilerplate (under 0.3 in practice), the same job posted twice shares most of it (0.8+).
- A job-board reposting of a job already on the board. Sites like Jobgether post other
  employers' jobs on LinkedIn under their own name and rewrite the text, so the only match is
  the title.

Posting text is kept in alerts-postings.json (LinkedIn job ID -> company, title, text), plus the
posting.md saved in each application packet.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SIMILAR = 0.6  # share of three-word phrases two postings have in common to count as one job

# Companies whose LinkedIn listings are other employers' jobs, reposted.
AGGREGATORS = {"jobgether", "ladders", "lensa", "jobs via dice", "jooble", "talent com",
               "virtual vocations", "remotehunter", "jobright ai"}
# A repost is only skipped when the title is specific enough (4+ words besides these) that two
# employers are unlikely to share it; "Director of Marketing" gets a note instead.
FILLER = {"of", "and", "the", "for", "a", "an", "to", "in", "on", "at", "with", "remote", "us", "usa"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def is_aggregator(company: str) -> bool:
    return norm(company) in AGGREGATORS


def specific(title: str) -> bool:
    return len([w for w in norm(title).split() if w not in FILLER]) >= 4


def phrases(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}


def similarity(a: str, b: str) -> float:
    pa, pb = phrases(a), phrases(b)
    if len(pa) < 30 or len(pb) < 30:
        return 0.0  # too short to judge (a login wall or an empty description)
    return len(pa & pb) / len(pa | pb)


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def packet_text(home: Path, job_id: str) -> str:
    """The job description from a packet's posting.md, or ""."""
    try:
        text = (home / "applications" / job_id / "posting.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    return text.split("## Job description", 1)[1] if "## Job description" in text else ""


class Board:
    """The jobs to compare against: those in jobs.js, then each new one as it's accepted."""

    def __init__(self, jobs: list[dict], texts: dict, home: Path):
        # jobs: [{id, company, role, linkedin}] from jobs.js; texts: alerts-postings.json
        self.jobs = []
        for j in jobs:
            cached = texts.get(j.get("linkedin") or "", {})
            self.jobs.append({**j, "text": cached.get("text") or packet_text(home, j["id"])})

    def add(self, job_id: str, company: str, role: str, text: str) -> None:
        self.jobs.append({"id": job_id, "company": company, "role": role, "text": text})

    def duplicate_of(self, company: str, role: str, text: str) -> tuple[str, str] | None:
        """(board id, reason) if this job is already on the board, else None."""
        co, title = norm(company), norm(role)
        if is_aggregator(company) and specific(role):
            for j in self.jobs:
                if norm(j["role"]) == title and norm(j["company"]) != co:
                    return j["id"], f'{company} reposting {j["company"]}\'s "{j["role"]}"'
        if text:
            best = None
            for j in self.jobs:
                if norm(j["company"]) == co and j["text"]:
                    s = similarity(text, j["text"])
                    if s >= SIMILAR and (best is None or s > best[0]):
                        best = (s, j)
            if best:
                s, j = best
                return j["id"], f'{round(s * 100)}% the same posting text as "{j["role"]}"'
        return None

    def possible_repost(self, company: str, role: str) -> str:
        """A note when a job may be a repost of one on the board (or the reverse) but isn't
        certain enough to skip: an employer's posting whose title a job board has already
        reposted, or a job board's posting with a short, common title."""
        co, title = norm(company), norm(role)
        if is_aggregator(company):
            same = [j for j in self.jobs if norm(j["role"]) == title and norm(j["company"]) != co]
        else:
            same = [j for j in self.jobs if is_aggregator(j["company"]) and norm(j["role"]) == title]
        if not same:
            return ""
        j = same[0]
        board = company if is_aggregator(company) else j["company"]
        return (f' Possibly the same job as {j["id"]} (same title at {j["company"]});'
                f' {board} reposts other employers\' jobs.')
