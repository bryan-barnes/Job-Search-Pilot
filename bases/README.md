# Resume bases

Each application packet starts from ONE base, then gets one light variant (summary wording, bullet
order, the posting's exact phrases where they're true, and at most two approved "Resume lines" from
`../experience-bank.md` when the posting is about that topic). See `../tools/application-prompt.md`
for the full rules.

| Base | Source | Use for |
|---|---|---|
| core | `../resume/master.md` | The default for most roles |

Add your own bases here: a folder `bases/<name>/` with its own `resume.md` (exactly the same
Markdown structure as the master, see `../resume/README.md`) and, optionally, a `cover-letter.md`
starting point. Examples people find useful: a fundraising/advancement version, a broader
marketing-leader version.

Same facts in every base; only emphasis, order, and wording differ. Never add facts to a base.
