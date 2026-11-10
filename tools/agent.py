"""Run prompts through the configured agent, and read config.json.

Three runners (config.json -> agent.runner):
  "opencode"  the OpenCode CLI, with whatever provider/model you've configured for it
  "claude"    the Claude Code CLI, logged in with your Claude account (subscription works)
  "manual"    no CLI: writes the prompt to RUN-THIS.md so you can paste it into Claude,
              ChatGPT, or any other assistant

The agent only ever runs with the packet folder (or a scratch dir) as its working directory,
and the prompts tell it to work only there. Nothing here talks to an LLM API directly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
CONFIG = HOME / "config.json"
RUNNERS = ("opencode", "claude", "manual")


def load_config() -> dict:
    if not CONFIG.exists():
        sys.exit(f"No config.json in {HOME}. Copy config.example.json to config.json and fill "
                 "it in (see README.md).")
    cfg = json.loads(CONFIG.read_text())
    runner = cfg.get("agent", {}).get("runner", "manual")
    if runner not in RUNNERS:
        sys.exit(f"config.json: agent.runner must be one of {RUNNERS} (got {runner!r}).")
    return cfg


def runner_name(cfg: dict) -> str:
    return cfg.get("agent", {}).get("runner", "manual")


def worker_token(cfg: dict) -> str:
    """The job-alerts Worker's read key. On macOS, from the Keychain (service
    job-alerts-worker); on any platform, from config.json's worker_token (gitignored, so it's
    safe on Windows, which has no Keychain equivalent here)."""
    tok = str(cfg.get("worker_token", "") or "").strip()
    if tok and "YOUR-" not in tok.upper():
        return tok
    if sys.platform == "darwin":
        out = subprocess.run(
            ["security", "find-generic-password", "-s", "job-alerts-worker", "-w"],
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    sys.exit("No Worker key. On a Mac, add it to the Keychain (service job-alerts-worker); "
             "on Windows, set worker_token in config.json. See docs/linkedin-alerts.md.")


def executable(cfg: dict) -> str | None:
    runner = runner_name(cfg)
    if runner == "opencode":
        return shutil.which("opencode")
    if runner == "claude":
        return shutil.which("claude")
    return None


def check(cfg: dict) -> str | None:
    """An error message if the configured runner can't run, else None."""
    runner = runner_name(cfg)
    if runner == "manual":
        return None
    if not executable(cfg):
        return (f"config.json says agent.runner is {runner!r}, but the {runner} CLI is not on "
                f"your PATH. Install it (see docs/agents.md) or set agent.runner to \"manual\".")
    return None


def run_prompt(cfg: dict, prompt: str, cwd: Path, log: Path, timeout: int = 1800) -> str:
    """Run the prompt through the configured agent; output goes to log.

    Returns the runner used. For "manual" it writes the prompt to cwd/RUN-THIS.md and returns
    "manual" without running anything.
    """
    runner = runner_name(cfg)
    cwd = Path(cwd)
    if runner == "manual":
        (cwd / "RUN-THIS.md").write_text(prompt)
        return "manual"
    exe = executable(cfg)
    if not exe:
        raise RuntimeError(check(cfg) or f"{runner} CLI not found")
    if runner == "opencode":
        cmd = [exe, "run", "--auto", "--archived"]
        model = cfg.get("agent", {}).get("model")
        if model:
            cmd += ["--model", model]
        cmd.append(prompt)
    else:  # claude
        cmd = [exe, "-p", prompt, "--permission-mode", "acceptEdits"]
    with open(log, "w") as f:
        r = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                           stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{runner} exited {r.returncode}; see {log.name}")
    return runner


def extract_json_results(text: str) -> list[dict] | None:
    """Find a JSON object with a "results" array in agent output, tolerating prose and
    markdown fences around it (one-line or pretty-printed). Returns the list, or None."""
    start = text.find("{")
    while start != -1:
        end = text.rfind("}")
        while end > start:
            try:
                data = json.loads(text[start:end + 1])
            except ValueError:
                end = text.rfind("}", start, end)
                continue
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                return data["results"]
            break
        start = text.find("{", start + 1)
    return None
