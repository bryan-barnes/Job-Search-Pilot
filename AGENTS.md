# Job Search Pilot: rules for agents

**Read `about-me.md` first.** It says who the owner of this folder is, what they're looking for,
their pay floor and salary rule, their voice, and their own rules. Where it disagrees with this
file, `about-me.md` wins. (If it doesn't exist yet, run `python3 tools/setup-wizard.py`, or copy
`templates/about-me.md` and fill it in.)

This folder is private. The tools are a public template, but the owner's files (listed under
"Their files" below) are gitignored and must never be committed or published.

**Every claim in an application must trace back to the master resume, a base,
`canned-answers.md`, `experience-bank.md`, or the owner's own words in `about-me.md`. Never
invent metrics, titles, team sizes, or outcomes.**

## Their files

| File | What |
|---|---|
| `about-me.md` | Who they are, targets, pay, voice, references, their own rules |
| `resume/master.md` | The one-page master resume. Format: `resume/README.md`. Rebuild the .docx/.pdf with `python3 tools/rebuild-resume.py` (it must stay one page) |
| `bases/<name>/resume.md` | Other resume bases, if any (see `bases/README.md`) |
| `applicant-profile.md` | Standard form answers. Fields marked **[you: fill]** are theirs to decide; never fill them in |
| `canned-answers.md` | Approved openers, proof blocks, closers, and answers |
| `experience-bank.md` | Approved facts beyond the resume, in their words, grouped by angle |
| `jobs.js` | The board's data (see below) |
| `inbox.md` | Links they've dropped for an agent to add |
| `applications/<job-id>/` | One packet per job |
| `config.json` | Settings (agent runner, Worker, Chrome path) |

The tools create any missing file from `templates/` the first time they run.

## The tracker

- `inbox.md` is where the owner drops links to postings. Process it at the start of any
  job-search task: verify each link, add the job to `jobs.js`, then delete the line.
- The board is `tracker.html`, opened with `Open Job Board.command` (Mac) or `Open Job
  Board.bat` (Windows), which start `tools/board-server.py` (http://127.0.0.1:8765, this
  computer only). Its buttons save to `jobs.js`: **Add job**, Interested (new → found), Not
  interested (→ passed), Posting expired (→ expired), Mark applied, the next stage (Screen,
  Interview, Offer), Not selected (→ rejected), Not fully remote / Confirmed remote, and the
  three 1–5 scores. An optional reason is added to `notes`. **Check for new jobs** runs
  `tools/ingest-alerts.py` now when LinkedIn alerts are set up; the board server also runs it
  every 3 hours between 8am and 10pm (output in `ingest.log`). Opened as a plain file, the
  board is read-only.
- The board lists **fully remote jobs only** (`remote: "yes"`). Jobs with `remote` "no" or
  "unknown" stay in `jobs.js` but are hidden behind a link. Jobs with status `expired` never show.
- `jobs.js` holds the data. Keep it valid JavaScript, in the exact block format shown at the top
  of the file (2-space block indent, 4-space fields, one field per line, unquoted keys). The
  board can only edit jobs written that way, and marks any it can't. After any change, set
  `window.JOBS_UPDATED` to today's date.

### Fields for each job

| Field | Meaning |
|---|---|
| `id` | kebab-case, company + role, unique |
| `company`, `role` | Required |
| `pay`, `location`, `url`, `source` | Text. Mark anything unverified as "(unverified)" |
| `status` | One of: `new` (unreviewed lead from a LinkedIn alert), `found`, `applying`, `applied`, `screen`, `interview`, `offer`, `rejected` (shown as "Not selected": the employer declined to interview them or moved on after they applied), `closed` (ended after they applied for another reason), `passed` (they're not interested), `expired` (posting closed before they applied; hidden from the board) |
| `remote` | `yes` (posting says fully remote), `no` (hybrid, on-site, or tied to a metro), or `unknown`. Set it only from the posting's own text, and quote that text in `notes` |
| `remoteChecked` | Date the owner confirmed `remote` themselves. Only the owner sets this (the board does it) |
| `fit` | 1–5: how well they match the requirements. An agent may set this |
| `co` | 1–5: how much they want to work for the company. **The owner sets this.** |
| `like` | 1–5: how much they would enjoy the work. **The owner sets this.** |
| `applied`, `lastContact`, `nextDate`, `added` | Dates as `YYYY-MM-DD` |
| `contact`, `resume`, `next`, `blocker`, `notes` | Text |

### Rules

1. **Verify before adding.** Open the posting on the employer's own careers site or ATS
   (Greenhouse, Lever, Workday) when possible. Aggregator listings go stale. Put what you
   couldn't verify in `notes` and add a `blocker`.
2. **Check fit honestly.** Name the real gaps. No cheerleading.
3. **Don't delete jobs.** Set `status` to `rejected`, `closed`, `passed`, or `expired` and say why
   in `notes`. If a posting closed before they applied, use `expired`, which takes it off the
   board.
4. **Writing for them** (cover letters, LinkedIn, outreach): keep their voice, as described in
   `about-me.md`. Start from their own draft or words. Reuse about five exact phrases from the
   posting where they're true.
5. **Edit jobs.js with `tools/jobsfile.py`** when scripting (`add_job`, `set_field`, `add_note`,
   `touch`). It changes single fields in place and writes atomically, so it's safe while the
   board server is running.
6. **Never decline a job for them** because of its sector or company type. They triage.

## Applications

Each job they apply to gets a packet in `applications/<job-id>/`.

1. **Check remote.** The board's "Check remote" mode lists active jobs whose remote status they
   haven't confirmed. They open the posting, come back, and click Fully remote or Not remote,
   which sets `remote` and `remoteChecked`.
2. **Prep.** **Prep packets (N)** on the board lists every job confirmed fully remote that isn't
   applied to and has no packet; the server queues the ticked ones, 3 at a time. For a single
   job, the dialog's "Prep application" button runs `tools/prep-application.py <job-id>`, which
   saves the posting to `posting.md`, then runs the configured agent (config.json →
   `agent.runner`: `opencode`, `claude`, or `manual`; see `docs/agents.md`) with
   `tools/application-prompt.md` to write `resume.md`, `cover-letter.md`, `answers.md`, and
   `fit-check.md`. It then builds `<Name>-Resume.pdf/.docx` and `<Name>-Cover-Letter.pdf/.docx`
   (each must stay one page) and writes `apply-in-chrome.md`. In `manual` mode the agent step
   writes `RUN-THIS.md`, one self-contained prompt with every source file inside it; the owner
   pastes it into any AI assistant, pastes the reply back into the board, and the board splits
   it into the four files and builds the documents.
3. **Review.** They read `fit-check.md` first, then the letter and resume. To change wording,
   they edit the .md files and click Rebuild documents, or ask an agent.
4. **Apply.** "Copy Chrome prompt" copies `apply-in-chrome.md`. They paste it into Claude in
   Chrome, which fills the form from `applicant-profile.md` and `answers.md`, asks them to
   attach the PDFs and handle sign-ins, and stops before Submit. They submit, then click "Mark
   applied".

**Experience bank.** When the owner tells you about their work, add it to `experience-bank.md`
with the date, in their words, and ask them the open "Ask" questions. Letters and answers can
use any entry.

**Resume bases.** Each application starts from the one base that fits (the core base is
`resume/master.md`, the default) and gets one light variant: summary wording, bullet order,
posting phrases, and at most two approved bank "Resume lines" when the posting is about that
topic. Same facts in every base; never add facts.

## LinkedIn alerts pipeline (optional)

**Why this design:** LinkedIn's terms prohibit automated access, and accounts get locked out for
scraping, especially through a logged-in session. So this pipeline never logs in to LinkedIn:
it uses LinkedIn's own alert emails (forwarded to an address the owner controls and stored in
their own Cloudflare account) and only reads public job pages, a few per run. The only signed-in
LinkedIn is the manual, human-paced part: the owner reading the badge and clicking Apply. See
`docs/linkedin-alerts.md`.

`tools/ingest-alerts.py` pulls new alert emails from the Worker and reads each job's public
LinkedIn page (`tools/linkedin_check.py`). It skips postings that already closed, skips
contract/temp/part-time jobs when `permanent_only` is on, sets `remote` from the posting text,
and adds the rest to `jobs.js` with status `new`. Each run (even without alerts set up) also
marks jobs they haven't applied to (new, found, applying) as `expired` once the posting says it's
closed. If `scoring.enabled` is on, the configured agent gives each new job a skills-fit
pre-score from the title, as a first pass only.

**Use the source posting, not a copy.** Job aggregators (arc.dev, Built In, etc.) keep showing
postings after they close. Store the employer's or LinkedIn's posting URL. If only an aggregator
copy exists, note that it's unconfirmed and check the employer's site before building a packet.

**LinkedIn's workplace badge is the best remote signal.** Under the job title, signed-in
LinkedIn shows Remote, Hybrid, or On-site. The public pages the scripts read don't include it,
so the auto-check reads the description and location instead, and the owner confirms with the
badge. When working in a signed-in browser (Claude in Chrome), read the badge.
