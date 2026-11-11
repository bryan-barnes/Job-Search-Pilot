"""Settings (config.json), your files, the Worker, and the agent runners. Shared by every tool.

Three runners (config.json -> agent.runner):
  "opencode"  the OpenCode CLI, with whatever provider/model you've configured for it
  "claude"    the Claude Code CLI, logged in with your Claude account (subscription works)
  "manual"    no CLI: writes the prompt to RUN-THIS.md so you can paste it into Claude,
              ChatGPT, or any other assistant, then paste the reply back into the board

The agent only ever runs with the packet folder (or a scratch dir) as its working directory,
and the prompts tell it to work only there. Nothing here talks to an LLM API directly.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
CONFIG = HOME / "config.json"
TEMPLATES = HOME / "templates"
RUNNERS = ("opencode", "claude", "manual")
# The files the agent writes in a packet.
WRITES = ("resume.md", "cover-letter.md", "answers.md", "fit-check.md")

# Your own files (gitignored) and the template each one starts from.
PERSONAL = {
    "about-me.md": "about-me.md",
    "applicant-profile.md": "applicant-profile.md",
    "canned-answers.md": "canned-answers.md",
    "experience-bank.md": "experience-bank.md",
    "inbox.md": "inbox.md",
    "jobs.js": "jobs.js",
    "resume/master.md": "master.md",
}


def ensure_personal_files() -> list[str]:
    """Create any of your files that don't exist yet from templates/. Never overwrites.
    Returns the ones it created."""
    made = []
    elsewhere = False  # resume_master points outside resume/master.md: don't make a placeholder
    try:
        master = json.loads(CONFIG.read_text(encoding="utf-8")).get("resume_master")
        elsewhere = bool(master) and (HOME / Path(master).expanduser()).resolve() != (HOME / "resume/master.md").resolve()
    except (OSError, ValueError):
        pass
    for rel, tpl in PERSONAL.items():
        if rel == "resume/master.md" and elsewhere:
            continue
        dest = HOME / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATES / tpl, dest)
            made.append(rel)
    if not CONFIG.exists():
        cfg = json.loads((HOME / "config.example.json").read_text(encoding="utf-8"))
        cfg["chrome_path"] = find_chrome() or cfg.get("chrome_path")
        CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        made.append("config.json")
    return made


def load_config() -> dict:
    ensure_personal_files()
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except ValueError as exc:
        sys.exit(f"config.json isn't valid JSON ({exc}). Fix it, or delete it and run "
                 "tools/setup-wizard.py to make a new one.")
    runner = cfg.get("agent", {}).get("runner", "manual")
    if runner not in RUNNERS:
        sys.exit(f"config.json: agent.runner must be one of {RUNNERS} (got {runner!r}).")
    if not cfg.get("chrome_path") or not Path(cfg["chrome_path"]).exists():
        cfg["chrome_path"] = find_chrome() or cfg.get("chrome_path") or ""
    return cfg


def runner_name(cfg: dict) -> str:
    return cfg.get("agent", {}).get("runner", "manual")


# ---------- Chrome (prints the PDFs) ----------

def chrome_candidates() -> list[str]:
    if sys.platform == "win32":
        out = []
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                out.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))
        return out
    if sys.platform == "darwin":
        return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    return [p for p in (shutil.which(n) for n in ("google-chrome", "google-chrome-stable",
                                                  "chromium", "chromium-browser")) if p]


def find_chrome() -> str | None:
    return next((c for c in chrome_candidates() if Path(c).exists()), None)


# ---------- the LinkedIn alerts Worker ----------

def alerts_configured(cfg: dict) -> bool:
    url = str(cfg.get("worker_url") or "")
    return url.startswith("http") and "YOUR-" not in url.upper()


def worker_token(cfg: dict, required: bool = True) -> str | None:
    """The job-alerts Worker's read key. From config.json's worker_token, else (on a Mac) the
    Keychain, service job-alerts-worker."""
    tok = str(cfg.get("worker_token", "") or "").strip()
    if tok and "YOUR-" not in tok.upper():
        return tok
    if sys.platform == "darwin":
        out = subprocess.run(
            ["security", "find-generic-password", "-s", "job-alerts-worker", "-w"],
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    if not required:
        return None
    sys.exit("No Worker key. Run tools/setup-wizard.py, or put it in config.json as "
             "worker_token (on a Mac it can live in the Keychain instead, service "
             "job-alerts-worker). See docs/linkedin-alerts.md.")


def worker_get(cfg: dict, path: str, params: dict | None = None, token: str | None = None) -> bytes:
    token = token or worker_token(cfg)
    base = str(cfg["worker_url"]).rstrip("/")
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "User-Agent": "job-alerts-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ---------- the agent runners ----------

def executable(cfg: dict) -> str | None:
    runner = runner_name(cfg)
    if runner not in ("opencode", "claude"):
        return None
    found = shutil.which(runner)
    if found:
        return found
    # A board started by double-click may not have the shell's full PATH; try the usual homes.
    names = [runner + ext for ext in ((".cmd", ".exe") if sys.platform == "win32" else ("",))]
    dirs = [Path.home() / ".local/bin", Path.home() / ".opencode/bin", Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"), Path(os.environ.get("APPDATA", "")) / "npm"]
    return next((str(d / n) for d in dirs for n in names if (d / n).is_file()), None)


def check(cfg: dict) -> str | None:
    """An error message if the configured runner can't run, else None."""
    runner = runner_name(cfg)
    if runner == "manual":
        return None
    if not executable(cfg):
        return (f"config.json says agent.runner is {runner!r}, but the {runner} CLI is not on "
                f"your PATH. Install it (see docs/agents.md) or set agent.runner to \"manual\".")
    return None


def run_prompt(cfg: dict, prompt: str, cwd: Path, log: Path, timeout: int = 1800) -> str:
    """Run the prompt through the configured agent; output goes to log.

    Returns the runner used. For "manual" it writes the prompt to cwd/RUN-THIS.md and returns
    "manual" without running anything.
    """
    runner = runner_name(cfg)
    cwd = Path(cwd)
    if runner == "manual":
        (cwd / "RUN-THIS.md").write_text(prompt, encoding="utf-8")
        return "manual"
    exe = executable(cfg)
    if not exe:
        raise RuntimeError(check(cfg) or f"{runner} CLI not found")
    # The prompt never goes on the command line: on Windows the CLIs are .cmd wrappers, and
    # cmd.exe cuts a multi-line argument off at the first line break.
    prompt_bytes = prompt.encode("utf-8")
    if runner == "opencode":
        (cwd / "PROMPT.md").write_bytes(prompt_bytes)
        # An absolute path: opencode resolves --file from its own service, not from cwd.
        cmd = [exe, "run", "--auto", "--archived", "--file", str((cwd / "PROMPT.md").resolve())]
        model = cfg.get("agent", {}).get("model")
        if model:
            cmd += ["--model", model]
        cmd.append("Follow the instructions in the attached file PROMPT.md.")
        stdin = b""
    else:  # claude reads the prompt from stdin
        cmd = [exe, "-p", "--permission-mode", "acceptEdits"]
        stdin = prompt_bytes
    try:
        with open(log, "wb") as f:
            r = subprocess.run(cmd, cwd=cwd, input=stdin,
                               stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    finally:
        (cwd / "PROMPT.md").unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"{runner} exited {r.returncode}; see {log.name}")
    return runner


def extract_json_results(text: str) -> list[dict] | None:
    """Find a JSON object with a "results" array in agent output, tolerating prose and
    markdown fences around it (one-line or pretty-printed). Returns the list, or None."""
    start = text.find("{")
    while start != -1:
        end = text.rfind("}")
        while end > start:
            try:
                data = json.loads(text[start:end + 1])
            except ValueError:
                end = text.rfind("}", start, end)
                continue
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                return data["results"]
            break
        start = text.find("{", start + 1)
    return None


MARKER = re.compile(r"^[ \t#>*_`]*@@@\s*FILE:\s*([\w.\-]+)\s*@@@[ \t*_`]*$", re.M)


def split_reply(text: str) -> dict[str, str]:
    """Split a pasted manual-mode reply into {file name: contents}, for the known file names."""
    text = text.replace("\r\n", "\n")
    marks = list(MARKER.finditer(text))
    out = {}
    for i, m in enumerate(marks):
        name = m.group(1)
        if name not in WRITES + ("NEEDS-POSTING.md",):
            continue
        body = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip()
        fence = re.fullmatch(r"```[\w-]*\n(.*?)\n```", body, re.S)  # some assistants add a code block
        out[name] = (fence.group(1) if fence else body).strip() + "\n"
    return out
