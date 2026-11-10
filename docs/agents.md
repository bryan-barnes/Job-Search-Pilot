# The agent runners

The writing in this setup (application packets, optional alert pre-scoring, trim passes) is
done by an AI agent through one of three runners, chosen in `config.json` under
`agent.runner`. All three are driven by the same prompt files, so the output doesn't depend on
which one you pick. `tools/agent.py` runs them; nothing in this repo talks to an LLM API
directly.

## The three runners

### `opencode` — the OpenCode CLI

The most flexible: any provider or model you've configured for OpenCode.

- Install: `npm install -g opencode-ai` (or the installer in OpenCode's docs), then `opencode`
  once to log in to your provider.
- Config: `agent.runner: "opencode"`, and `agent.model` — `null` uses whatever OpenCode is
  configured with, or a specific `provider/model` ID (run `opencode models` to list them).
- How it runs: `opencode run --auto --archived --model <model> <prompt>` with the packet
  folder as the working directory. `--auto` accepts its file tools; `--archived` keeps the
  session out of your normal list. Its permissions come from your OpenCode config
  (`~/.config/opencode/opencode.json`): the prompt needs file reads/edits in the packet
  folder and, for one fallback, webfetch. No browser.

### `claude` — the Claude Code CLI

Good if you already have a Claude subscription you want to spend on this.

- Install: `npm install -g @anthropic-ai/claude-code`, then `claude` once to log in.
- Config: `agent.runner: "claude"`. (`agent.model` is ignored.)
- How it runs: `claude -p <prompt> --permission-mode acceptEdits` with the packet folder as
  the working directory. `acceptEdits` lets it write the packet files without asking; it has
  no browser and can't leave the folder the prompt points at.

### `manual` — no CLI, you paste the prompt

Works with any AI assistant, including the web versions of Claude or ChatGPT.

- Config: `agent.runner: "manual"`. No CLI needed; `setup.sh` won't warn you about one.
- How it works: instead of running anything, the script writes the full prompt to
  `RUN-THIS.md` in the packet folder and the packet waits in `manual` state. You open
  `RUN-THIS.md`, paste it into your assistant (give it the packet folder's files, or the
  assistant's file access), and tell it to work only in that folder. When the four files
  (`resume.md`, `cover-letter.md`, `answers.md`, `fit-check.md`) are in the folder, click
  **Build documents** on the board and the PDFs and the Chrome prompt are built the same way
  as in the other modes.
- Trade-offs: the one-page trim pass can't run (there's no agent to ask), so the build check
  just reports the page counts; and alert pre-scoring is skipped.

## What the agent may touch

Whatever the runner, the working directory is the packet folder (or a scratch directory for
scoring), and the prompts tell the agent to work only there. The prompt
(`tools/application-prompt.md`) fixes the sources it may claim from: the master resume, the
bases, `canned-answers.md`, `experience-bank.md`, and the owner's own words in `AGENTS.md`. It
must not invent metrics, and it must write `fit-check.md` naming the real gaps. You review
every file before anything is sent, and Claude in Chrome stops before Submit.

## Privacy notes

- In `opencode`/`claude` mode the prompt and your resume go to that provider's API. Pick a
  provider whose data terms you're comfortable with, and keep the files in this folder
  gitignored (they are: `applications/`, `config.json`, `resume/*.pdf`, `resume/*.docx`).
- In `manual` mode you control exactly which assistant sees the files.
- The alert pre-scoring (off by default) sends only job titles, companies, and locations plus
  your master resume.
- Nothing here is submitted anywhere. The scripts have no access to application forms; the
  only step that touches a form is you, pasting the Chrome prompt, with Claude in Chrome
  stopping before Submit.
