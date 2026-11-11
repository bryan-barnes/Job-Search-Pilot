#!/usr/bin/env python3
"""End-to-end smoke test for a fresh checkout: setup, the board's API, a manual-mode packet,
and the PDF build. Runs on macOS, Windows, and Linux (CI runs it on all three).

Usage:  python3 tests/smoke.py [checkout-dir]

It works on a COPY of the checkout in a temp folder, so your own files are never touched.
Needs Node.js, Google Chrome, and `npm install` done in tools/ (the copy reuses node_modules).
No network access needed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
PY = [sys.executable, "-X", "utf8"]
ROLE = "Directeur · Numérique – Stratégie ✓"  # non-ASCII on purpose: Windows code pages


def step(msg: str) -> None:
    print(f"\n== {msg}", flush=True)


def check(cond, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {msg}")
    print(f"   ok: {msg}", flush=True)


def call(path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers.get_content_type() == "application/json" else raw)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def wait_packet(job_id: str, states: set, timeout: int = 180) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        pk = call("/api/packets")[1].get(job_id, {})
        if pk.get("state") in states:
            return pk
        time.sleep(1)
    raise SystemExit(f"FAIL: packet {job_id} never reached {states}; last: {pk}")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="pilot-smoke-"))
    root = tmp / "pilot"
    personal = {"applications", "config.json", "jobs.js", "about-me.md", "inbox.md", "strengths",
                "applicant-profile.md", "canned-answers.md", "experience-bank.md", "alerts-state.json",
                "alerts-scores.json", "ingest.log", "board.log", ".git", ".jobs.lock"}

    def skip(folder: str, names: list[str]) -> set:
        here = Path(folder).resolve()
        if here == SRC:
            return personal & set(names)
        if here == SRC / "resume":
            return {n for n in names if n == "master.md" or n.endswith((".pdf", ".docx"))}
        return {n for n in names if n == "__pycache__"}
    shutil.copytree(SRC, root, ignore=skip)
    env = {**os.environ, "JOB_BOARD_PORT": str(PORT)}
    server = None
    try:
        step("Board server")
        server = subprocess.Popen(PY + ["-I", str(root / "tools/board-server.py")], cwd=root, env=env)
        for _ in range(60):
            try:
                call("/api/info")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        code, info = call("/api/info")
        check(code == 200 and info["alerts"] is False, "board answers; alerts not configured")
        code, page = call("/")
        check(code == 200 and b"Job Search Pilot" in page, "board page served")

        step("Setup wizard (--yes)")
        r = subprocess.run(PY + [str(root / "tools/setup-wizard.py"), "--yes"], cwd=root, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=300,
                           input="")
        print(r.stdout[-1500:], r.stderr[-1500:])
        check(r.returncode == 0, "wizard finished")
        for f in ("about-me.md", "jobs.js", "resume/master.md", "config.json", "applicant-profile.md"):
            check((root / f).exists(), f"created {f}")
        cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
        cfg["agent"]["runner"] = "manual"
        (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        step("Resume build")
        master = root / "resume/master.md"
        master.write_text(master.read_text(encoding="utf-8").replace("# Your Name", "# Zoë Q. Example", 1),
                          encoding="utf-8")
        r = subprocess.run(PY + [str(root / "tools/rebuild-resume.py")], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
        print(r.stdout, r.stderr)
        check(r.returncode == 0 and "Pages: 1" in r.stdout, "master resume builds to one page")
        check((root / "resume/Zoe-Q-Example-Resume.pdf").exists(), "PDF named after the resume")

        step("Add job, scores, stages")
        code, res = call("/api/add", {"company": "Ácme Coöp", "role": ROLE, "remote": "yes",
                                      "pay": "$150K–$170K", "notes": "smoke test"})
        check(code == 200, f"added job {res}")
        jid = res["id"]
        code, _ = call("/api/add", {"company": "Ácme Coöp", "role": ROLE, "remote": "yes"})
        check(code == 200, "same company+role gets a second, unique id")
        code, res = call("/api/update", {"id": jid, "fit": 4, "co": 5, "like": 3})
        check(code == 200, "scores saved")
        code, _ = call("/api/update", {"id": jid, "fit": 9})
        check(code == 400, "bad score refused")
        code, info = call("/api/info")
        check(jid in info["editable"], "new job is editable")
        jobs = (root / "jobs.js").read_text(encoding="utf-8")
        check(ROLE in jobs and "fit: 4," in jobs and 'remoteChecked: "' in jobs, "jobs.js has it, UTF-8 intact")
        r = subprocess.run(["node", "-e", f"const window={{}}; eval(require('fs').readFileSync({json.dumps(str(root / 'jobs.js'))},'utf8')); "
                            "if (window.JOBS.length !== 2) process.exit(1)"], capture_output=True, text=True)
        check(r.returncode == 0, f"jobs.js is still valid JavaScript {r.stderr}")
        code, _ = call("/api/update", {"id": jid, "status": "applied"})
        code2, _ = call("/api/undo", {})
        check(code == 200 and code2 == 200 and 'status: "found"' in (root / "jobs.js").read_text(encoding="utf-8"),
              "mark applied, then undo")

        step("Manual-mode packet")
        code, _ = call("/api/prep", {"id": jid})
        check(code == 200, "prep started")
        pk = wait_packet(jid, {"manual", "failed"})
        check(pk["state"] == "manual", f"packet waits for the reply ({pk.get('step')})")
        prompt = (root / "applications" / jid / "RUN-THIS.md").read_text(encoding="utf-8")
        check("@@@ FILE: ../../about-me.md @@@" in prompt and "@@@ FILE: posting.md @@@" in prompt,
              "RUN-THIS.md includes the source files")
        code, res = call("/api/reply", {"id": jid, "text": "only part of it\n@@@ FILE: resume.md @@@\n# X\n"})
        check(code == 400 and "cover-letter.md" in res["error"], "partial reply refused with a reason")
        resume = master.read_text(encoding="utf-8")
        reply = ("Here you go!\n\n**@@@ FILE: resume.md @@@**\n\n" + resume +
                 "\n@@@ FILE: cover-letter.md @@@\n```markdown\nDear Hiring Team,\n\nI'd like the "
                 f"{ROLE} role.\n\nSincerely,\nZoë Q. Example\n```\n"
                 "@@@ FILE: answers.md @@@\nSingle number for forms: $160,000\n"
                 "@@@ FILE: fit-check.md @@@\nFit 4/5. Base: core.\n")
        code, res = call("/api/reply", {"id": jid, "text": reply})
        check(code == 200, f"reply saved {res}")
        pk = wait_packet(jid, {"ready", "failed"})
        print("   build:", pk)
        check(pk["state"] == "ready" and pk.get("pages") == {"resume": 1, "letter": 1}, "PDFs built, one page each")
        files = set(pk["files"])
        for f in ("Zoe-Q-Example-Resume.pdf", "Zoe-Q-Example-Cover-Letter.pdf", "apply-in-chrome.md",
                  "Zoe-Q-Example-Resume.docx"):
            check(f in files, f"packet has {f}")
        letter = (root / "applications" / jid / "cover-letter.md").read_text(encoding="utf-8")
        check(letter.startswith("Dear Hiring Team") and "```" not in letter, "code fence stripped from the letter")
        code, txt = call(f"/api/packet/{jid}/apply-in-chrome.md")
        check(code == 200 and "Zoë" in txt.decode("utf-8"), "Chrome prompt served as UTF-8")

        step("Ingest without alerts set up")
        r = subprocess.run(PY + ["-I", str(root / "tools/ingest-alerts.py")], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        print(r.stdout[-600:], r.stderr[-600:])
        check(r.returncode == 0 and "Alerts not set up" in r.stdout, "ingest runs the re-check only")

        step("Security")
        req = urllib.request.Request(BASE + "/api/update", method="POST",
                                     data=json.dumps({"id": jid, "status": "passed"}).encode(),
                                     headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
        try:
            urllib.request.urlopen(req, timeout=10)
            check(False, "cross-site post refused")
        except urllib.error.HTTPError as exc:
            check(exc.code == 403, "cross-site post refused")
        print("\nALL PASSED")
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
