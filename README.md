# Job Search Pilot

A private, local pilot for a job search: a job board, an automatic LinkedIn alert pipeline,
and a per-job application workflow where an AI agent writes your resume variants, cover letters,
and form answers from your approved materials. You review everything; nothing is ever submitted
without you.

It's built to be cloned and configured for your own search. The folder is **private by
design**: your resume, jobs, and applications stay on your Mac. The public repo contains only
the tools and templates, with no personal data (see `AGENTS.md` for the rule).

## What it does

- **The board** (`tracker.html` + `tools/board-server.py`): a local web page listing your jobs
  in a pipeline (New → Found → Applying → Applied → ...). Its buttons save straight to
  `jobs.js`. Fully remote jobs only; the rest are hidden.
- **The setup wizard** (`tools/setup-wizard.py`): walks a new Mac or Windows through the
  whole setup in plain language - tools, config, your files, a resume build test, the board,
  and the optional LinkedIn alerts.
- **The alert pipeline** (`tools/ingest-alerts.py` + a Cloudflare Email Worker): LinkedIn
  alert emails are forwarded to an address you own, stored for 30 days, and pulled into the
  board as `new` jobs. Closed postings and (optionally) contract/temp/part-time jobs are
  skipped; each job's remote status is read from the posting. It never logs in to LinkedIn,
  on purpose, so your account is never at risk (see `docs/linkedin-alerts.md`).
- **Application packets** (`tools/prep-application.py`): for each job you want, a folder in
  `applications/<job-id>/` with the saved posting, a one-page resume variant, a cover letter,
  draft form answers, an honest fit check, and a prompt for Claude in Chrome to fill the
  application form (it stops before Submit).
- **The agent** (`tools/agent.py`): the writing is done by the CLI you configure, `opencode`
  or `claude`, or by you pasting a prompt file into any assistant (`manual` mode).

## Quick start

**Run the setup wizard — it walks you through every step:**

```
python3 tools/setup-wizard.py        (Mac and Windows)
```

or double-click `Open Job Board.command` (Mac) / `Open Job Board.bat` (Windows) once the
wizard is done. The wizard checks your tools, installs the one Node dependency, creates
`config.json`, stores your Worker key, and walks you through the files you need to fill in,
with separate instructions for Mac and Windows. On a Mac you can also run `zsh setup.sh`
for a quick non-interactive check.

Then fill in the templates (the wizard lists them):
   - `resume/master.md` — your one-page resume. The format the builders expect is in
     `resume/README.md`. The PDF/Word files are named after its first line.
   - `AGENTS.md` — who you are, what you're targeting, your rules for agents. This is the file
     every agent reads first.
   - `applicant-profile.md` — contact details and standard form answers.
   - `canned-answers.md` — your approved openers, proof blocks, closers, and answers.
   - `experience-bank.md` — approved facts beyond the one-page resume.
3. `zsh tools/rebuild-resume.sh` — builds `Your-Name-Resume.pdf/.docx` from the master and
   prints the page count (it must be one).
4. Double-click `Open Job Board.command` — the board at http://127.0.0.1:8765/.
5. Add your first job: paste the link into `inbox.md` (or add a block to `jobs.js` by hand,
   following the fields in `AGENTS.md`), then work it through the board.

LinkedIn alerts are optional; set them up when you're ready to let the pipeline feed the board.
See `docs/linkedin-alerts.md`.

## Configuration

`config.json` (gitignored; copy from `config.example.json`):

| Key | Meaning |
|---|---|
| `worker_url` | Your job-alerts Worker, e.g. `https://your-worker.yourname.workers.dev` |
| `resume_master` | The master resume, default `resume/master.md` |
| `agent.runner` | `opencode`, `claude`, or `manual` (see `docs/agents.md`) |
| `agent.model` | Model for the opencode runner; `null` = whatever OpenCode is configured with |
| `scoring.enabled` | Pre-score alert jobs with the agent (off by default) |
| `permanent_only` | Skip contract/temp/part-time postings (on by default) |
| `chrome_path` | Path to the Chrome binary used to print the PDFs |

## How a job moves

1. **Found** — a link lands in `inbox.md` or `jobs.js` (or the alert pipeline adds it as `new`).
   Agents verify it against the source posting and set `remote` from the posting's own text.
2. **Confirmed remote** — the board's "Check remote" mode: you open the posting, read LinkedIn's
   workplace badge (Remote / Hybrid / On-site), and click. This is the gate to a packet.
3. **Packet** — "Prep application" (or "Prep packets" for a batch, 3 at a time) saves the
   posting and runs the configured agent with `tools/application-prompt.md`. You read
   `fit-check.md` first, then the letter and resume; edit the .md files and click Rebuild to
   change wording.
4. **Apply** — "Copy Chrome prompt" copies `apply-in-chrome.md`; you paste it into Claude in
   Chrome, which fills the form from `applicant-profile.md` and `answers.md`, asks you to attach
   the PDFs and handle sign-ins, and stops before Submit. You submit, then click "Mark applied".
5. **Outcomes** — Not selected (rejected), Posting expired, Not interested (passed), and so on,
   all recorded in `jobs.js` with a note. Jobs are never deleted.

The full field list and the rules agents follow are in `AGENTS.md`.

## Files

| Path | What it is |
|---|---|
| `AGENTS.md` | The rules: who you are, what you want, how agents work here |
| `CLAUDE.md` | Points Claude Code at `AGENTS.md` |
| `tracker.html` | The board (read-only as a plain file; the server makes it editable) |
| `jobs.js` | The board's data; one block per job |
| `inbox.md` | Where you drop links to postings you spot |
| `resume/master.md` | Your one-page master resume (format: `resume/README.md`) |
| `bases/README.md` | Your resume bases (the core base is the master) |
| `applicant-profile.md` | Contact details and standard form answers |
| `canned-answers.md` | Approved openers, proof blocks, closers, answers |
| `experience-bank.md` | Approved facts beyond the resume, grouped by angle |
| `config.example.json` | The configuration template |
| `tools/` | The scripts (see below) |
| `applications/<job-id>/` | One folder per applied job (gitignored) |
| `docs/linkedin-alerts.md` | Setting up the alert pipeline, how the emails get parsed, and why it never logs in to LinkedIn |
| `docs/agents.md` | The three agent runners and how to install them |
| `docs/windows.md` | Windows setup and the differences from Mac |

## The tools

| Script | Job |
|---|---|
| `tools/setup-wizard.py` | The setup wizard: walks a new Mac or Windows through every step |
| `tools/board-server.py` | Serves the board on 127.0.0.1:8765 and saves its buttons to `jobs.js` |
| `tools/jobsfile.py` | Safe, atomic edits to `jobs.js` (used by the other scripts) |
| `tools/ingest-alerts.py` | Pulls new alert emails, checks the postings, adds jobs to `jobs.js` |
| `tools/linkedin_check.py` | Reads a LinkedIn posting's public page: closed? remote? permanent? |
| `tools/prep-application.py` | Builds one application packet (or `--build-only` for manual mode) |
| `tools/agent.py` | Config loading and the three agent runners (opencode / claude / manual) |
| `tools/application-prompt.md` | The prompt the agent follows when writing a packet |
| `tools/build-resume.js` | Master resume → one-page .docx + .html (name from the resume's first line) |
| `tools/build-letter.js` | Cover letter .md → .docx + .html (header from the master resume) |
| `tools/rebuild-resume.sh` | Rebuild the master resume's .docx/.pdf and report the page count |
| `tools/job-alerts-worker/worker.js` | The Cloudflare Email Worker that stores the alert emails |

## Privacy

Everything personal lives in gitignored files: `config.json`, `applications/`, `resume/*.pdf`,
`resume/*.docx`, and the alert state. The repo itself is a template. If you make this repo
public, run a final check first: nothing in `AGENTS.md`, the profile, the canned answers, or the
experience bank should contain names, employers, addresses, or metrics you don't want public.
(This template contains none.)
