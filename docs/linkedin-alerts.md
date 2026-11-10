# The LinkedIn alerts pipeline

How job alert emails get from LinkedIn to the board, and how to set it up.

```
LinkedIn (your saved alert)
   |  email to your inbox
   v
Gmail filter  ->  forwards to  alerts@yourdomain.com  (an address you own)
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

## 1. The LinkedIn alert

In LinkedIn, save a job alert with your search (title, location "Remote", etc.). It emails
your inbox as `Your job alert for <search>`. You'll also get one "Your alert has been created"
email with sample jobs; the pipeline skips that notice.

## 2. The forwarding filter

In Gmail, create a filter that matches the alert sender (e.g. `from:jobs-noreply@linkedin.com`
and the created-alert sender `jobalerts-noreply@linkedin.com`) and adds the action **Forward
to: alerts@yourdomain.com**. The address must be one you own and control.

The Worker only accepts mail from `@linkedin.com` addresses plus Gmail's one-time forwarding
confirmation; everything else is rejected and never stored. So the filter only has to forward
the LinkedIn mail, but any other mail sent to that address bounces.

## 3. The Cloudflare Email Worker

The code is in `tools/job-alerts-worker/worker.js`. It stores each accepted email in a KV
namespace for 30 days and serves two endpoints, both requiring a bearer token:

- `GET /list` — the stored emails (key, sender, subject)
- `GET /msg?key=...` — one email's raw text

To deploy it:

1. In the Cloudflare dashboard, create a KV namespace (any name; the binding in the code is
   `ALERTS`).
2. Create a Worker and paste in `worker.js`.
3. Bind the KV namespace to the Worker as `ALERTS`.
4. Add the secret `ALERTS_TOKEN` (any long random string; the Worker won't serve mail without
   the matching `Authorization: Bearer <token>` header).
5. Add an **Email route** for `alerts@yourdomain.com` pointing at the Worker. (Your domain has
   to be on Cloudflare, or the address has to be set up for Email Routing.)

When it's live, test it:

```
curl https://your-worker.yourname.workers.dev/list -H "Authorization: Bearer <token>"
```

That returns `[]` until the first alert email arrives.

## 4. Your side of it

1. Put the Worker key in the macOS Keychain, service name `job-alerts-worker`:

   ```
   security add-generic-password -a "$(whoami)" -s job-alerts-worker -w "<token>"
   ```

   (or `security add-generic-password -s job-alerts-worker` and type it). `ingest-alerts.py`
   reads it with `security find-generic-password -s job-alerts-worker -w`; it exits with a
   message if it's missing.
2. Set `worker_url` in `config.json` to the Worker's URL, e.g.
   `https://your-worker.yourname.workers.dev`.
3. Test the whole path without changing anything:

   ```
   python3 -I tools/ingest-alerts.py --dry-run
   ```

   It lists the new emails it parsed, the jobs it would add (with remote verdicts), and any
   open jobs it would mark expired. A real run does the same and writes to `jobs.js` and
   `alerts-state.json`.

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
