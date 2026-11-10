#!/usr/bin/env python3
"""Job Search Pilot setup wizard.

Walks you through every setup step, in order, in plain language, on Mac or Windows:

  1. checks the tools you need (and tells you exactly how to install any that are missing)
  2. installs the one Node dependency
  3. creates config.json (which AI runner, Chrome, the LinkedIn alerts settings)
  4. stores your Worker key (Keychain on Mac, config.json on Windows)
  5. walks you through the files you need to fill in
  6. tests that your resume builds to a one-page PDF
  7. opens the job board
  8. optionally walks you through the LinkedIn alerts setup and tests it

Usage:  python3 tools/setup-wizard.py          (or: python tools\\setup-wizard.py on Windows)
        python3 tools/setup-wizard.py --yes    (answer every question with the default)

Nothing here is sent anywhere except to your own Cloudflare account and your chosen AI
provider when you run the tools later. Everything stays in this folder on this computer.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
TOOLS = HOME / "tools"
IS_WIN = sys.platform == "win32"
AUTO_YES = "--yes" in sys.argv


# ---------- small helpers ----------

def banner(title: str) -> None:
    print(f"\n{'=' * 62}\n{title}\n{'=' * 62}")


def say(msg: str) -> None:
    print(msg)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    if AUTO_YES:
        return default
    try:
        val = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return val or default


def yn(prompt: str, default: bool = True) -> bool:
    mark = "Y/n" if default else "y/N"
    if AUTO_YES:
        return default
    try:
        val = input(f"{prompt} ({mark}): ").strip().lower()
    except EOFError:
        return default
    if not val:
        return default
    return val in ("y", "yes")


def have(cmd: str) -> str | None:
    return shutil.which(cmd)


def open_in_default_app(p: Path) -> None:
    if IS_WIN:
        import os
        os.startfile(str(p))  # type: ignore[attr-defined]
    else:
        subprocess.run(["open", str(p)], check=False)


def run_quiet(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---------- 1. tools ----------

def chrome_path() -> str | None:
    if IS_WIN:
        for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
            if Path(c).exists():
                return c
    else:
        c = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if c.exists():
            return str(c)
    return None


def check_tools() -> dict:
    """Returns {name: (have_it, install_instruction)} for the tools we need."""
    tools = {}
    py = sys.executable
    tools["Python 3"] = (True, "")
    tools["Node.js"] = (have("node") is not None,
                        "winget install OpenJS.NodeJS.LTS" if IS_WIN else "brew install node")
    tools["Google Chrome"] = (chrome_path() is not None,
                              "download it from google.com/chrome and run the installer")
    tools["pdfinfo (poppler)"] = (have("pdfinfo") is not None,
                                  "winget install oschwartz10612.Poppler" if IS_WIN
                                  else "brew install poppler")
    return tools


def install_step() -> dict:
    banner("1. The tools we need")
    say("We need Python (you're running it now), Node.js, Google Chrome, and a small tool\n"
        "called pdfinfo. Let's check what you have.")
    tools = check_tools()
    missing = [n for n, (ok, _) in tools.items() if not ok]
    for name, (ok, how) in tools.items():
        say(f"  {'ok      ' if ok else 'MISSING '} {name}")
    while missing and yn(f"\nInstall the missing ones? (I'll tell you how, then re-check)", True):
        for name in missing:
            _, how = tools[name]
            say(f"\n  {name}: run this in a terminal, then close this wizard and start it again\n"
                f"  once it's done:\n\n    {how}\n")
        say("\n(If you'd rather keep going now, answer no and we'll skip the steps that need\n"
            "the missing tools.)")
        if AUTO_YES:
            break
        time.sleep(0.3)
        tools = check_tools()
        missing = [n for n, (ok, _) in tools.items() if not ok]
        say(f"\nRe-checking... {len(missing)} still missing." if missing else "\nAll present. Nice.")
    if missing:
        say(f"\nContinuing without: {', '.join(missing)}. The board works fine; the steps that\n"
            f"need these (building PDFs) will be skipped and can be done later.")
    return tools


# ---------- 2. node dependency ----------

def npm_step() -> None:
    banner("2. The one Node dependency")
    if not have("node"):
        say("Node.js isn't installed, so we'll skip this. Come back to the wizard after\n"
            "installing it (step 1).")
        return
    if (TOOLS / "node_modules").is_dir():
        say("Already installed. Nothing to do.")
        return
    if not yn("Install the docx package now? (runs: npm install, in the tools folder)", True):
        say("Skipped. Run it later:  cd tools && npm install")
        return
    say("Installing... (one minute)")
    r = run_quiet(["npm", "install"], cwd=TOOLS)
    if r.returncode == 0 and (TOOLS / "node_modules").is_dir():
        say("Done.")
    else:
        say(f"npm install failed: {r.stderr.strip()[:300]}\nRun it by hand later:  cd tools && npm install")


# ---------- 3. config ----------

def runners_available() -> list[str]:
    out = []
    if have("opencode"):
        out.append("opencode")
    if have("claude"):
        out.append("claude")
    return out


def config_step() -> dict:
    banner("3. Your settings (config.json)")
    say("This file tells the tools which AI writes your applications and where things are.\n"
        "It stays on this computer and is never committed to a public repo.")
    cfg_path = HOME / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        say("You already have a config.json. I'll show each setting; press Enter to keep it.")
    else:
        cfg = json.loads((HOME / "config.example.json").read_text())

    say("\nWhich AI should write your resume variants and cover letters?\n"
        "  opencode  the OpenCode CLI, any model you like\n"
        "  claude    the Claude Code CLI (your Claude subscription)\n"
        "  manual    no program at all: the tools write a prompt file you paste into any\n"
        "            AI assistant (Claude or ChatGPT in the browser), then you click\n"
        "            \"Build documents\" on the board when the files are written\n")
    avail = runners_available()
    default = avail[0] if avail else "manual"
    runner = ask("Choose (opencode / claude / manual)", default)
    while runner not in ("opencode", "claude", "manual"):
        runner = ask("That's not one of the three. Choose (opencode / claude / manual)", default)
    if runner in avail:
        say(f"(I see the {runner} CLI installed, good.)")
    elif runner != "manual":
        say(f"(Note: I don't see the {runner} CLI on this computer. You can install it later\n"
            f"     (docs/agents.md); until then the board will say the packet failed.)")
    cfg.setdefault("agent", {})
    cfg["agent"]["runner"] = runner

    model = None
    if runner == "opencode":
        model = ask("Which model? (leave blank for whatever OpenCode is set to)",
                     cfg.get("agent", {}).get("model") or "") or None
        cfg["agent"]["model"] = model

    say("\nThe LinkedIn alerts pipeline (optional, step 8) needs two things here: your Worker's\n"
        "address and its key. If you haven't set that up yet, say skip and we'll come back.")
    worker_url = ask("Worker address (https://your-worker.yourname.workers.dev)",
                      cfg.get("worker_url") or "")
    if worker_url and "YOUR-" not in worker_url.upper():
        cfg["worker_url"] = worker_url
        token = worker_token_step(cfg)
        cfg["worker_token"] = token if IS_WIN else cfg.get("worker_token")
    else:
        say("Skipped. We'll do the alerts setup in step 8, where I'll ask for these again.")

    scoring = yn("\nPre-score new alert jobs with the AI (a 1-5 skills guess from the job title,\n"
                 "off by default; it only sees titles and your resume)",
                 bool(cfg.get("scoring", {}).get("enabled", False)))
    cfg["scoring"] = {"enabled": scoring}

    permanent_only = yn("Skip contract, temporary, and part-time postings automatically\n"
                        "(on by default; this search is for full-time permanent roles)",
                        bool(cfg.get("permanent_only", True)))
    cfg["permanent_only"] = permanent_only

    chrome = chrome_path()
    chrome = ask("Chrome location", cfg.get("chrome_path") or chrome or "")
    if not chrome and not IS_WIN:
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if chrome:
        cfg["chrome_path"] = chrome
    else:
        say("No Chrome found; set chrome_path in config.json when you install it.")

    cfg.setdefault("resume_master", "resume/master.md")
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    say(f"\nSaved {cfg_path}")
    return cfg


def worker_token_step(cfg: dict) -> str | None:
    """Store the Worker's read key. Mac: Keychain. Windows: config.json (gitignored)."""
    say("\nYour Worker's key (the ALERTS_TOKEN secret you made in the Cloudflare dashboard;\n"
        "it looks like a long random string).")
    if IS_WIN:
        tok = ask("Paste it (it's saved in config.json, which is never committed)") or ""
        return tok.strip() or None
    existing = run_quiet(["security", "find-generic-password", "-s", "job-alerts-worker", "-w"])
    if existing.returncode == 0 and existing.stdout.strip():
        if yn("I found your Worker key in the Keychain. Keep it?", True):
            return None
    tok = ask("Paste the key (I'll store it in the Keychain, service job-alerts-worker)")
    tok = tok.strip()
    if not tok:
        return None
    r = run_quiet(["security", "add-generic-password", "-U",
                   "-a", str(Path.home()), "-s", "job-alerts-worker", "-w", tok])
    if r.returncode == 0:
        say("Stored in the Keychain.")
    else:
        say(f"Couldn't store it in the Keychain ({r.stderr.strip()[:120]}). I'll put it in\n"
            "config.json instead (that's gitignored, so it's safe).")
        return tok
    return None


# ---------- 4. your files ----------

def files_step() -> None:
    banner("4. Your files (the part only you can do)")
    say("These files are where your information lives. Each one has placeholders to fill in.\n"
        "I can open each one for you; take your time, and tell me when you're done with it.\n"
        "(You can also do all of this later - the tools won't work well without the first two.)")
    files = [
        ("resume/master.md", "your one-page resume (the format rules are in resume/README.md;\n"
                             "the first line must be:  # Your Full Name"),
        ("AGENTS.md", "who you are, what jobs you want, and the rules the AI must follow\n"
                      "(there are placeholders to make it yours)"),
        ("applicant-profile.md", "your contact details and standard answers for application forms"),
        ("canned-answers.md", "your approved openers, proof blocks, closers, and answers"),
        ("experience-bank.md", "approved facts beyond the one-page resume (add as you go)"),
    ]
    for rel, what in files:
        p = HOME / rel
        say(f"\n--- {rel}\n    {what}")
        if yn(f"Open {rel} now?", not AUTO_YES):
            open_in_default_app(p)
        done = yn(f"When you've filled in {rel}, tell me (you can say no and finish later)", False)
        if done:
            say("  done - nice")
    say("\nWhen these are filled in, come back and run the wizard again; it'll test your\n"
        "resume build (step 5) and open the board (step 6).")


# ---------- 5. resume test ----------

def master_name() -> str:
    p = HOME / "resume/master.md"
    if p.is_file():
        for line in p.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return ""


def resume_test_step(tools: dict) -> None:
    banner("5. Test: build your resume to a PDF")
    name = master_name()
    if not name or name == "Your Name":
        say("Your resume/master.md still has the placeholder name, so there's nothing real\n"
            "to build yet. Fill it in (step 4) and run the wizard again.")
        return
    if not (have("node") and chrome_path() and have("pdfinfo")):
        say("Skipping: this needs Node.js, Chrome, and pdfinfo (all of step 1).")
        return
    if not (TOOLS / "node_modules").is_dir():
        say("Skipping: the docx package isn't installed yet (step 2).")
        return
    if not yn(f"Build a test copy of your resume now? (it lands in resume/ as {name}-Resume.pdf)",
              True):
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        r = run_quiet(["node", str(TOOLS / "build-resume.js"),
                       str(HOME / "resume/master.md"), str(tmp)], cwd=TOOLS)
        if r.returncode != 0:
            say(f"The build failed: {r.stderr.strip()[:300]}")
            return
        time.sleep(1)
        stem = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
        html = tmp / f"{stem}-Resume.html"
        pdf = tmp / f"{stem}-Resume.pdf"
        r = run_quiet([chrome_path(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                       f"--print-to-pdf={pdf}", f"file://{html}"])
        if not pdf.exists():
            say("Chrome didn't produce a PDF. Check chrome_path in config.json.")
            return
        pages = run_quiet(["pdfinfo", str(pdf)]).stdout
        m = re.search(r"Pages:\s+(\d+)", pages)
        n = int(m.group(1)) if m else "?"
        shutil.copy(pdf, HOME / "resume" / pdf.name)
        shutil.copy(tmp / f"{stem}-Resume.docx", HOME / "resume" / f"{stem}-Resume.docx")
        say(f"\nBuilt it: {n} page{'s' if n not in (1, '?') else ''}.\n"
            + ("Perfect - it's one page." if n == 1
               else "It's over one page. Trim resume/master.md (drop the least relevant\n"
                    "bullets) and run the wizard again."))
        say(f"Saved to resume/{pdf.name} and {stem}-Resume.docx")


# ---------- 6. the board ----------

def board_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def board_step() -> None:
    banner("6. The job board")
    if board_up():
        say("The board is already running at http://127.0.0.1:8765/")
    else:
        say("Starting the board server (it only listens on this computer)...")
        log = open(HOME / "board.log", "a")
        kwargs = {"cwd": str(HOME), "stdout": log, "stderr": subprocess.STDOUT}
        if IS_WIN:
            kwargs["creationflags"] = 0x00000200  # DETACHED_PROCESS
        subprocess.Popen([sys.executable, "-I", str(TOOLS / "board-server.py")], **kwargs)
        for _ in range(20):
            if board_up():
                break
            time.sleep(0.25)
        if not board_up():
            say("It didn't come up. Check board.log and run it by hand:\n"
                f"    {sys.executable} -I tools/board-server.py")
            return
        say("It's up.")
    if yn("Open it in your browser now?", not AUTO_YES):
        webbrowser.open("http://127.0.0.1:8765/")
    say("\nThat's the whole daily interface: add jobs, check remote, prep packets, apply.")


# ---------- 7. linkedin alerts ----------

def alerts_step(cfg: dict) -> None:
    banner("7. LinkedIn alerts (optional)")
    say("This is how new jobs arrive on their own. It's set up so your LinkedIn account is\n"
        "never at risk: LinkedIn emails you its own alerts, a small program of yours stores\n"
        "those emails, and the board reads them. The only thing it reads on LinkedIn is the\n"
        "public job pages - it never logs in. Full details: docs/linkedin-alerts.md")
    if not yn("Set it up now?", False):
        say("Skipped - you can run the wizard again any time, or just add jobs by hand.\n"
            "(The board works fine without it.)")
        return
    steps = [
        ("1. Create a KV namespace", "Go to https://dash.cloudflare.com/ , pick (or add) your\n"
         "domain, and create a KV namespace - any name is fine, e.g. job-alerts."),
        ("2. Create the Worker", "In the dashboard: Workers & Pages -> Create Worker. Name it\n"
         "job-alerts. Paste in the contents of tools/job-alerts-worker/worker.js and save."),
        ("3. Bind the KV namespace", "In the Worker's settings: Variables -> Bindings -> add a\n"
         "KV Namespace binding named ALERTS pointing at the namespace from step 1."),
        ("4. Make the key", "Worker settings -> Secrets and variables -> add the secret\n"
         "ALERTS_TOKEN. Make up a long random string (or run:  python3 -c \"import secrets;\n"
         "print(secrets.token_urlsafe(32))\"). You'll need this string in a moment."),
        ("5. Route the email address", "Workers & Pages -> the job-alerts Worker -> Triggers ->\n"
         "Email routes: add an route for alerts@YOURDOMAIN.com (an address you own; your\n"
         "domain has to be on Cloudflare)."),
        ("6. The Gmail filter", "In Gmail: Settings -> Filters -> New filter. From:\n"
         "jobs-noreply@linkedin.com  (and a second filter for jobalerts-noreply@linkedin.com).\n"
         "Action: Forward to: alerts@YOURDOMAIN.com."),
        ("7. The LinkedIn alert", "On LinkedIn: Jobs -> the bell icon -> create an alert for\n"
         "your search (titles, Remote, etc.). It emails your inbox; the filter does the rest."),
    ]
    for title, body in steps:
        say(f"\n{title}\n{body}")
        yn(f"Done with that step?", True)
    say("\nNow for the last two pieces, I can do these for you.")
    worker_url = ask("The Worker's address (dashboard shows it, ends in .workers.dev)",
                      cfg.get("worker_url") or "")
    if worker_url and "YOUR-" not in worker_url.upper():
        cfg["worker_url"] = worker_url
        tok = worker_token_step(cfg)
        if IS_WIN and tok:
            cfg["worker_token"] = tok
        (HOME / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
        say("Saved to config.json.")
        if yn("Test the whole pipeline now? (runs the ingest script in dry-run mode:\n"
              "it reads the Worker and your postings, changes nothing)", True):
            say("\nRunning the test...")
            r = run_quiet([sys.executable, "-I", str(TOOLS / "ingest-alerts.py"), "--dry-run"],
                          cwd=HOME, timeout=300)
            say((r.stdout or r.stderr).strip()[:1500])
    else:
        say("No Worker address given - finish steps 1-5 in the dashboard, then run the\n"
            "wizard again (it picks up where this left off).")


# ---------- 8. done ----------

def finish() -> None:
    banner("You're set up")
    say("""
The day-to-day, in one sentence each:

  1. Spot a job link? Paste it in inbox.md (or let the alerts do it).
  2. Open the board (Open Job Board.command / .bat) and work the New jobs:
     Interested or Not interested; confirm the remote ones ("Check remote").
  3. For a job you want, click "Prep application". Read fit-check.md first,
     then the letter and resume. Edit the .md files and click Rebuild to change wording.
  4. "Copy Chrome prompt", paste it into Claude in Chrome, attach the two PDFs
     when asked, and it fills the form. It stops before Submit. You submit.

Everything personal stays in this folder on this computer (config.json, applications/,
and the PDFs are gitignored, so they're safe if the folder becomes a public repo).

Good luck out there.
""")


def main() -> None:
    banner("Job Search Pilot - setup")
    say("""
This walks you through the whole setup, step by step. Nothing is sent anywhere
except to your own Cloudflare account (for the optional email pipeline) and to
your chosen AI provider when you later run the tools. You can skip any step;
run this wizard again any time to pick up where you left off.
""")
    say(f"Operating system: {'Windows' if IS_WIN else 'macOS'}")
    if not IS_WIN and sys.platform != "darwin":
        say("(That's neither Mac nor Windows; the wizard will try its best, but the\n"
            "install instructions below are for Mac and Windows.)")
    tools = install_step()
    npm_step()
    cfg = config_step()
    files_step()
    resume_test_step(tools)
    board_step()
    alerts_step(cfg)
    finish()


if __name__ == "__main__":
    main()
