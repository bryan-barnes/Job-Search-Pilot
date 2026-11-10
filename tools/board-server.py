#!/usr/bin/env python3
"""Serve the job board at http://127.0.0.1:8765/ and let its buttons save changes to jobs.js.

Usage:  python3 -I tools/board-server.py      (or double-click "Open Job Board.command")

Only listens on this Mac (127.0.0.1) and only accepts same-origin JSON posts. Serves only
tracker.html and jobs.js, plus a few files from application packets.

POST /api/update  {"id", "status"?, "remote"?, "note"?}   change a job (via jobsfile.py)
POST /api/undo    undo the last change made here, if jobs.js hasn't changed since
POST /api/prep    {"id"}  build an application packet in the background (prep-application.py)
POST /api/prep-batch {"ids": [...]}  queue several packets; PREP_PARALLEL run at a time
POST /api/build   {"id"}  build the packet's PDFs and Chrome prompt from its .md files
                       (manual mode, where the agent wrote the .md files by hand)
GET  /api/packets         status.json of every packet, plus the files it contains
POST /api/open    {"id", "file"?}  open a packet folder or file on this Mac
GET  /api/packet/<id>/<file>       read a packet's text file (e.g. apply-in-chrome.md)
POST /api/ingest          pull new LinkedIn alert jobs now (tools/ingest-alerts.py, in the background)
GET  /api/ingest          whether that's running, and the last run's result

The server also runs ingest-alerts.py on its own every few hours during the day (AUTO_* below),
so new alert emails reach the board without anyone clicking.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobsfile  # noqa: E402

PORT = 8765
HOME = jobsfile.HOME
APPS = HOME / "applications"
FILES = {"/": ("tracker.html", "text/html"), "/tracker.html": ("tracker.html", "text/html"),
         "/jobs.js": ("jobs.js", "text/javascript")}
# Packet files: any .md/.pdf/.docx in the packet, named <word>s plus optional -Resume or
# -Cover-Letter (the builders derive the base name from the master resume), plus *.log.
PACKET_RE = re.compile(r"^[\w-]+(?:-Resume|-Cover-Letter)?\.(md|pdf|docx)$|^[\w-]+\.log$")
LABEL = {"passed": "Not interested", "expired": "Posting expired before applying",
         "found": "Moved to Found", "closed": "Closed", "applied": "Applied",
         "rejected": "Not selected: they declined to move forward"}
lock = Lock()
undo_stack: list[tuple[str, str]] = []  # (text before, text after)
running: dict[str, subprocess.Popen] = {}
INGEST_LOG = HOME / "ingest.log"
AUTO_HOURS = range(8, 22)     # local time window for automatic runs
AUTO_EVERY = 3 * 3600         # seconds between automatic runs
ingest_proc: subprocess.Popen | None = None
ingest_lock = Lock()
PREP_PARALLEL = 3
prep_queue: list[str] = []


def start_ingest() -> bool:
    """Start ingest-alerts.py unless it's already running. Output goes to ingest.log."""
    global ingest_proc
    with ingest_lock:
        if ingest_proc is not None and ingest_proc.poll() is None:
            return False
        with open(INGEST_LOG, "w") as log:
            log.write(f"Started {datetime.now():%Y-%m-%d %H:%M}\n")
            log.flush()
            ingest_proc = subprocess.Popen(
                [sys.executable, "-I", str(HOME / "tools/ingest-alerts.py")],
                cwd=HOME, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        return True


def ingest_status() -> dict:
    busy = ingest_proc is not None and ingest_proc.poll() is None
    if not INGEST_LOG.exists():
        return {"running": busy, "last": None, "summary": ""}
    lines = [ln.strip() for ln in INGEST_LOG.read_text(errors="replace").splitlines() if ln.strip()]
    summary = next((ln for ln in lines if ln.startswith("Added ")), "")
    if not summary and not busy and lines:
        # No "Added" line means it stopped early (no Keychain key, network down, a crash).
        summary = "Didn't finish: " + lines[-1][:200]
    last = datetime.fromtimestamp(INGEST_LOG.stat().st_mtime).isoformat(timespec="minutes")
    m = re.match(r"Added (\d+) job\(s\).*?\((\d+) fully remote", summary)
    return {"running": busy, "last": last, "summary": summary, "ok": bool(m),
            "added": int(m.group(1)) if m else None, "remote": int(m.group(2)) if m else None}


def auto_ingest() -> None:
    """Run the ingest every AUTO_EVERY seconds during AUTO_HOURS."""
    while True:
        last = INGEST_LOG.stat().st_mtime if INGEST_LOG.exists() else 0
        if datetime.now().hour in AUTO_HOURS and time.time() - last >= AUTO_EVERY:
            start_ingest()
        time.sleep(600)


def valid_id(job_id) -> bool:
    return isinstance(job_id, str) and re.fullmatch(r"[a-z0-9-]{1,120}", job_id) is not None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if self.command == "POST":
            sys.stderr.write("%s\n" % (fmt % args))

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode())

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        if path in FILES:
            name, ctype = FILES[path]
            return self._send(200, (HOME / name).read_bytes(), ctype)
        if path == "/api/packets":
            return self._json(200, packets())
        if path == "/api/ingest":
            return self._json(200, ingest_status())
        m = re.fullmatch(r"/api/packet/([a-z0-9-]+)/([\w.-]+\.md)", path)
        if m and (APPS / m.group(1) / m.group(2)).is_file():
            return self._send(200, (APPS / m.group(1) / m.group(2)).read_bytes(), "text/plain")
        self._send(404, b"Not found", "text/plain")

    def _same_origin(self) -> bool:
        # Blocks other websites from posting to this server from your browser.
        origin = self.headers.get("Origin")
        ok_hosts = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        return (self._host_ok() and (origin is None or origin.split("//", 1)[-1] in ok_hosts)
                and self.headers.get("Content-Type", "").startswith("application/json"))

    def do_POST(self):
        if not self._same_origin():
            return self._json(403, {"error": "Forbidden"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 2))
        except ValueError:
            return self._json(400, {"error": "Bad JSON"})
        route = {"/api/update": self._update, "/api/undo": self._undo, "/api/prep": self._prep,
                 "/api/prep-batch": self._prep_batch, "/api/build": self._build,
                 "/api/open": self._open, "/api/ingest": self._ingest}.get(self.path)
        if not route:
            return self._json(404, {"error": "Not found"})
        with lock:
            route(body)

    def _update(self, body: dict):
        job_id, status, remote = body.get("id"), body.get("status"), body.get("remote")
        note = str(body.get("note") or "").strip()[:500]
        if status is not None and status not in jobsfile.STATUSES:
            return self._json(400, {"error": f"Unknown status {status!r}"})
        if remote is not None and remote not in jobsfile.REMOTE:
            return self._json(400, {"error": f"Unknown remote value {remote!r}"})
        today = date.today().isoformat()

        def change(text):
            if status:
                text = jobsfile.set_field(text, job_id, "status", status)
                if status == "applied" and not jobsfile.get(text, job_id, "applied"):
                    text = jobsfile.set_field(text, job_id, "applied", today)
            if remote:
                text = jobsfile.set_field(text, job_id, "remote", remote)
                text = jobsfile.set_field(text, job_id, "remoteChecked", today)
            label = LABEL.get(status) or {"no": "Checked: not fully remote",
                                          "yes": "Checked: fully remote"}.get(remote, "")
            if label:
                text = jobsfile.add_note(text, job_id,
                                         f"{label} ({today}){': ' + note if note else '.'}")
            return jobsfile.touch(text, today)

        try:
            with jobsfile.locked():
                before = jobsfile.read()
                text = change(before)
                jobsfile.write(text)
        except KeyError:
            return self._json(404, {"error": f"No job with id {job_id!r}"})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        undo_stack.append((before, text))
        del undo_stack[:-20]
        self._json(200, {"ok": True, "notes": jobsfile.get(text, job_id, "notes"),
                         "applied": jobsfile.get(text, job_id, "applied"),
                         "remoteChecked": jobsfile.get(text, job_id, "remoteChecked")})

    def _undo(self, _body):
        if not undo_stack:
            return self._json(409, {"error": "Nothing to undo"})
        before, after = undo_stack[-1]
        with jobsfile.locked():
            if jobsfile.read() != after:
                undo_stack.clear()
                return self._json(409, {"error": "jobs.js changed since then; reload the page"})
            undo_stack.pop()
            jobsfile.write(before)
        self._json(200, {"ok": True})

    def _prep(self, body: dict):
        err = prep_problem(body.get("id"))
        if err:
            return self._json(err[0], {"error": err[1]})
        start_prep(body["id"])
        undo_stack.clear()  # a packet build isn't something Undo should silently reverse
        self._json(200, {"ok": True})

    def _prep_batch(self, body: dict):
        ids = body.get("ids")
        if not isinstance(ids, list) or not ids or len(ids) > 40:
            return self._json(400, {"error": "Send 1 to 40 job ids"})
        queued, skipped = [], []
        for job_id in ids:
            err = prep_problem(job_id)
            if err:
                skipped.append({"id": str(job_id)[:120], "why": err[1]})
                continue
            mark_applying(job_id)
            write_status(job_id, "queued", "Waiting in line")
            prep_queue.append(job_id)
            queued.append(job_id)
        undo_stack.clear()
        self._json(200, {"ok": True, "queued": queued, "skipped": skipped})

    def _ingest(self, _body):
        if not start_ingest():
            return self._json(409, {"error": "Already checking for new jobs"})
        self._json(200, {"ok": True})

    def _build(self, body: dict):
        job_id = body.get("id")
        if not valid_id(job_id) or not (APPS / job_id).is_dir():
            return self._json(404, {"error": "No packet for that job yet"})
        if job_id in running and running[job_id].poll() is None:
            return self._json(409, {"error": "Already building this one"})
        missing = [n for n in ("resume.md", "cover-letter.md", "answers.md")
                   if not (APPS / job_id / n).is_file()]
        if missing:
            return self._json(400, {"error": "Missing " + ", ".join(missing)
                                    + "; follow RUN-THIS.md and get them written first"})
        write_status(job_id, "running", "Building documents")
        with open(APPS / job_id / "build.log", "w") as log:
            running[job_id] = subprocess.Popen(
                [sys.executable, "-I", str(HOME / "tools/prep-application.py"), job_id, "--build-only"],
                cwd=HOME, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self._json(200, {"ok": True})

    def _open(self, body: dict):
        job_id, name = body.get("id"), body.get("file")
        if not valid_id(job_id) or not (APPS / job_id).is_dir():
            return self._json(404, {"error": "No packet for that job yet"})
        target = APPS / job_id
        if name:
            if not PACKET_RE.match(name) or not (target / name).is_file():
                return self._json(404, {"error": f"{name} isn't in the packet"})
            target = target / name
        if sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            subprocess.run(["open", str(target)], check=False)
        self._json(200, {"ok": True})


def prep_problem(job_id) -> tuple[int, str] | None:
    if not valid_id(job_id) or job_id not in jobsfile.ids(jobsfile.read()):
        return 404, "No such job"
    if (job_id in running and running[job_id].poll() is None) or job_id in prep_queue:
        return 409, "Already preparing this one"
    return None


def write_status(job_id: str, state: str, step: str) -> None:
    (APPS / job_id).mkdir(parents=True, exist_ok=True)
    (APPS / job_id / "status.json").write_text(json.dumps(
        {"state": state, "step": step, "updated": datetime.now().isoformat(timespec="seconds")}))


def mark_applying(job_id: str) -> None:
    def change(text):
        if jobsfile.get(text, job_id, "status") in {"new", "found"}:
            text = jobsfile.set_field(text, job_id, "status", "applying")
        return jobsfile.touch(text, date.today().isoformat())
    jobsfile.update(change)


def start_prep(job_id: str) -> None:
    """Run prep-application.py for one job in the background. Call with `lock` held."""
    mark_applying(job_id)
    write_status(job_id, "running", "Starting")
    with open(APPS / job_id / "prep.log", "w") as log:
        running[job_id] = subprocess.Popen(
            [sys.executable, "-I", str(HOME / "tools/prep-application.py"), job_id],
            cwd=HOME, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def run_prep_queue() -> None:
    """Start queued packets, PREP_PARALLEL at a time."""
    while True:
        time.sleep(3)
        with lock:
            busy = sum(p.poll() is None for p in running.values())
            while prep_queue and busy < PREP_PARALLEL:
                start_prep(prep_queue.pop(0))
                busy += 1


def packets() -> dict:
    out = {}
    for f in APPS.glob("*/status.json"):
        try:
            data = json.loads(f.read_text())
        except ValueError:
            continue
        job_id = f.parent.name
        proc = running.get(job_id)
        if data.get("state") == "running" and (proc is None or proc.poll() is not None):
            # The prep process ended without reporting (crash or server restart).
            if proc is not None or data.get("step") == "Starting":
                data = {**data, "state": "failed", "step": "Stopped unexpectedly; see prep.log"}
        if data.get("state") == "queued" and job_id not in prep_queue:
            data = {**data, "state": "failed", "step": "The board restarted before this one ran; click Try again"}
        data["files"] = sorted(x.name for x in f.parent.iterdir()
                               if x.is_file() and x.suffix in (".md", ".pdf", ".docx"))
        out[job_id] = data
    return out


def main() -> None:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        sys.exit(f"Port {PORT} is busy. The board may already be running: http://127.0.0.1:{PORT}/")
    print(f"Job board: http://127.0.0.1:{PORT}/  (Ctrl+C to stop)", flush=True)
    threading.Thread(target=auto_ingest, daemon=True).start()
    threading.Thread(target=run_prep_queue, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
