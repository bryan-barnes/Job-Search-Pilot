# Resume bases

Each application packet starts from ONE base, then gets one light variant (summary wording,
bullet order, the posting's exact phrases where they're true, and at most two approved "Resume
lines" from `../experience-bank.md` when the posting is about that topic). See
`../tools/application-prompt.md` for the full rules.

The default base is the master resume, `../resume/master.md` ("core"). Most people only need
that one.

To add another base, make a folder here, `bases/<name>/`, with:

- `resume.md`: exactly the same Markdown structure as the master (see `../resume/README.md`),
  with the same facts. Only emphasis, order, and wording differ. Never add facts to a base.
- `about.md`: one or two lines saying which jobs it's for, e.g. "Fundraising and advancement
  roles at nonprofits and universities."
- optionally `cover-letter.md`: a starting point for letters built from this base.

Examples people find useful: a fundraising/advancement version, a broader marketing-leader
version. Your base folders are gitignored, like the rest of your files.
