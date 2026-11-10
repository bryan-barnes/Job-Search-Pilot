# The master resume

`master.md` is the one-page source of truth. Every application packet starts from it (or from one
of the bases in `../bases/`) and gets a light per-job variant.

## Format the builders expect

`tools/build-resume.js` and `tools/build-letter.js` read specific lines, so keep this shape:

- **Line 1:** `# Your Name` — the PDF and Word files are named after this line
  (`Your-Name-Resume.pdf`, `Your-Name-Cover-Letter.pdf`).
- **Line 2:** blank.
- **Line 3:** your headline (one line).
- **Line 4:** your contact line (one line: email · phone · LinkedIn · site).
- **After that:** body, using only these building blocks:
  - `## Section` (Experience, Skills, Education)
  - `### Job Title` followed by a `**Company, City** · dates` line
  - `- ` bullets
  - plain text lines
  - `[check ...]` notes are allowed anywhere; the builders strip them

No tables, no links with markup, no images. Keep it to one page.

## Rebuilding the .docx and .pdf

```
zsh tools/rebuild-resume.sh
```

It writes `Your-Name-Resume.docx` and `Your-Name-Resume.pdf` next to `master.md` and prints the
page count. It needs `node`, Google Chrome, and `pdfinfo` (poppler).

## Rules

- Same facts in every resume variant. Never add facts to fit a posting; reorder and reword instead.
- Every number in the resume must be one you gave (see `../experience-bank.md` for the warehouse
  of approved facts beyond this page).
