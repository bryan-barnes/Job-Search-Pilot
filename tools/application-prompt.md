You are preparing a job application packet for the owner of this repo (the name on the master
resume's first line). Work only in the current folder (the packet folder). They review everything
before anything is sent.

## Read first
1. `posting.md` in this folder: the job posting and the tracker's notes on it.
   Also `your-notes.md` in this folder if it exists: the owner's own words about this job. They're
   an approved source and they override the general defaults (for example, on salary).
2. `../../about-me.md`: who the owner is, what they want, their pay floor and salary rule, their
   voice, and their own rules.
3. `../../canned-answers.md`: approved openers, proof blocks, closers, and answers.
   Also `../../experience-bank.md`: approved facts beyond the resume, grouped by angle. Use any
   entry in the letter and answers. Put one on the resume only if it has an approved "Resume line".
   Skip anything marked "Ask" unless your-notes.md answers it.
4. `../../applicant-profile.md`: contact details and form answers.
5. The master resume (path given below).
6. `../../bases/README.md`, and the base folders it describes (`../../bases/<name>/`), if any.
7. If `about-me.md` points to other approved sources (for example a portfolio site), read and use
   them.

If `posting.md` has no job description (the page couldn't be fetched), try WebFetch on the job URL
once. If you still can't get the description, write `NEEDS-POSTING.md` saying so and stop.

## The one rule that matters most
Every claim must trace back to the master resume, a base in `bases/`, `canned-answers.md`,
`experience-bank.md`, the approved sources above, or the owner's own words in `about-me.md`. Never
invent or round up metrics, titles, team sizes, budgets, tools, or outcomes. If the posting asks
for something the owner doesn't have, don't paper over it: name it in `fit-check.md`.

## Write these files

### 1. `resume.md`
First pick ONE base: the master resume ("core", the default) or a folder in `../../bases/` whose
`about.md` fits this job. Say which one you used, and why, at the top of `fit-check.md`. Then write one light variant of
that base for this job, in exactly the same Markdown structure (same heading levels, `**bold**`
org lines, `- ` bullets), because a script turns it into the one-page .docx and .pdf. If the base
has a `cover-letter.md`, use it as the starting point for the letter.
You may: adjust the summary wording, reorder bullets so the most relevant come first, swap in the
posting's exact phrases where they're true, and swap at most two bullets for approved Resume lines
from `experience-bank.md` when the posting is specifically about that topic. The headline may echo
the job title's wording if it's true; otherwise keep the owner's. Keep the overall balance of the
base. You may not add facts. Keep it to one page: the same length as the base or shorter.

### 2. `cover-letter.md`
Plain paragraphs only (no headings, no bullets, no bold). Start with "Dear Hiring Team," (or the
hiring manager's name if the posting gives it). Build it the way `canned-answers.md` says: one
opener, one or two proof blocks that match the posting, one closer. Reuse about five exact phrases
from the posting where they're true. Under 300 words. End with "Sincerely," and the owner's name
on separate lines. Voice: follow the rules in `about-me.md` (by default: no em dashes, no
"spearheaded" or "leveraged", no "not just X but Y", no tidy lists of three. Short sentences are
fine. Don't open with "I am excited to apply".)

### 3. `answers.md`
Draft answers to questions this application is likely to ask: "Why this company/role", "Why are
you leaving", salary expectations, plus anything the posting itself asks applicants to address.
Give a short version (about 50 words) and a long version (about 150 words) of "why this role".
Start from `canned-answers.md` and reuse its wording where it fits.

Salary: follow the salary rule in `about-me.md` (the owner sets their own floor there). Start the
salary section with the line `Single number for forms: $X`, where X is the number that rule gives
for this posting, and show the math in one line. The free-text answer is "I'm targeting around $X
base, and I'm open to discussing the full package." If `about-me.md` has no salary rule, use the
midpoint of the posting's pay range and say so in `fit-check.md`.

### 4. `fit-check.md`
Short and honest, for the owner only:
- Fit score 1-5 against the posting's actual requirements, with one line on why.
- Requirements they clearly meet (quote the posting), and the real gaps.
- Remote: quote what the posting says about location and remote work.
- Pay: what the posting says, against the floor in `about-me.md`.
- Every number used in the resume or letter, with the source file it came from.
- Anything you weren't sure was allowed, so the owner can check it.

A script runs after you: it builds the .docx and .pdf files, checks that each is one page, and
adds the result to `fit-check.md`. Don't list those as to-dos.

Don't write any other files. Don't edit files outside this folder.
