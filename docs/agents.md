# The agent runners

The writing in this setup (application packets, optional alert pre-scoring, trim passes) is
done by an AI agent through one of three runners, chosen in `config.json` under
`agent.runner`. All three are driven by the same prompt files, so the output doesn't depend on
which one you pick. `tools/agent.py` runs them; nothing in this repo talks to an LLM API
directly.

## The three runners

### `manual`: no install, any AI chat (the default)

Works with any AI assistant, including Claude or ChatGPT in the browser.

- Config: `agent.runner: "manual"`.
- How it works: **Prep application** saves the posting and writes `RUN-THIS.md` in the packet
  folder: one self-contained prompt with the instructions and every file the AI needs (the
  posting, `about-me.md`, your canned answers, experience bank, profile, master resume, and any
  bases) pasted inside it. On the board, click **Copy the prompt**, paste it into a new chat,
  and send it. The AI replies with four sections, each starting with a line like
  `@@@ FILE: resume.md @@@`. Copy its whole reply, paste it into the box on the board, and
  click **Save reply and build**: the board splits it into `resume.md`, `cover-letter.md`,
  `answers.md`, and `fit-check.md`, then builds the PDFs and the Chrome prompt.
- If you'd rather write the files yourself (or with an AI that has file access), put them in
  the packet folder and click **Build documents**.
- Trade-offs: the one-page trim pass can't run (there's no agent to ask), so the build check
  just reports the page counts; and alert pre-scoring is skipped.

### `claude`: the Claude Code CLI

Good if you have a Claude subscription and want the packets written for you.

- Install: see https://docs.claude.com/en/docs/claude-code (native installer, or
  `npm install -g @anthropic-ai/claude-code`), then run `claude` once to log in.
- Config: `agent.runner: "claude"`. (`agent.model` is ignored.)
- How it runs: `claude -p --permission-mode acceptEdits` with the packet folder as the working
  directory and the prompt on stdin. `acceptEdits` lets it write the packet files without
  asking. It has no browser.

### `opencode`: the OpenCode CLI

The most flexible: any provider or model you've configured for OpenCode, including local ones.

- Install: `npm install -g opencode-ai` (or the installer in OpenCode's docs), then `opencode`
  once to set up your provider.
- Config: `agent.runner: "opencode"`, and `agent.model`: `null` uses whatever OpenCode is
  configured with, or a specific `provider/model` ID (run `opencode models` to list them).
- How it runs: `opencode run --auto --archived --file PROMPT.md "Follow the instructions in the
  attached file PROMPT.md."` with the packet folder as the working directory (the prompt file
  is deleted afterwards). `--auto` accepts its file tools; `--archived` keeps the session out
  of your normal list. Its permissions come from your OpenCode config: the prompt needs file
  reads and edits in the packet folder and, for one fallback, webfetch.

The prompt never goes on the command line, because on Windows the CLIs are `.cmd` wrappers and
a multi-line argument gets cut off there.

## What the agent may touch

Whatever the runner, the working directory is the packet folder (or a scratch directory for
scoring), and the prompts tell the agent to work only there. The prompt
(`tools/application-prompt.md`) fixes the sources it may claim from: the master resume, the
bases, `canned-answers.md`, `experience-bank.md`, and the owner's own words in `about-me.md`. It
must not invent metrics, and it must write `fit-check.md` naming the real gaps. You review
every file before anything is sent, and Claude in Chrome stops before Submit.

## Privacy notes

- In `opencode`/`claude` mode the prompt and your resume go to that provider's API. Pick a
  provider whose data terms you're comfortable with, and keep your files private
  (they're gitignored: your files from `templates/`, `applications/`, `config.json`, the PDFs).
- In `manual` mode you control exactly which assistant sees the files.
- The alert pre-scoring (off by default) sends only job titles, companies, and locations plus
  your master resume.
- Nothing here is submitted anywhere. The scripts have no access to application forms; the
  only step that touches a form is you, pasting the Chrome prompt, with Claude in Chrome
  stopping before Submit.
