#!/usr/bin/env python3
"""Check your job-alerts Worker, and read Gmail's forwarding confirmation code from it.

Usage:  python3 tools/alerts_worker.py        (Windows: python tools\\alerts_worker.py)

When you add your alerts address as a forwarding address in Gmail, Gmail emails a confirmation
code to that address. The Worker stores that one email (it accepts only LinkedIn mail and
Gmail's confirmation), so this script fetches it and prints the code and the confirmation link.
It also tells you whether the Worker answers, and how many emails it's holding.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
from email import message_from_bytes, policy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent  # noqa: E402
import jobsfile  # noqa: E402

GOOGLE = "forwarding-noreply@google.com"


def list_messages(cfg: dict, token: str | None = None) -> list[dict]:
    return json.loads(agent.worker_get(cfg, "/list", token=token))


def body_text(raw: bytes) -> tuple[str, str]:
    msg = message_from_bytes(raw, policy=policy.default)
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    return str(msg.get("subject", "")), text


def forwarding_confirmation(cfg: dict, token: str | None = None) -> dict | None:
    """The newest Gmail forwarding confirmation the Worker holds: {code, link, subject}."""
    msgs = [m for m in list_messages(cfg, token) if m.get("from", "").lower() == GOOGLE]
    if not msgs:
        return None
    newest = sorted(msgs, key=lambda m: m["key"])[-1]
    subject, text = body_text(agent.worker_get(cfg, "/msg", {"key": newest["key"]}, token=token))
    code = re.search(r"Confirmation code:\s*(\d+)", text) or re.search(r"\(#(\d+)\)", subject)
    link = re.search(r"https://mail(?:-settings)?\.google\.com/mail/\S+", text)
    return {"code": code.group(1) if code else "", "link": link.group(0).rstrip(".>)") if link else "",
            "subject": subject}


def connection_problem(cfg: dict, token: str | None) -> str | None:
    """None if the Worker answers with this key, else a plain-language reason."""
    try:
        list_messages(cfg, token)
        return None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ("The Worker answered 'Not found'. Either the key doesn't match its ALERTS_TOKEN "
                    "secret, or the address isn't the Worker's.")
        return f"The Worker answered with an error ({exc.code})."
    except (urllib.error.URLError, OSError) as exc:
        return f"Couldn't reach the Worker at {cfg.get('worker_url')} ({exc})."
    except ValueError:
        return ("The address answered, but not like the job-alerts Worker. Check that you pasted "
                "tools/job-alerts-worker/worker.js into it and bound the ALERTS namespace.")


def main() -> None:
    jobsfile.utf8_stdio()
    cfg = agent.load_config()
    if not agent.alerts_configured(cfg):
        sys.exit("config.json has no worker_url yet. Run tools/setup-wizard.py (step 7).")
    token = agent.worker_token(cfg)
    problem = connection_problem(cfg, token)
    if problem:
        sys.exit(problem)
    msgs = list_messages(cfg, token)
    linkedin = sum("linkedin" in m.get("from", "") for m in msgs)
    print(f"The Worker answers. It holds {len(msgs)} email(s): {linkedin} from LinkedIn.")
    conf = forwarding_confirmation(cfg, token)
    if conf:
        print(f"\nGmail forwarding confirmation: {conf['subject']}")
        print(f"  Confirmation code: {conf['code'] or '(not found; open the link)'}")
        if conf["link"]:
            print(f"  Or open this link to confirm: {conf['link']}")
    else:
        print("\nNo Gmail forwarding confirmation yet. (In Gmail: Settings -> See all settings -> "
              "Forwarding and POP/IMAP -> Add a forwarding address. Then run this again.)")


if __name__ == "__main__":
    main()
