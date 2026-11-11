# Job Search Pilot

A private, local co-pilot for a job search: a job board on your own computer, an optional
automatic LinkedIn alert feed, and a per-job application workflow where an AI writes your
resume variant, cover letter, and form answers from material you've approved. You review
everything; nothing is ever submitted without you.

Runs on **Mac and Windows**. Your resume, jobs, and applications stay on your computer: the
repo holds only the tools and templates, and your own files are never committed (so you can
`git pull` updates any time without conflicts).

## What it does

- **The board**: a local web page listing your jobs in a pipeline (New → Found → Applying →
  Applied → Screen → Interview → Offer). **Add job** takes a posting's link and fills in the
  details. Score each job 1–5 on fit, company, and how much you'd like it, and move it along
  with one click. Fully remote jobs only; the rest are kept but hidden.
- **Application packets**: for each job you want, a folder with the saved posting, a one-page
  resume variant, a cover letter, draft form answers, an honest fit check, and a prompt for
  Claude in Chrome that fills the application form and stops before Submit.
- **Your choice of AI**: the writing is done by the Claude Code or OpenCode CLI, or, with no
  install at all, by any AI chat: the board gives you one prompt to paste, and you paste the
  reply back.
- **LinkedIn alerts (optional)**: LinkedIn's alert emails are forwarded to an address you own,
  stored in your own Cloudflare account, and pulled onto the board. It never logs in to
  LinkedIn, on purpose, so your account is never at risk (see `docs/linkedin-alerts.md`).
- **Closed postings leave the board on their own**: every few hours the board re-checks the
  jobs you haven't applied to yet.

## Quick start

1. **Get the folder.** With Git: `git clone https://github.com/bryan-barnes/Job-Search-Pilot.git`.
   Or download the ZIP from GitHub (Code → Download ZIP) and unzip it somewhere you'll keep it,
   like Documents.
2. **Run the setup wizard.** It checks your tools (Python, Node.js, Chrome) and tells you how to
   install anything missing, sets up your settings, makes your own copies of the files to fill
   in, test-builds your resume, and opens the board.

   | Mac (Terminal) | Windows (Command Prompt or PowerShell) |
   |---|---|
   | `cd` into the folder, then `python3 tools/setup-wizard.py` | `cd` into the folder, then `py tools\setup-wizard.py` |

   You can stop any time and run it again; it picks up where you left off.
3. **Fill in your files** (the wizard opens each one): `resume/master.md` (your one-page
   resume; format in `resume/README.md`) and `about-me.md` (who you are, what you want, your pay
   floor and voice) matter most. Then `applicant-profile.md`, `canned-answers.md`, and
   `experience-bank.md`.
4. **Open the board**: double-click `Open Job Board.command` (Mac) or `Open Job Board.bat`
   (Windows). It opens http://127.0.0.1:8765/ in your browser. Click **Add job** and paste a
   posting's link.

New to Terminal? On a Mac, open Terminal, type `cd ` (with a space), drag the folder onto the
window, and press Return. On Windows, open the folder, click the address bar, type `cmd`, and
press Enter.

**Mac, downloaded ZIP:** the first time you double-click `Open Job Board.command`, macOS may say
it's from an unidentified developer. The setup wizard clears that for you; if you skipped it,
right-click the file → Open → Open.

## How a job moves

1. **Found**: you add it with **Add job** (or the alert feed adds it as New, and you click
   Interested). Paste the employer's own posting link when you can.
2. **Confirmed remote**: "Check remote" lists jobs you haven't confirmed. Open the posting,
   check where the job is worked, and click Fully remote or Not remote. (When you add a job
   yourself and pick "Yes, fully remote", that counts.)
3. **Packet**: click the job → **Prep application** (or **Prep packets** for several, three at
   a time). Read the fit check first, then the letter and resume. To change wording, edit the
   .md files in the packet folder and click **Rebuild documents**.
4. **Apply**: **Copy Chrome prompt**, paste it into Claude in Chrome, attach the PDFs when it
   asks, and let it fill the form. It stops before Submit; you submit, then **Mark applied**.
   (Applied without a packet? **Mark applied** works on any job.)
5. **After**: Got a screen → Got an interview → Got an offer, or Not selected. Jobs are never
   deleted; each change is noted with the date.

## Configuration

`config.json` (yours, never committed; the wizard writes it from `config.example.json`):

| Key | Meaning |
|---|---|
| `agent.runner` | `manual` (paste into any AI chat), `claude`, or `opencode`. See `docs/agents.md` |
| `agent.model` | Model for the opencode runner; `null` = whatever OpenCode is set to |
| `permanent_only` | Skip contract/temp/part-time postings (on by default) |
| `scoring.enabled` | Give new alert jobs a 1–5 fit guess from the title (off by default) |
| `chrome_path` | Chrome, which prints the PDFs. Found automatically on Mac and Windows |
| `worker_url`, `worker_token` | Your LinkedIn alerts Worker, if you set one up (the wizard fills these in; on a Mac the key goes in the Keychain instead) |
| `resume_master` | The master resume, default `resume/master.md` (it can live elsewhere, e.g. `~/Documents/site/resume.md`) |
| `document_name` | The name on your PDF and Word file names, if not the resume's first line (e.g. `"Alex Doe"` gives `Alex-Doe-Resume.pdf`) |

## Files

**Yours** (created from `templates/` the first time you run anything, never committed):

| Path | What it is |
|---|---|
| `about-me.md` | Who you are, what you want, your pay and salary rule, your voice, your rules |
| `resume/master.md` | Your one-page master resume |
| `applicant-profile.md` | Contact details and standard form answers |
| `canned-answers.md` | Approved openers, proof blocks, closers, answers |
| `experience-bank.md` | Approved facts beyond the resume, grouped by angle |
| `jobs.js` | The board's data, one block per job |
| `inbox.md` | Links for an AI agent working in this folder to add for you |
| `bases/<name>/` | Optional extra resume bases (see `bases/README.md`) |
| `applications/<job-id>/` | One folder per job you prep |
| `config.json` | Your settings |

**The tools** (shared, updated with `git pull`):

| Path | What it is |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | The rules any AI agent working in this folder follows |
| `tracker.html` | The board |
| `Open Job Board.command` / `.bat` | Start the board (Mac / Windows) |
| `tools/setup-wizard.py` | The setup wizard |
| `tools/board-server.py` | Serves the board on 127.0.0.1:8765 and saves its buttons to `jobs.js` |
| `tools/prep-application.py` | Builds one application packet |
| `tools/rebuild-resume.py` | Rebuild your master resume's .docx/.pdf and check it's one page |
| `tools/application-prompt.md` | The instructions the AI follows when writing a packet |
| `tools/agent.py` | Settings, your files, and the three AI runners |
| `tools/documents.py`, `build-resume.js`, `build-letter.js` | Markdown → Word and PDF |
| `tools/jobsfile.py` | Safe, atomic edits to `jobs.js` |
| `tools/ingest-alerts.py`, `linkedin_check.py` | The LinkedIn alert feed and the posting checks |
| `tools/alerts_worker.py` | Check your alerts Worker; shows Gmail's forwarding confirmation code |
| `tools/job-alerts-worker/worker.js` | The Cloudflare Email Worker that stores the alert emails |
| `templates/` | The starting copies of your files |
| `docs/` | `agents.md` (the AI runners), `linkedin-alerts.md` (the alert feed), `windows.md` |
| `tests/smoke.py` | End-to-end test; runs on Mac and Windows in CI |

## Updating

With Git: `git pull` in the folder. Your files aren't tracked, so they're never touched. With a
ZIP: download the new ZIP and copy your files (the "Yours" table above, plus `applications/`)
into it.

## Privacy

Everything personal is gitignored: your files above, `config.json`, `applications/`, the
resume PDFs, and the alert state. The only things that leave your computer are what you
choose: the prompt and your files go to your AI provider when it writes a packet, and the
optional alert feed uses your own Cloudflare account.

## License

MIT. See `LICENSE`.
