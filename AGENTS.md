# Your job search: rules for agents

This folder is private. Never commit it to a public repo or publish it anywhere.

## Who and what

[YOUR NAME], [current title] at [current employer] ([city], remote). Targets: [the roles you want,
e.g. Director/Senior Director roles in digital, web, and marketing technology]. Focus sectors:
[the sectors you want]. Other sectors are fine if your skills qualify.

You decide on companies yourself after reading about them: **never decline a job for you because
of its sector or company type**, including startups.

Fully remote only: not hybrid, not [your city]. [If you want full-time permanent roles only: no
contract, contractor-of-record (Crossover), temporary, interim, fractional, or part-time jobs.
`linkedin_check.not_permanent()` detects them; ingest-alerts.py skips them and prep-application.py
refuses them (config.json: `permanent_only`).]

Pay floor: [your floor]; postings at your level run [your range]. [You can't relocate right now.]

[Edit this whole section to be true for you, and date any rule you add with your name and the day:
"(You, 2026-11-10): ...". The dates keep the rules honest when you change your mind.]

Resume source: `resume/master.md`, with the one-page `Your-Name-Resume.docx`/`.pdf` beside it (the
builders name the files after the resume's first line). To rebuild the .docx/.pdf after editing the
markdown, run `tools/rebuild-resume.sh` (it must stay one page). [Private reports you want agents to
use, e.g. CliftonStrengths, go in `strengths/` (gitignored, never publish the files).]

**Every claim in an application must trace back to the master resume, a base, `canned-answers.md`,
`experience-bank.md`, or your own words in this file. Never invent metrics, titles, team sizes, or
outcomes.**

## The tracker

- `inbox.md` is where you drop links to postings you spot. Process it at the start of any
  job-search task.

- `tracker.html` is the board. You open it with `Open Job Board.command`, which starts
  `tools/board-server.py` (http://127.0.0.1:8765, this Mac only). Its buttons save to `jobs.js`:
  Interested (new → found), Not interested (→ passed), Posting expired (→ expired), Not selected
  (→ rejected, for jobs you applied to), Not fully remote / Confirmed remote, with an optional
  reason added to `notes`. **Check for new jobs** runs `tools/ingest-alerts.py` now; the board
  server also runs it every 3 hours between 8am and 10pm (output in `ingest.log`). Opened as a
  plain file, it's read-only.
- The board lists **fully remote jobs only** (`remote: "yes"`). Jobs with `remote` "no" or
  "unknown" stay in `jobs.js` but are hidden behind a link. Jobs with status `expired` never show.
- `jobs.js` holds the data. Edit it directly and keep it valid JavaScript. After any change, set
  `window.JOBS_UPDATED` to today's date.

### Fields for each job

| Field | Meaning |
|---|---|
| `id` | kebab-case, company + role, unique |
| `company`, `role` | Required |
| `pay`, `location`, `url`, `source` | Text. Mark anything unverified as "(unverified)" |
| `status` | One of: `new` (unreviewed lead from a LinkedIn alert), `found`, `applying`, `applied`, `screen`, `interview`, `offer`, `rejected` (shown as "Not selected": the employer declined to interview you or moved on after you applied), `closed` (ended after you applied for another reason), `passed` (you're not interested), `expired` (posting closed before you applied; hidden from the board) |
| `remote` | `yes` (posting says fully remote), `no` (hybrid, on-site, or tied to a metro), or `unknown`. Set it only from the posting's own text, and quote that text in `notes` |
| `fit` | 1–5: how well you match the requirements. An agent may set this |
| `co` | 1–5: how much you want to work for the company. **You set this.** Only fill it if you have said so |
| `like` | 1–5: how much you would enjoy the work. **You set this.** |
| `applied`, `lastContact`, `nextDate`, `added` | Dates as `YYYY-MM-DD` |
| `contact`, `resume`, `next`, `blocker`, `notes` | Text |

### Rules

1. **Verify before adding.** Open the posting on the employer's own careers site or ATS (Greenhouse,
   Lever, Workday) when possible. Aggregator listings go stale. Put what you couldn't verify in
   `notes` and add a `blocker`.
2. **Check fit honestly.** Name the real gaps. No cheerleading.
3. **Don't delete jobs.** Set `status` to `rejected`, `closed`, `passed`, or `expired` and say why
   in `notes`. If a posting closed before you applied, use `expired`, which takes it off the board.
4. **Writing for you** (cover letters, LinkedIn, outreach): keep your voice. Start from your own
   draft or words. [By default: avoid em dashes, "spearheaded" and "leveraged", "not just X but
   Y", and tidy three-item lists.] Reuse about five exact phrases from the posting where they're
   true.
5. **Edit jobs.js with `tools/jobsfile.py`** when scripting (`set_field`, `add_note`, `touch`). It
   changes single fields in place and writes atomically, so it's safe while the board server is
   running.

## Applications

Each job you apply to gets a packet in `applications/<job-id>/` (private, like everything here).

1. **Check remote.** The board's "Check remote" mode lists active jobs whose remote status you
   haven't confirmed. You open the posting, come back, and click Fully remote or Not remote, which
   sets `remote` and `remoteChecked`.
2. **Prep.** **Prep packets (N)** on the board lists every job you confirmed fully remote that
   isn't applied to and has no packet. All are ticked; you untick any to skip, and the server
   queues the rest (`POST /api/prep-batch`, 3 at a time; queued packets show "Packet queued"). The
   queue lives in the server, so restarting the board marks queued packets failed (Try again
   restarts them). For a single job, the dialog's "Prep application" button runs
   `tools/prep-application.py <job-id>`, which saves the posting to `posting.md`, then runs the
   configured agent (config.json → `agent.runner`: `opencode`, `claude`, or `manual`; see
   `docs/agents.md`) with `tools/application-prompt.md` to write `resume.md`, `cover-letter.md`,
   `answers.md`, and `fit-check.md`. It then builds `Your-Name-Resume.pdf/.docx`
   (`tools/build-resume.js`; it must stay one page) and `Your-Name-Cover-Letter.pdf/.docx`
   (`tools/build-letter.js`), and writes `apply-in-chrome.md`. In `manual` mode the agent step
   writes `RUN-THIS.md` (the prompt to paste into any AI assistant) and the packet waits; when the
   .md files are in the folder, **Build documents** makes the PDFs and the Chrome prompt. Progress
   goes to `status.json`, `prep.log`, and `agent.log`.
3. **Review.** You read `fit-check.md` first, then the letter and resume. To change wording, edit
   the .md files and click Rebuild (or Build documents), or ask an agent.
4. **Apply.** "Copy Chrome prompt" copies `apply-in-chrome.md`. You paste it into Claude in
   Chrome, which fills the form from `applicant-profile.md` and `answers.md`, asks you to attach
   the PDFs and handle sign-ins, and stops before Submit. You submit, then click "Mark applied".

**Experience bank.** `experience-bank.md` holds everything you've done beyond the one-page resume,
in your words, grouped by angle. When you tell an agent about your work, it adds it there with the
date, and asks you the open "Ask" questions. Letters and answers can use any entry.

**Resume bases.** `bases/README.md` lists your bases (the core base is `resume/master.md`, the
default). Each application starts from the one base that fits and gets one light variant: summary
wording, bullet order, posting phrases, and at most two approved bank "Resume lines" when the
posting is about that topic. Same facts in every base; never add facts.

`applicant-profile.md` holds standard form answers. Fields marked **[you: fill]** are yours to
decide; agents never fill them in.

## LinkedIn alerts pipeline

**Why this design:** LinkedIn's terms prohibit automated access, and accounts get locked out for
scraping, especially through a logged-in session. So this pipeline never logs in to LinkedIn: it
uses LinkedIn's own alert emails (read from your mailbox, stored in your own Cloudflare account)
and only reads public job pages, a few per run. The only signed-in LinkedIn is the manual,
human-paced part: you reading the badge and you clicking Apply. See `docs/linkedin-alerts.md`.

LinkedIn alert emails reach your inbox, and an email filter forwards them to an alerts address you
own (e.g. `alerts@yourdomain.com`). A Cloudflare Email Worker called `job-alerts` (code in
`tools/job-alerts-worker/`) stores only LinkedIn mail, for 30 days. `tools/ingest-alerts.py` pulls
new emails and reads each job's public LinkedIn page (`tools/linkedin_check.py`). It skips
postings that already closed, skips contract/temp/part-time jobs when `permanent_only` is on, sets
`remote` from the posting text, and adds the rest to `jobs.js` with status `new`. Each run also
marks jobs you haven't applied to (new, found, applying) as `expired` once LinkedIn says "No
longer accepting applications." If `scoring.enabled` is on in config.json, the configured agent
gives each job a skills-fit pre-score from the title, as a first pass only. You triage the New
stage yourself: move a job to `found` or `passed`. **Don't decline jobs for you.**

Full setup, including how the emails get parsed: `docs/linkedin-alerts.md`.

## References

[Your primary reference: name, role, relationship, and how to reach them. They know you're
looking and support you.]

**Use the source posting, not a copy.** Job aggregators (arc.dev, Built In, etc.) keep showing
postings after they close. When adding a job, store the employer's or LinkedIn's posting URL. If
only an aggregator copy exists, note that it's unconfirmed and check the employer's site before
building a packet.

**LinkedIn's workplace badge is the best remote signal.** Under the job title, signed-in LinkedIn
shows Remote, Hybrid, or On-site. The public pages the scripts read don't include it, so the
auto-check reads the description and location instead, and you confirm with the badge. When
working in a signed-in browser (Claude in Chrome), read the badge.
