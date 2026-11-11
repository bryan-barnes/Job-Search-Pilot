#!/usr/bin/env python3
"""Build an application packet for one job in jobs.js.

Usage:  python3 -I tools/prep-application.py <job-id>              (full prep)
        python3 -I tools/prep-application.py <job-id> --build-only (build the PDFs from the .md files)
        (the board's "Prep application" button runs the first form for you)

Makes applications/<job-id>/ with:
  posting.md                 the job description, saved now in case the posting disappears
  resume.md, cover-letter.md, answers.md, fit-check.md   written by the configured agent
                               (config.json -> agent.runner: opencode, claude, or manual),
                               following tools/application-prompt.md
  <First-Last>-Resume.pdf/.docx, <First-Last>-Cover-Letter.pdf/.docx
                             (the name comes from the master resume's first line)
  apply-in-chrome.md         the prompt to paste into Claude in Chrome to fill the form
  status.json                progress, read by the board

In "manual" mode the agent step writes RUN-THIS.md, one self-contained prompt with every source
file inside it, and stops. You paste it into any AI assistant and paste the reply back into the
board, which saves the four .md files and runs this script with --build-only.

Nothing is submitted anywhere; you review the packet and apply yourself.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import urllib.request
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent  # noqa: E402
import documents  # noqa: E402
import jobsfile  # noqa: E402
import linkedin_check  # noqa: E402

HOME = jobsfile.HOME
TOOLS = HOME / "tools"
FIELDS = ["company", "role", "pay", "location", "remote", "url", "source", "fit", "blocker", "notes"]
WRITES = agent.WRITES


def load_cfg() -> dict:
    cfg = agent.load_config()
    cfg["_master"] = HOME / Path(cfg.get("resume_master") or "resume/master.md").expanduser()
    if not cfg["_master"].is_file():
        sys.exit(f"No master resume at {cfg['_master']} (config.json: resume_master).")
    return cfg


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


class Packet:
    def __init__(self, job_id: str):
        self.id = job_id
        self.dir = HOME / "applications" / job_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def status(self, state: str, step: str, **extra) -> None:
        data = {"state": state, "step": step, "updated": datetime.now().isoformat(timespec="seconds"),
                **extra}
        (self.dir / "status.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"[{state}] {step}", flush=True)


def job_fields(job_id: str) -> dict:
    text = jobsfile.read()
    return {k: jobsfile.get(text, job_id, k) for k in FIELDS}


def fetch_generic(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": linkedin_check.UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        page = resp.read().decode("utf-8", "replace")
    page = re.sub(r"<(script|style|nav|header|footer)\b.*?</\1>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", page)
    text = linkedin_check.html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()[:20000]


def save_posting(p: Packet, job: dict, cfg: dict) -> None:
    url = job.get("url") or ""
    desc, extra = "", ""
    m = re.search(r"linkedin\.com/jobs/view/(\d+)", url)
    if m:
        info = linkedin_check.posting(m.group(1))
        if info and info["closed"]:
            raise RuntimeError("LinkedIn says this posting is no longer accepting applications. "
                               "Mark it Posting expired.")
        if cfg.get("permanent_only", True) and info and info.get("not_permanent"):
            raise RuntimeError("This looks like a contract, temporary, or part-time job "
                               f"({info['not_permanent'][:100]}). This search is for full-time "
                               "permanent roles only; mark it Not interested.")
        if info:
            desc = info["description"]
            extra = (f"- LinkedIn says: {'CLOSED, no longer accepting applications' if info['closed'] else 'open'}\n"
                     f"- Remote check: {info['remote']} ({info['evidence']})\n")
    elif url:
        gone = linkedin_check.other_site_closed(url)
        if gone and gone[0]:
            raise RuntimeError(f"The posting page looks closed ({gone[1][:80]}). Mark it Posting expired.")
        try:
            desc = fetch_generic(url)
        except Exception as exc:  # noqa: BLE001
            extra = f"- Couldn't fetch the posting automatically: {exc}\n"
    if not m and cfg.get("permanent_only", True) \
            and linkedin_check.not_permanent(job.get("role", ""), desc):
        raise RuntimeError("This looks like a contract, temporary, or part-time job "
                           f"({linkedin_check.not_permanent(job.get('role', ''), desc)[:100]}). "
                           "This search is for full-time permanent roles only; mark it Not interested.")
    if len(desc) < 400:
        extra += ("- The saved description looks too short. The page may need a browser. Paste the "
                  "job description into your-notes.md in this folder, or below, and run Prep again.\n")
    head = "\n".join(f"- {k}: {job[k]}" for k in FIELDS if job.get(k) not in (None, ""))
    (p.dir / "posting.md").write_text(
        f"# {job.get('role')} at {job.get('company')}\n\nSaved {date.today().isoformat()}.\n\n"
        f"## From the tracker\n{head}\n{extra}\n## Job description\n\n{desc or '(not fetched)'}\n",
        encoding="utf-8")


# ---------- the agent step ----------

MANUAL_HEADER = """\
You're helping me apply for a job, working in this chat without access to my files.
Everything the instructions below tell you to read is included at the end of this message,
each file starting with a line like `@@@ FILE: posting.md @@@`.

How to answer: where the instructions say to write a file, put it in your reply instead. Start
each file on its own line with its marker, exactly like this, in this order:

@@@ FILE: resume.md @@@
@@@ FILE: cover-letter.md @@@
@@@ FILE: answers.md @@@
@@@ FILE: fit-check.md @@@

Under each marker, write that file's contents as plain Markdown (not inside a code block).
Write nothing before the first marker. If you can't do the job (for example, there's no job
description below), reply only with `@@@ FILE: NEEDS-POSTING.md @@@` and say what's missing.

I'll paste your whole reply back into my job board, which splits it into the four files.

===== INSTRUCTIONS =====

"""


def master_ref(p: Packet, cfg: dict) -> str:
    """How the prompt names the master resume: relative to the packet folder when it's inside
    this folder (../../resume/master.md), else its full path (resume_master can point anywhere)."""
    try:
        return "../../" + cfg["_master"].resolve().relative_to(HOME.resolve()).as_posix()
    except ValueError:
        return str(cfg["_master"])


def source_files(p: Packet, cfg: dict) -> list[tuple[str, Path]]:
    """(name as the prompt refers to it, path) for every file the agent should read."""
    out = [("posting.md", p.dir / "posting.md")]
    if (p.dir / "your-notes.md").exists():
        out.append(("your-notes.md", p.dir / "your-notes.md"))
    for name in ("about-me.md", "canned-answers.md", "experience-bank.md", "applicant-profile.md"):
        out.append((f"../../{name}", HOME / name))
    out.append((master_ref(p, cfg), cfg["_master"]))
    out.append(("../../bases/README.md", HOME / "bases" / "README.md"))
    for base in sorted(d for d in (HOME / "bases").iterdir() if d.is_dir()):
        for f in ("about.md", "resume.md", "cover-letter.md"):
            if (base / f).is_file():
                out.append((f"../../bases/{base.name}/{f}", base / f))
    return [(n, f) for n, f in out if f.is_file()]


def agent_prompt(p: Packet, cfg: dict) -> str:
    base = read(TOOLS / "application-prompt.md") + (
        f"\n\nThe master resume is at: {master_ref(p, cfg)}\n")
    if agent.runner_name(cfg) != "manual":
        return base + "Start now. When you're done, reply with one line: the files you wrote."
    files = "\n\n".join(f"@@@ FILE: {name} @@@\n\n{read(path).strip()}"
                        for name, path in source_files(p, cfg))
    return MANUAL_HEADER + base + "\n===== THE FILES =====\n\n" + files + "\n"


def run_agent(p: Packet, cfg: dict, prompt: str | None = None, log_name: str = "agent.log") -> str:
    """Run the prompt through the configured agent. Returns the runner used ('manual' writes
    RUN-THIS.md and runs nothing)."""
    prompt = prompt or agent_prompt(p, cfg)
    runner = agent.run_prompt(cfg, prompt, cwd=p.dir, log=p.dir / log_name)
    if runner != "manual":
        if (p.dir / "NEEDS-POSTING.md").exists():
            raise RuntimeError("Couldn't get the job description; see NEEDS-POSTING.md")
        missing = [f for f in WRITES if not (p.dir / f).exists()]
        if missing:
            raise RuntimeError("The agent didn't write: " + ", ".join(missing))
    return runner


# ---------- building the documents ----------

def build_documents(p: Packet, cfg: dict) -> dict:
    stem = documents.file_stem(cfg, cfg["_master"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pages = {
            "resume": documents.build_resume(p.dir / "resume.md", tmp, cfg["chrome_path"], stem),
            "letter": documents.build_letter(p.dir / "cover-letter.md", cfg["_master"], tmp,
                                             cfg["chrome_path"], stem),
        }
        for f in list(tmp.glob("*.pdf")) + list(tmp.glob("*.docx")):
            shutil.copy(f, p.dir / f.name)
    return pages


TRIM = {"resume": ("resume.md", "Remove the least relevant bullet for this posting, or shorten two or three "
                              "bullets, so it drops about 25 words. Keep the same Markdown structure."),
        "letter": ("cover-letter.md", "Cut about 30 words. Keep the opener, the strongest proof, and the closer.")}


def build_one_page(p: Packet, cfg: dict, tries: int = 2) -> dict:
    """Build the documents; if the resume or letter runs past one page, ask the agent to trim it
    and rebuild. In manual mode there is no agent to trim with, so just report the page counts."""
    pages = build_documents(p, cfg)
    if agent.runner_name(cfg) == "manual":
        return pages
    for n in range(tries):
        long = [k for k, v in pages.items() if v > 1]
        if not long:
            break
        p.status("running", f"Trimming to one page ({', '.join(long)})")
        asks = "\n".join(f"- `{TRIM[k][0]}` prints at {pages[k]} pages; it must be one. {TRIM[k][1]}" for k in long)
        run_agent(p, cfg, prompt=(
            "You're in a job application packet folder. Edit only the files named below, in place.\n"
            f"{asks}\nOnly cut or shorten; never add facts, numbers, or new wording claims. Follow the voice "
            "rules already in the file (no em dashes). Reply with one line saying what you cut."),
            log_name=f"trim-{n + 1}.log")
        pages = build_documents(p, cfg)
    return pages


def chrome_prompt(p: Packet, job: dict, cfg: dict) -> None:
    """One self-contained prompt for Claude in Chrome, which can't read files on this computer."""
    stem = documents.file_stem(cfg, cfg["_master"])
    letter = read(p.dir / "cover-letter.md").strip()
    answers = read(p.dir / "answers.md").strip()
    profile = read(HOME / "applicant-profile.md").strip()
    (p.dir / "apply-in-chrome.md").write_text(f"""Help me fill out a job application. Don't submit it: I'll review and click Submit myself.

Job: {job.get('role')} at {job.get('company')}
Posting: {job.get('url')}

Steps:
1. Open the posting in a new tab. Read the workplace badge under the job title (Remote / Hybrid / On-site). If it says Hybrid or On-site, stop and tell me: I only apply to fully remote jobs. Otherwise click Apply. If it sends you to the employer's site (Workday, Greenhouse, Lever, iCIMS, Hirebridge, etc.), follow it. If it's LinkedIn Easy Apply, use that. If Apply opens a popup that doesn't appear, open that link in this tab instead.
2. Sign-in: if the site only asks for my email, use the email in MY PROFILE below. If it asks for a password, a verification code, or to create an account, stop and let me do it. Never type or invent a password.
3. Resume first. If the form has a resume upload or "autofill from resume", stop right away and ask me to attach {stem}-Resume.pdf before you fill anything, because the parser overwrites fields. Cover letter: if it's a text box, paste the COVER LETTER below; if it's an upload, ask me to attach {stem}-Cover-Letter.pdf at the same time as the resume. Both files (and .docx versions) are in my packet folder: {p.dir}
4. After the resume is parsed, check the fields it filled (name, contact, work history, education) against MY PROFILE and fix parsing errors.
5. Fill the rest using MY PROFILE and DRAFT ANSWERS below. Use the draft answers' wording for free-text questions, trimmed to fit any character limit.
6. Don't stop for each unknown question. Keep going, skip anything not covered (and anything marked "[you: fill]"), then ask me all of them together in one list. Don't guess on salary, work authorization, references, legal agreements, or demographic questions.
7. Required consent and attestation checkboxes (privacy, AI evaluation, recording, background checks, "all of this is true"): tick them. Leave optional marketing or talent-community boxes unticked.
8. Stop on the final review page. Tell me what you filled in, what you skipped, and which checkboxes you ticked.

===== MY PROFILE =====

{profile}

===== DRAFT ANSWERS FOR THIS JOB =====

{answers}

===== COVER LETTER =====

{letter}
""", encoding="utf-8")


def update_tracker(job_id: str, stem: str) -> None:
    def record(text):
        text = jobsfile.set_field(text, job_id, "resume", f"applications/{job_id}/{stem}-Resume.pdf")
        prev = jobsfile.get(text, job_id, "next") or ""
        nxt = "Review the packet (fit-check.md first), then apply with Claude in Chrome"
        if prev and not prev.startswith("Review the packet") and not prev.startswith("Follow the packet"):
            nxt += f" (earlier next step: {prev})"
        text = jobsfile.set_field(text, job_id, "next", nxt)
        return jobsfile.touch(text, date.today().isoformat())
    jobsfile.update(record)


def finish_packet(p: Packet, job: dict, cfg: dict, job_id: str, stem: str) -> None:
    """Build the documents and the Chrome prompt, note the page check, and mark it ready."""
    p.status("running", "Building PDF and Word files")
    pages = build_one_page(p, cfg)
    chrome_prompt(p, job, cfg)
    warn = [f"{k} is {n} pages" for k, n in pages.items() if n != 1]
    fit = p.dir / "fit-check.md"
    old = read(fit) if fit.exists() else ""
    old = old.split("\n\n## Build check (script)")[0].rstrip()
    fit.write_text(old + "\n\n## Build check (script)\n\n"
                   + "\n".join(f"- {k.title()} PDF: {n} page{'s' if n != 1 else ''}"
                               + ("" if n == 1 else ". Too long: trim resume.md or cover-letter.md, "
                                                    "then click Rebuild documents.")
                               for k, n in pages.items()) + "\n", encoding="utf-8")
    update_tracker(job_id, stem)
    p.status("ready", "Packet ready" + (f" (check: {', '.join(warn)})" if warn else ""), pages=pages)


def main() -> None:
    jobsfile.utf8_stdio()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build_only = "--build-only" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    job_id = args[0]
    cfg = load_cfg()
    if job_id not in jobsfile.ids(jobsfile.read()):
        sys.exit(f"No job {job_id!r} in jobs.js")
    p = Packet(job_id)
    stem = documents.file_stem(cfg, cfg["_master"])
    try:
        job = job_fields(job_id)
        if build_only:
            missing = [n for n in WRITES[:3] if not (p.dir / n).is_file()]
            if missing:
                raise RuntimeError("Missing " + ", ".join(missing) +
                                   "; paste the AI's reply into the board (or write them) first.")
            finish_packet(p, job, cfg, job_id, stem)
            return
        # Keep the last version of anything we're about to regenerate (you may have edited it).
        old = [f for f in p.dir.iterdir() if f.is_file() and f.name not in ("status.json", "prep.log")]
        if any(f.name == "cover-letter.md" for f in old):
            keep = p.dir / "previous" / datetime.now().strftime("%Y-%m-%d-%H%M%S")
            keep.mkdir(parents=True)
            for f in old:
                shutil.copy2(f, keep / f.name)
            for name in WRITES + ("NEEDS-POSTING.md",):
                (p.dir / name).unlink(missing_ok=True)
        p.status("running", "Saving the posting")
        save_posting(p, job, cfg)
        p.status("running", "Writing resume and cover letter (a few minutes)")
        runner = run_agent(p, cfg)
        if runner == "manual":
            p.status("manual", "Manual mode: copy the prompt, paste it into your AI assistant, then "
                               "paste its whole reply back here.")

            def record(text):
                prev = jobsfile.get(text, job_id, "next") or ""
                nxt = "Follow the packet's manual steps on the board (copy prompt, paste reply)"
                if prev and not prev.startswith("Follow the packet"):
                    nxt += f" (earlier next step: {prev})"
                return jobsfile.set_field(text, job_id, "next", nxt)
            jobsfile.update(record)
            return
        finish_packet(p, job, cfg, job_id, stem)
    except Exception as exc:  # noqa: BLE001
        p.status("failed", str(exc)[:300])
        sys.exit(1)


if __name__ == "__main__":
    main()
