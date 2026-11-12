#!/usr/bin/env python3
"""Job Search Pilot setup wizard.

Walks you through every setup step, in order, in plain language, on Mac or Windows:

  1. checks the tools you need (and tells you exactly how to install any that are missing)
  2. installs the one Node package
  3. your settings (config.json): which AI writes your applications, and a few choices
  4. your files: creates them from templates/ and walks you through filling them in
  5. tests that your resume builds to a one-page PDF
  6. opens the job board
  7. optionally walks you through the LinkedIn alerts setup and tests it

Usage:  python3 tools/setup-wizard.py          (Windows: py tools\\setup-wizard.py)
        python3 tools/setup-wizard.py --yes    (answer every question with the default)

Run it again any time: it keeps what you've done and picks up where you left off.

Nothing here is sent anywhere except to your own Cloudflare account and your chosen AI
provider when you run the tools later. Everything stays in this folder on this computer.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent  # noqa: E402
import alerts_worker  # noqa: E402
import documents  # noqa: E402
import jobsfile  # noqa: E402

HOME = agent.HOME
TOOLS = HOME / "tools"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
AUTO_YES = "--yes" in sys.argv
PORT = int(os.environ.get("JOB_BOARD_PORT", "8765"))
BOARD = f"http://127.0.0.1:{PORT}/"
PY = "py" if IS_WIN else "python3"


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
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif IS_MAC:
        subprocess.run(["open", str(p)], check=False)
    else:
        subprocess.run(["xdg-open", str(p)], check=False)


def run_quiet(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


def load_cfg() -> dict:
    return json.loads(agent.CONFIG.read_text(encoding="utf-8"))


def save_cfg(cfg: dict) -> None:
    agent.CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


# ---------- 1. tools ----------

def node_install_hint() -> str:
    if IS_WIN:
        return "winget install OpenJS.NodeJS.LTS   (or the LTS installer from https://nodejs.org)"
    if IS_MAC and have("brew"):
        return "brew install node"
    return "download the LTS installer from https://nodejs.org and run it"


def check_tools() -> dict:
    """Returns {name: (have_it, install_instruction)} for the tools we need."""
    return {
        f"Python 3 ({sys.version.split()[0]})": (sys.version_info >= (3, 9),
                                                 "install Python 3.9 or newer from https://python.org"),
        "Node.js": (have("node") is not None, node_install_hint()),
        "Google Chrome": (agent.find_chrome() is not None,
                          "download it from https://google.com/chrome and run the installer"),
    }


def install_step() -> None:
    banner("1. The tools we need")
    say("We need Python (you're running it now), Node.js, and Google Chrome (it prints your\n"
        "resume and letters to PDF). Let's check what you have.")
    while True:
        tools = check_tools()
        missing = [n for n, (ok, _) in tools.items() if not ok]
        for name, (ok, _) in tools.items():
            say(f"  {'ok      ' if ok else 'MISSING '} {name}")
        if not missing:
            say("\nAll present.")
            return
        for name in missing:
            say(f"\n  {name}: {tools[name][1]}")
        if IS_WIN:
            say("\n  After installing, close this window, open a NEW terminal, and run the wizard again\n"
                "  (a new window picks up the newly installed programs).")
        if AUTO_YES or not yn("\nInstalled them? Check again", False):
            break
    say("\nContinuing without them for now. The board works fine; the steps that build PDFs\n"
        "will say what's missing, and you can run the wizard again later.")


# ---------- 2. node package ----------

def npm_step() -> None:
    banner("2. The one Node package")
    npm = have("npm")
    if not npm:
        say("Node.js isn't installed yet, so we'll skip this. Run the wizard again after\n"
            "installing it (step 1).")
        return
    if (TOOLS / "node_modules" / "docx").is_dir():
        say("Already installed. Nothing to do.")
        return
    if not yn("Install the docx package now? (runs: npm install, in the tools folder)", True):
        say("Skipped. Run it later:  cd tools  then  npm install")
        return
    say("Installing... (about a minute)")
    r = run_quiet([npm, "install", "--no-audit", "--no-fund"], cwd=TOOLS)
    if r.returncode == 0 and (TOOLS / "node_modules" / "docx").is_dir():
        say("Done.")
    else:
        say(f"npm install failed: {(r.stderr or r.stdout).strip()[-300:]}\n"
            "Run it by hand later:  cd tools  then  npm install")


# ---------- 3. settings ----------

def runners_available() -> list[str]:
    return [r for r in agent.CLI_RUNNERS if have(r)]


def config_step() -> dict:
    banner("3. Your settings (config.json)")
    say("This file tells the tools which AI writes your applications. It stays on this\n"
        "computer and is never committed. Press Enter to keep what's in brackets.")
    cfg = load_cfg()

    say("\nWhich AI should write your resume variants and cover letters?\n"
        "  manual    the simplest: the board gives you a prompt to paste into any AI chat\n"
        "            (ChatGPT, Claude, Gemini, ...), and you paste its reply back. Nothing to install.\n"
        "  claude    the Claude Code CLI does it for you (uses your Claude subscription)\n"
        "  codex     OpenAI's Codex CLI does it for you (uses your ChatGPT subscription)\n"
        "  opencode  the OpenCode CLI does it for you, with any model you've set up\n"
        "You can change this any time under Settings on the board.\n")
    avail = runners_available()
    current = agent.runner_name(cfg)
    default = current if current != "manual" or not avail else avail[0]
    if avail:
        say(f"(I see these installed: {', '.join(avail)}.)")
    runner = ask("Choose (manual / claude / codex / opencode)", default)
    while runner not in agent.RUNNERS:
        runner = ask("That's not one of them. Choose (manual / claude / codex / opencode)", default)
    if runner != "manual" and runner not in avail:
        say(f"(I don't see the {runner} CLI on this computer. Install it (docs/agents.md); until\n"
            f" then, packets will fail with a message saying so.)")
    cfg.setdefault("agent", {})["runner"] = runner
    if runner != "manual":
        cfg["agent"]["model"] = ask(f"Which model? (blank = whatever {runner} is set to)",
                                    cfg["agent"].get("model") or "") or None

    cfg["permanent_only"] = yn("\nSkip contract, temporary, and part-time postings automatically?",
                               bool(cfg.get("permanent_only", True)))
    if cfg["agent"]["runner"] != "manual":
        cfg["scoring"] = {"enabled": yn(
            "Give new LinkedIn alert jobs a 1-5 fit guess from the title? (only if you set up\n"
            "alerts; it sends job titles and your resume to your AI)",
            bool(cfg.get("scoring", {}).get("enabled", False)))}

    chrome = agent.find_chrome()
    if chrome:
        cfg["chrome_path"] = chrome
        say(f"\nFound Chrome: {chrome}")
    else:
        typed = ask("\nWhere is Chrome? (paste the full path to the program, or leave blank)",
                    cfg.get("chrome_path") or "")
        if typed:
            cfg["chrome_path"] = typed
    cfg.setdefault("resume_master", "resume/master.md")
    save_cfg(cfg)
    say(f"Saved {agent.CONFIG}")
    return cfg


# ---------- 4. your files ----------

FILES = [
    ("resume/master.md", "your one-page resume. The first line must be  # Your Full Name;\n"
                         "the format is in resume/README.md"),
    ("about-me.md", "who you are, the jobs you want, your pay floor and salary rule, your\n"
                    "voice, and your own rules for the AI"),
    ("applicant-profile.md", "your contact details and standard answers for application forms"),
    ("canned-answers.md", "your approved openers, proof blocks, closers, and answers"),
    ("experience-bank.md", "approved facts beyond the one-page resume (add to it as you go)"),
]


def still_template(rel: str) -> bool:
    tpl = agent.TEMPLATES / agent.PERSONAL[rel]
    return (HOME / rel).read_text(encoding="utf-8-sig") == tpl.read_text(encoding="utf-8")


def files_step() -> None:
    banner("4. Your files (the part only you can do)")
    made = agent.ensure_personal_files()
    if made:
        say("I made your own copies of these from templates/: " + ", ".join(made))
    say("These files are where your information lives. They're yours: they're never committed\n"
        "or overwritten by updates. Each one has [brackets] to fill in. The first two matter\n"
        "most; the others make the letters and answers better.")
    for rel, what in FILES:
        state = "not filled in yet" if still_template(rel) else "you've started it"
        say(f"\n--- {rel}  ({state})\n    {what}")
        if still_template(rel) and yn(f"Open {rel} now?", not AUTO_YES):
            open_in_default_app(HOME / rel)
            yn("Tell me when you've saved it (or say no and finish it later)", True)
    say("\nTip: if you use Claude Code or OpenCode, you can open this folder in it and say\n"
        "\"help me fill in about-me.md and my experience bank\": it will interview you.")


# ---------- 5. resume test ----------

def resume_test_step() -> None:
    banner("5. Test: build your resume to a PDF")
    master = HOME / "resume" / "master.md"
    name = documents.master_name(master)
    if still_template("resume/master.md") or name == "Your Name":
        say("resume/master.md still has the placeholder name, so there's nothing real to\n"
            "build yet. Fill it in (step 4) and run the wizard again.")
        return
    if not (have("node") and agent.find_chrome()):
        say("Skipping: this needs Node.js and Chrome (step 1).")
        return
    if not (TOOLS / "node_modules" / "docx").is_dir():
        say("Skipping: the docx package isn't installed yet (step 2).")
        return
    if not yn(f"Build your resume now? (it lands in resume/ as {documents.file_stem(load_cfg(), master)}-Resume.pdf)",
              True):
        return
    r = run_quiet([sys.executable, "-X", "utf8", str(TOOLS / "rebuild-resume.py")], cwd=HOME)
    say((r.stdout + r.stderr).strip())
    if r.returncode == 0:
        say("Perfect: it's one page.")
    elif "Pages:" in r.stdout:
        say("It's over one page. Trim resume/master.md (drop the least relevant bullets) and\n"
            f"run:  {PY} tools/rebuild-resume.py")


# ---------- 6. the board ----------

def board_up() -> bool:
    try:
        with urllib.request.urlopen(BOARD, timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def board_step() -> None:
    banner("6. The job board")
    if IS_MAC:
        # A downloaded ZIP marks the launcher as "from the internet", and macOS refuses to
        # double-click it. Clear that, and make sure it's executable.
        launcher = HOME / "Open Job Board.command"
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(launcher)], capture_output=True)
        launcher.chmod(0o755)
    if board_up():
        say(f"The board is already running at {BOARD}")
    else:
        say("Starting the board server (it only listens on this computer)...")
        log = open(HOME / "board.log", "a", encoding="utf-8")
        kwargs: dict = {"cwd": str(HOME), "stdout": log, "stderr": subprocess.STDOUT}
        if IS_WIN:
            kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, "-X", "utf8", "-I", str(TOOLS / "board-server.py")], **kwargs)
        for _ in range(40):
            if board_up():
                break
            time.sleep(0.25)
        if not board_up():
            say("It didn't come up. Check board.log, or run it by hand to see why:\n"
                f"    {PY} tools/board-server.py")
            return
        say("It's up.")
    if yn("Open it in your browser now?", not AUTO_YES):
        webbrowser.open(BOARD)
    launcher = "Open Job Board.bat" if IS_WIN else "Open Job Board.command"
    say(f"\nFrom now on, double-click \"{launcher}\" in this folder to open the board.\n"
        "Start with \"Add job\": paste a posting's link and it fills in the details.")


# ---------- 7. linkedin alerts ----------

def alerts_step(cfg: dict) -> None:
    banner("7. LinkedIn alerts (optional)")
    say("This is how new jobs arrive on their own. It needs a domain name of your own on\n"
        "Cloudflare (free plan is fine) and about 20 minutes. Your LinkedIn account is never\n"
        "at risk: LinkedIn emails you its own alerts, Gmail forwards them to an address on\n"
        "your domain, a small program of yours stores them, and the board reads them. It never\n"
        "logs in to LinkedIn. Full details: docs/linkedin-alerts.md")
    if agent.alerts_configured(cfg):
        say(f"\nYou've set this up already (Worker: {cfg['worker_url']}).")
        if not yn("Go through it again (for example, to test it or fix the Gmail part)?", False):
            return
    elif not yn("\nSet it up now?", False):
        say("Skipped. Run the wizard again any time. The board works fine without it: use\n"
            "\"Add job\" to add postings you find.")
        return

    say("\nPart 1: your Worker, in the Cloudflare dashboard (https://dash.cloudflare.com)")
    for title, body in [
        ("1. Create a KV namespace", "Storage & Databases -> KV -> Create. Any name, e.g. job-alerts."),
        ("2. Create the Worker", "Workers & Pages -> Create -> Worker. Name it job-alerts, deploy,\n"
         "then Edit code: replace everything with the contents of\n"
         "tools/job-alerts-worker/worker.js, and Deploy."),
        ("3. Bind the KV namespace", "The Worker -> Settings -> Bindings -> Add -> KV namespace.\n"
         "Variable name: ALERTS. Namespace: the one from step 1."),
        ("4. Make the key", "The Worker -> Settings -> Variables and Secrets -> Add, type Secret,\n"
         "name ALERTS_TOKEN, value: a long random string. Here's one you can use:\n"
         f"    {__import__('secrets').token_urlsafe(32)}\n"
         "Copy it somewhere for a moment; I'll ask for it next."),
        ("5. Route an email address to it", "Your domain -> Email -> Email Routing (turn it on if\n"
         "asked) -> Routing rules -> Create address, e.g. alerts@yourdomain.com,\n"
         "action: Send to a Worker -> job-alerts."),
    ]:
        say(f"\n{title}\n{body}")
        yn("Done with that step?", True)

    say("\nPart 2: connect this computer to the Worker")
    worker_url = ask("The Worker's address (on its page in the dashboard; ends in .workers.dev)",
                     cfg.get("worker_url") if agent.alerts_configured(cfg) else "")
    if not worker_url.startswith("http"):
        say("No Worker address, so we'll stop here. Run the wizard again when it's ready.")
        return
    cfg["worker_url"] = worker_url.rstrip("/")
    token = store_worker_key(cfg)
    save_cfg(cfg)
    problem = alerts_worker.connection_problem(cfg, token)
    if problem:
        say(f"\nThe Worker didn't answer properly: {problem}\nFix that and run the wizard again.")
        return
    say("The Worker answers. Saved to config.json.")

    say("\nPart 3: Gmail forwards LinkedIn's alerts to that address\n"
        "Gmail won't forward to a new address until you confirm a code it emails there. The\n"
        "Worker keeps that email for you, so I can read the code.\n\n"
        "In Gmail: the gear -> See all settings -> Forwarding and POP/IMAP -> Add a forwarding\n"
        "address -> type your alerts address (e.g. alerts@yourdomain.com) -> Next -> Proceed.\n"
        "Gmail says it sent a confirmation code. (Leave forwarding itself turned OFF: the\n"
        "filter below forwards only the LinkedIn mail.)")
    if yn("\nDone? I'll look for the code", True):
        for attempt in range(6):
            conf = alerts_worker.forwarding_confirmation(cfg, token)
            if conf:
                say(f"\nGmail's confirmation code: {conf['code'] or '(not found)'}")
                if conf["link"]:
                    say(f"Or open this link to confirm: {conf['link']}")
                say("Back in Gmail, on the Forwarding and POP/IMAP page, enter the code and Verify.")
                break
            if attempt == 5 or AUTO_YES:
                say("No confirmation email yet. Run  "
                    f"{PY} tools/alerts_worker.py  in a minute to see it.")
                break
            say("Not there yet; checking again in 10 seconds...")
            time.sleep(10)
        yn("Verified?", True)

    say("\nPart 4: the filter, and the alert\n"
        "In Gmail, in the search box, paste:\n"
        "    from:(jobalerts-noreply@linkedin.com OR jobs-noreply@linkedin.com)\n"
        "then click the filter icon at the right of the search box -> Create filter ->\n"
        "tick \"Forward it to\" and pick your alerts address -> Create filter.\n\n"
        "On LinkedIn: search Jobs for what you want (title, and Remote under the location\n"
        "filters), then turn on \"Set alert\" (or \"Job alert\") and choose email delivery.")
    yn("Done?", True)
    if yn("\nTest it now? (reads the Worker and the postings it finds, changes nothing)", True):
        say("Running the test...")
        r = run_quiet([sys.executable, "-X", "utf8", "-I", str(TOOLS / "ingest-alerts.py"), "--dry-run"],
                      cwd=HOME, timeout=600)
        say((r.stdout + r.stderr).strip()[-1500:] or "(no output)")
        say("\nIf it says 0 new emails, that's normal until LinkedIn sends the first alert\n"
            "(usually within a day). The board checks every 3 hours from 8am to 10pm.")


def store_worker_key(cfg: dict) -> str | None:
    """Ask for the Worker's key. Mac: the Keychain. Windows and Linux: config.json (never
    committed). Returns the key."""
    existing = agent.worker_token(cfg, required=False)
    if existing and yn("I have a Worker key saved already. Keep it?", True):
        return existing
    tok = ask("Paste the key (the ALERTS_TOKEN value from step 4)").strip()
    if not tok:
        return existing
    if IS_MAC:
        r = run_quiet(["security", "add-generic-password", "-U", "-a", os.environ.get("USER", "me"),
                       "-s", "job-alerts-worker", "-w", tok])
        if r.returncode == 0:
            cfg["worker_token"] = None
            say("Stored in your Keychain.")
            return tok
        say("Couldn't use the Keychain, so it goes in config.json (never committed).")
    cfg["worker_token"] = tok
    return tok


# ---------- done ----------

def finish() -> None:
    banner("You're set up")
    launcher = "Open Job Board.bat" if IS_WIN else "Open Job Board.command"
    say(f"""
The day-to-day:

  1. Open the board: double-click "{launcher}".
  2. Found a job? Click "Add job" and paste the link. (Alert jobs arrive on their own.)
     Work the New ones: Interested or Not interested. Confirm remote ones ("Check remote").
  3. For a job you want, click it, then "Prep application". Read the fit check first,
     then the letter and resume.
  4. "Copy Chrome prompt", paste it into Claude in Chrome, attach the two PDFs when
     asked, and it fills the form. It stops before Submit. You submit, then "Mark applied".

Your own files (resume, about-me.md, the profile, jobs, applications) are never committed,
so you can update the tools any time with:  git pull

Good luck out there.
""")


def main() -> None:
    jobsfile.utf8_stdio()
    banner("Job Search Pilot: setup")
    say("""
This walks you through the whole setup, step by step. You can skip any step and run
this wizard again any time; it picks up where you left off.""")
    say(f"Computer: {'Windows' if IS_WIN else 'Mac' if IS_MAC else sys.platform}")
    agent.ensure_personal_files()
    install_step()
    npm_step()
    cfg = config_step()
    files_step()
    resume_test_step()
    board_step()
    alerts_step(cfg)
    finish()


if __name__ == "__main__":
    main()
