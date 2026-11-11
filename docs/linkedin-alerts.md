# The LinkedIn alerts pipeline

How job alert emails get from LinkedIn to the board, and how to set it up.

```
LinkedIn (your saved alert)
   |  email to your inbox
   v
Gmail filter  ->  forwards to  alerts@yourdomain.com  (an address on your own domain)
   v
Cloudflare Email Worker  "job-alerts"  (stores only LinkedIn mail, 30 days, read needs a token)
   v
tools/ingest-alerts.py  (fetches new mail, reads each posting's public LinkedIn page,
                         skips closed and non-permanent jobs, sets remote, adds to jobs.js)
   v
jobs.js  ->  the board (status "new", fully remote ones listed)
```

The ingest script is safe to run any time: it's a no-op when there's no new mail, and
`--dry-run` changes nothing. The board runs it for you every 3 hours between 8am and 10pm
(output in `ingest.log`); "Check for new jobs" runs it on demand.

## Why it's built this way (LinkedIn's policy)

LinkedIn's terms prohibit automated access to the site, and enforcement has locked out and
banned accounts that scrape it, especially through a logged-in session. Your account is worth
more than any single job alert, so this pipeline is designed to **never log in to LinkedIn**:

- **The alerts come from LinkedIn's own email feature.** You set up the alert as a human user,
  and LinkedIn emails it to your inbox. Reading your own mailbox is not scraping.
- **The Worker stores the emails in your own Cloudflare account.** Nothing about your LinkedIn
  account touches it; it just holds mail for 30 days.
- **The scripts only read public job pages** — the same HTML a logged-out browser gets, a few
  pages per alert batch, about one page per second. They never send a login, never use your
  cookies, and never click anything.
- **When a script can't read a page, it gives up quietly.** The job stays in the board with
  `remote: unknown` and a note. The design goal is to degrade gracefully, never to fight a
  login wall.

The only signed-in LinkedIn in the whole workflow is the manual, human-paced part: you
reading the workplace badge and you clicking Apply, in your own browser. That's normal use of
the site, not automation.

## Setting it up

The easiest way is the setup wizard's step 7 (`python3 tools/setup-wizard.py`, or
`py tools\setup-wizard.py` on Windows): it walks you through each part below, stores your key,
tests the Worker, and reads Gmail's confirmation code for you. This section is the same thing
written out.

**You need:** a domain name of your own whose DNS is on Cloudflare (the free plan is fine), so
Cloudflare can receive mail for an address like `alerts@yourdomain.com`. Gmail is assumed for
your inbox; any mail provider that can forward by rule works the same way.

The order matters: Gmail won't forward to an address until you confirm a code it sends there,
and that email arrives at the Worker. So the Worker comes first.

### 1. The Cloudflare Email Worker

The code is in `tools/job-alerts-worker/worker.js`. It stores each accepted email in a KV
namespace for 30 days and serves two endpoints, both requiring a bearer token:

- `GET /list`: the stored emails (key, sender, subject)
- `GET /msg?key=...`: one email's raw text

In the Cloudflare dashboard:

1. **Storage & Databases → KV → Create** a namespace (any name, e.g. `job-alerts`).
2. **Workers & Pages → Create → Worker**, name it `job-alerts`, deploy, then **Edit code**:
   replace everything with `worker.js` and deploy again.
3. The Worker → **Settings → Bindings → Add → KV namespace**: variable name `ALERTS`, the
   namespace from step 1.
4. The Worker → **Settings → Variables and Secrets → Add**, type **Secret**, name
   `ALERTS_TOKEN`, value: a long random string (e.g. from
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`). The Worker won't serve
   mail without the matching `Authorization: Bearer <token>` header.
5. Your domain → **Email → Email Routing** (turn it on if asked) → **Routing rules → Create
   address**: e.g. `alerts@yourdomain.com`, action **Send to a Worker** → `job-alerts`.

The Worker accepts mail only from `@linkedin.com` addresses and Gmail's forwarding
confirmation (`forwarding-noreply@google.com`); everything else is rejected and never stored.

### 2. Connect this computer to the Worker

Put the Worker's address in `config.json` as `worker_url` (e.g.
`https://job-alerts.yourname.workers.dev`), and its key:

- **Mac:** in the Keychain, service `job-alerts-worker`:
  `security add-generic-password -a "$USER" -s job-alerts-worker -w "<token>"`
  (or put it in `config.json` as `worker_token`).
- **Windows:** in `config.json` as `worker_token`. The file is never committed.

Then check it:

```
python3 tools/alerts_worker.py          (Windows: py tools\alerts_worker.py)
```

It says whether the Worker answers with your key and how many emails it holds.

### 3. Gmail forwarding, and the confirmation code

1. In Gmail: the gear → **See all settings → Forwarding and POP/IMAP → Add a forwarding
   address** → your alerts address → Next → Proceed. Gmail sends a confirmation code to that
   address, which means to the Worker.
2. Run `python3 tools/alerts_worker.py` again. It prints the **confirmation code** and the
   confirmation link from that email. (It can take a minute to arrive.)
3. Back in Gmail, on the same settings page, enter the code and click **Verify**. Leave
   "Forward a copy of incoming mail" **off**: the filter below forwards only LinkedIn's mail.

### 4. The Gmail filter

In Gmail's search box, paste:

```
from:(jobalerts-noreply@linkedin.com OR jobs-noreply@linkedin.com)
```

Click the filter icon at the right of the search box → **Create filter** → tick **Forward it
to** and choose your alerts address → **Create filter**.

### 5. The LinkedIn alert

On LinkedIn, search Jobs for what you want (title, and Remote under the location filters),
then turn on **Set alert** with email delivery. LinkedIn emails your inbox as `Your job alert
for <search>`, and the filter forwards it. You'll also get one "Your alert has been created"
email with sample jobs; the pipeline skips that notice.

### 6. Test the whole path

```
python3 -I tools/ingest-alerts.py --dry-run
```

It lists the new emails it parsed, the jobs it would add (with remote verdicts), and any open
jobs it would mark expired, and changes nothing. 0 new emails is normal until LinkedIn sends
its first alert (usually within a day). After that the board checks every 3 hours from 8am to
10pm, and **Check for new jobs** checks now.

## How the emails get parsed

`tools/ingest-alerts.py` treats the email text as untrusted data: it's only searched with
fixed patterns, never followed as instructions.

1. **Fetch.** `GET /list` from the Worker; any email whose key isn't in `alerts-state.json`
   and whose sender contains "linkedin" is new. Each is fetched with `GET /msg`.
2. **Skip notices.** Emails whose subject contains "has been created" are the alert-creation
   notice (its sample jobs ignore your filters) and are skipped.
3. **Parse jobs.** The email body is split on the rows of dashes LinkedIn puts between
   listings. Each block that ends in `View job: https://www.linkedin.com/.../jobs/view/<id>`
   is one job: the first line is the title, the second the company, the third the location.
   LinkedIn's own UI lines (alumni counts, "actively hiring", "View all jobs") are dropped.
4. **Deduplicate.** A job is dropped if its LinkedIn ID is already in `alerts-state.json`,
   already in `jobs.js`, or has the same normalized company + title already in `jobs.js`
   (the same role is often posted once per city).
5. **Read the posting.** For each new job, `tools/linkedin_check.py` fetches the public
   `linkedin.com/jobs/view/<id>` page and decides:
   - **closed** — the page says "No longer accepting applications". Closed jobs are skipped
     and recorded in the state file.
   - **remote** — a fixed-pattern heuristic over the title and description. Concrete
     in-office schedules ("3 days a week in the office", "must be based in ...") win and give
     `no`; strong statements ("fully remote", "Location: Remote", "work location is virtual")
     win over generic hybrid language and give `yes`; a bare "remote" gives `yes`; neither
     gives `unknown`. The matching phrase is saved as `evidence` and quoted in the job's
     `notes`. A country-wide location ("United States") is treated as remote, the way
     LinkedIn usually lists them. The public page has no login wall for jobs, but if LinkedIn
     changes its layout the fetch returns nothing and the job is kept with `remote: unknown`.
   - **not permanent** — LinkedIn's "Employment type" field, plus wording in the title and
     description (contractor, 1099, via Crossover, fixed-term, hourly rate). When
     `permanent_only` is on in config.json, these are skipped with a note.
6. **Optional pre-score.** With `scoring.enabled` in config.json, the configured agent sees
   only the title, company, and location of each new job (batches of 10) plus your master
   resume, and returns a skills-fit score 1-5 and a short "why" per job. It's a first pass
   from the title only; the real fit check happens in the packet. Scores are cached in
   `alerts-scores.json` so a job is scored once. The manual runner can't run headless, so
   scoring is skipped with a note when `agent.runner` is `manual`.
7. **Add to the board.** New jobs go into `jobs.js` with status `new`. Fully remote ones
   (`remote: "yes"`) are listed; the rest stay in the file behind the board's "hidden" link.
   You triage the New stage yourself: Interested (→ found) or Not interested (→ passed).
   Nothing is declined for you on fit or sector.
8. **Expiry sweep.** Each run re-checks the jobs you haven't applied to yet (status `new`,
   `found`, `applying`). LinkedIn jobs whose posting now says "No longer accepting
   applications" and other-site jobs whose page 404s or says it's removed are marked
   `expired`, which takes them off the board.

## What's stored where

| File | What |
|---|---|
| Cloudflare KV (30-day TTL) | The raw alert emails, nothing else |
| `alerts-state.json` (gitignored) | Which emails and job IDs have been seen, and why skips happened |
| `alerts-scores.json` (gitignored) | Cached pre-scores, by LinkedIn job ID |
| `ingest.log` (gitignored) | Output of the board's scheduled runs |
| `jobs.js` | The jobs, with the posting's remote evidence quoted in `notes` |
