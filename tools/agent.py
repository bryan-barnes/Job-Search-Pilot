"""Settings (config.json), your files, the Worker, and the agent runners. Shared by every tool.

Four runners (config.json -> agent.runner; the board's Settings screen changes it):
  "manual"    no CLI: writes the prompt to RUN-THIS.md so you can paste it into Claude,
              ChatGPT, or any other assistant, then paste the reply back into the board
  "claude"    the Claude Code CLI, logged in with your Claude account (subscription works)
  "codex"     OpenAI's Codex CLI, logged in with your ChatGPT account or an OpenAI API key
  "opencode"  the OpenCode CLI, with whatever provider/model you've configured for it,
              including local models

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
RUNNERS = ("manual", "claude", "codex", "opencode")
CLI_RUNNERS = ("claude", "codex", "opencode")
# Shown by the board's Settings screen and the setup wizard.
RUNNER_INFO = {
    "manual": ("Copy and paste", "Any AI chat: ChatGPT, Claude, Gemini, Copilot. The board gives you "
               "a prompt to paste in, and you paste the reply back. Nothing to install."),
    "claude": ("Claude Code", "Writes the packets for you with your Claude subscription. Needs the "
               "Claude Code CLI."),
    "codex": ("Codex (ChatGPT / GPT)", "Writes the packets for you with your ChatGPT subscription or "
              "an OpenAI API key. Needs OpenAI's Codex CLI."),
    "opencode": ("OpenCode", "Writes the packets for you with any provider you've set up in "
                 "OpenCode, including a model running on your own computer."),
}
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


def model_name(cfg: dict) -> str | None:
    return cfg.get("agent", {}).get("model") or None


def save_config(cfg: dict) -> None:
    """Write config.json atomically (the board server and the tools read it at any time)."""
    tmp = CONFIG.with_name(CONFIG.name + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, CONFIG)


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
    if runner not in CLI_RUNNERS:
        return None
    found = shutil.which(runner)
    if found:
        return found
    # A board started by double-click may not have the shell's full PATH; try the usual homes.
    names = [runner + ext for ext in ((".cmd", ".exe") if sys.platform == "win32" else ("",))]
    dirs = [Path.home() / ".local/bin", Path.home() / ".opencode/bin", Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"), Path.home() / ".npm-global/bin",
            Path(os.environ.get("APPDATA", "")) / "npm"]
    return next((str(d / n) for d in dirs for n in names if (d / n).is_file()), None)


def check(cfg: dict) -> str | None:
    """An error message if the configured runner can't run, else None."""
    runner = runner_name(cfg)
    if runner == "manual":
        return None
    if not executable(cfg):
        return (f"Your settings say {RUNNER_INFO.get(runner, (runner,))[0]} writes your packets, but "
                f"the {runner} CLI isn't installed on this computer (or isn't on your PATH). Install "
                f"it (see docs/agents.md), or pick another AI under Settings on the board.")
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
    model = model_name(cfg)
    transcript = None
    if runner == "opencode":
        (cwd / "PROMPT.md").write_bytes(prompt_bytes)
        # An absolute path: opencode resolves --file from its own service, not from cwd.
        cmd = [exe, "run", "--auto", "--archived", "--file", str((cwd / "PROMPT.md").resolve())]
        if model:
            cmd += ["--model", model]
        cmd.append("Follow the instructions in the attached file PROMPT.md.")
        stdin = b""
    elif runner == "codex":
        # workspace-write: it may edit files only in the working folder. Its transcript echoes the
        # prompt (and the prompt's JSON examples), so the log gets only its final message (-o)
        # and the transcript goes to a second file.
        last = cwd / ".codex-last.txt"
        last.unlink(missing_ok=True)
        transcript = log.with_name(log.stem + "-codex" + log.suffix)
        cmd = [exe, "exec", "--sandbox", "workspace-write", "--skip-git-repo-check", "--ephemeral",
               "--color", "never", "--output-last-message", str(last.resolve())]
        if model:
            cmd += ["--model", model]
        cmd.append("-")  # the prompt comes from stdin
        stdin = prompt_bytes
    else:  # claude reads the prompt from stdin
        cmd = [exe, "-p", "--permission-mode", "acceptEdits"]
        if model:
            cmd += ["--model", model]
        stdin = prompt_bytes
    try:
        with open(transcript or log, "wb") as f:
            r = subprocess.run(cmd, cwd=cwd, input=stdin,
                               stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    finally:
        (cwd / "PROMPT.md").unlink(missing_ok=True)
        if transcript:
            last = cwd / ".codex-last.txt"
            log.write_bytes(last.read_bytes() if last.is_file() else b"")
            last.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"{runner} exited {r.returncode}; see {(transcript or log).name}")
    return runner


TEST_PROMPT = ("This is a connection test from Job Search Pilot. Don't read, write, or run anything. "
               "Reply with the sum of 19 and 23, as digits only.")


def test_runner(cfg: dict, timeout: int = 240) -> dict:
    """Send a tiny prompt through the configured runner. Returns {ok, message, output}."""
    import tempfile
    import time
    runner = runner_name(cfg)
    if runner == "manual":
        return {"ok": True, "message": "Copy and paste needs nothing installed.", "output": ""}
    problem = check(cfg)
    if problem:
        return {"ok": False, "message": problem, "output": ""}
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "test.log"
        try:
            run_prompt(cfg, TEST_PROMPT, cwd=Path(tmp), log=log, timeout=timeout)
            err = None
        except subprocess.TimeoutExpired:
            err = f"No answer after {timeout // 60} minutes."
        except (RuntimeError, OSError) as exc:
            err = str(exc)
        answer = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        out = "".join(f.read_text(encoding="utf-8", errors="replace")
                      for f in sorted(Path(tmp).glob("*.log")))
    secs = round(time.monotonic() - t0)
    out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out).strip()
    if err:
        if re.search(r"401|unauthori[sz]ed|not (logged|signed) in|log ?in|api key|credential", out, re.I):
            err = (f"It isn't signed in yet. Open a terminal, run {runner} once, and sign in. "
                   "Then test again.")
        elif "exited" in err:
            err = f"{RUNNER_INFO[runner][0]} ran but stopped with an error. See what it printed below."
        return {"ok": False, "message": err, "output": out[-1500:]}
    if not re.search(r"(?<!\d)42(?!\d)", answer):
        return {"ok": False, "message": f"It ran ({secs}s) but didn't answer the test question. "
                "Check that you're logged in and the model name is right.", "output": out[-1500:]}
    return {"ok": True, "message": f"Working: it answered in {secs} seconds.", "output": out[-600:]}


def opencode_models(cfg: dict) -> list[str]:
    """The provider/model IDs OpenCode knows about (for the Settings screen), or []."""
    exe = executable({"agent": {"runner": "opencode"}})
    if not exe:
        return []
    try:
        r = subprocess.run([exe, "models"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [ln.strip() for ln in r.stdout.splitlines() if re.fullmatch(r"[\w.@:-]+/[\w./@:-]+", ln.strip())]


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
