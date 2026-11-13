"""Read a LinkedIn job's public page and report whether it's still open and whether it's remote.

The page text is untrusted. It is only searched with fixed patterns, never passed on as
instructions. Remote detection is a heuristic over the job title and description:

  "no"       the description mentions hybrid, on-site, or in-office work
  "yes"      the title or description says remote / telework / work from home, with no hybrid signal
  "unknown"  neither (often an on-site job that just doesn't say so)
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130 Safari/537.36")

# Phrases that describe how the job itself is worked, not perks or company names.
NOT_REMOTE = re.compile(
    r"\bhybrid[- ](?:work|working|schedule|role|position|environment|model|workplace|policy"
    r"|options?|way|arrangement|basis)|\bdesignation:?\s*hybrid|\bthis (?:is a )?hybrid"
    r"|\bon-?site (?:role|position|job|presence|requirement|work)\b|\b(?:fully|100%) on-?site"
    r"|\bin[- ]office (?:presence|requirement|days|work)|\bin[- ]person presence"
    r"|days? (?:a|per|each) week in|% of (?:work )?time in the office|in the office \d"
    r"|must (?:live|reside) within", re.I)
# Concrete in-office schedules. These win even over "Location: ... remote" lines.
SCHEDULE = re.compile(
    r"\b(?:\d|one|two|three|four) days? (?:a |per |each )?(?:week )?(?:in|at) (?:the |our |an? )?[\w ,]{0,40}office\b"
    r"|\bhybrid work schedule\b|\b(?:will|must) be based in\b|\bwithin (?:a )?reasonable commute\b", re.I)
# Clear statements that this job is remote. These win over generic hybrid language.
STRONG_REMOTE = re.compile(
    r"\blocation\b:?[^.]{0,60}\bremote\b|\b(?:fully|100%|completely) remote\b"
    r"|\b(?:role|position|job) (?:will be|is) (?:fully |100% )?remote\b"
    r"|\bremote (?:role|position|opportunity|job)\b|\bteleworking \(remote\)|\bwork 100% remotely"
    r"|\bwork location[^.]{0,40}\bvirtual\b"
    r"|\b(?:role|position|job) (?:that )?can be (?:fully |100% )?(?:remote|performed remotely|done remotely)\b"
    r"|\bopen to (?:fully )?remote (?:candidates|applicants|work)\b", re.I)
WEAK_REMOTE = re.compile(
    r"\bremote\b(?! flexibility| workers| employees| team members| staff)|\btelework|\bwork[- ]from[- ]home\b(?! stipend)|\bfully virtual\b",
    re.I)


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    """About pad characters either side of a match, cut at word boundaries."""
    a, b = max(0, start - pad), min(len(text), end + pad)
    if a > 0:
        sp = text.find(" ", a, start)
        a = sp + 1 if sp != -1 else a
    if b < len(text):
        sp = text.rfind(" ", end, b)
        b = sp if sp != -1 else b
    return text[a:b].strip()


def classify(title: str, desc: str) -> tuple[str, str]:
    """Return (remote, evidence) from a title and plain-text description."""
    def near(text, m):
        return snippet(text, m.start(), m.end())
    if re.search(r"\bremote\b", title, re.I) and not re.search(r"\bhybrid\b", title, re.I):
        return "yes", f"title: {title}"
    if re.search(r"\bhybrid\b|\bon-?site\b", title, re.I):
        return "no", f"title: {title}"
    m = SCHEDULE.search(desc)
    if m:
        return "no", near(desc, m)
    m = STRONG_REMOTE.search(desc)
    if m:
        return "yes", near(desc, m)
    m = NOT_REMOTE.search(desc)
    if m:
        return "no", near(desc, m)
    m = WEAK_REMOTE.search(desc)
    if m:
        return "yes", near(desc, m)
    return "unknown", "posting doesn't say"


def posting(job_id: str, timeout: int = 20) -> dict | None:
    """Fetch linkedin.com/jobs/view/<id> and return its title, company, location, description text,
    whether it's closed, and the remote verdict. None if the page couldn't be read."""
    req = urllib.request.Request(f"https://www.linkedin.com/jobs/view/{job_id}/",
                                 headers={"User-Agent": UA, "Accept-Language": "en-US"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            page = resp.read().decode("utf-8", "replace")
    except Exception:
        return None
    t = re.search(r'<h1[^>]*top-card-layout__title[^>]*>(.*?)</h1>', page, re.S)
    d = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', page, re.S)
    if not t and not d:
        return None  # login wall or a layout change; don't guess
    co = re.search(r'topcard__org-name-link[^>]*>(.*?)</a>', page, re.S)
    loc = re.search(r'topcard__flavor--bullet[^>]*>(.*?)</span>', page, re.S)
    title, desc = _text(t.group(1)) if t else "", _text(d.group(1)) if d else ""
    # Keep paragraph breaks for the saved copy of the posting.
    desc_md = ""
    if d:
        md = re.sub(r"<li[^>]*>", "\n- ", d.group(1))
        md = re.sub(r"<br\s*/?>|</p>|</ul>|</li>|<p[^>]*>", "\n", md)
        md = html.unescape(re.sub(r"<[^>]+>", "", md))
        desc_md = re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", md)).strip()
    location = _text(loc.group(1)) if loc else ""
    emp = re.search(r'Employment type\s*</h3>\s*<span[^>]*>(.*?)</span>', page, re.S)
    employment = _text(emp.group(1)) if emp else ""
    remote, evidence = classify(title, desc)
    if remote == "unknown" and re.fullmatch(r"(?:United States|USA|US)(?: \(Remote\))?|Remote.*", location, re.I):
        # A country-wide location is how LinkedIn usually lists remote jobs (every one we checked was).
        remote, evidence = "yes", f"LinkedIn lists the location as {location!r}, which usually means remote"
    return {
        "title": title, "company": _text(co.group(1)) if co else "",
        "location": location, "description": desc_md or desc,
        "closed": "No longer accepting applications" in page,
        "remote": remote, "evidence": evidence[:200],
        "employment": employment,
        "not_permanent": not_permanent(title, desc, employment),
    }


# This search is for full-time, permanent roles only. LinkedIn's "Employment type" catches
# most contract and part-time jobs; the wording below catches ones listed as Full-time anyway
# (Crossover posts its contractor jobs that way).
NOT_PERMANENT_TYPES = {"contract", "temporary", "part-time", "internship", "volunteer"}
NOT_PERMANENT_TITLE = re.compile(
    r"\b(?:contract(?:or)?|temporary|temp|part[- ]time|interim|fractional|freelance|consultant \(contract\))\b", re.I)
NOT_PERMANENT_TEXT = re.compile(
    r"independent contractor|contractor of record|\b1099\b|via crossover|crossover\.com"
    r"|contract[- ]to[- ]hire|fixed[- ]term (?:contract|role|position)"
    r"|(?:this|the) (?:is a )?(?:role|position|job|opportunity) is (?:a )?(?:contract|temporary|part[- ]time)"
    r"|(?:contract|temporary|part[- ]time) (?:position|role|assignment|engagement|basis|opportunity)"
    r"|\d+[- ]month (?:contract|assignment|engagement)|\$\d+(?:\.\d+)? ?(?:USD)?/ ?(?:hour|hr)\b", re.I)


def not_permanent(title: str, desc: str, employment: str = "") -> str:
    """Evidence that a job is contract, temporary, or part-time, or "" if none found."""
    if employment.lower() in NOT_PERMANENT_TYPES:
        return f"LinkedIn lists the employment type as {employment}"
    m = NOT_PERMANENT_TITLE.search(title)
    if m:
        return f'title says "{m.group(0)}"'
    m = NOT_PERMANENT_TEXT.search(desc)
    if m:
        return '"' + desc[max(0, m.start() - 60):m.end() + 60].replace("\n", " ").strip() + '"'
    return ""


REMOVED = re.compile(
    r"this job was removed|job (?:posting )?(?:has been|was) removed|no longer accepting applications"
    r"|(?:job|position|posting) (?:is|has) (?:expired|closed|been filled|no longer available)"
    r"|(?:job|position|posting) is no longer (?:available|open|active)"
    r"|the job you are looking for (?:is no longer|has been)", re.I)


def other_site_closed(url: str) -> tuple[bool, str] | None:
    """For non-LinkedIn postings (Built In, arc.dev, employer sites): (closed?, evidence), or None
    if the page couldn't be read. Only says closed on a 404/410 or an explicit removed message."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read(600_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return (True, f"page returns {exc.code}") if exc.code in (404, 410) else None
    except Exception:  # noqa: BLE001
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I)))
    m = REMOVED.search(text)
    return (True, re.sub(r"\s+", " ", text[max(0, m.start() - 40):m.end() + 60]).strip()) if m else (False, "")


def page_text(url: str, limit: int = 20000) -> str:
    """A non-LinkedIn posting page as plain text (scripts, styles, nav, and footers removed)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        page = resp.read(1_500_000).decode("utf-8", "replace")
    page = re.sub(r"<(script|style|nav|header|footer)\b.*?</\1>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()[:limit]


def lookup(url: str) -> dict:
    """Best-effort details for the board's Add job form, from a posting URL on any site:
    {role, company, location, remote, evidence, closed, not_permanent, url}. Fields it can't
    find are empty. Never raises for a page it can't read."""
    m = re.search(r"linkedin\.com/(?:.*?/)?jobs/view/(?:[^/?#]*?-)?(\d{6,})", url) \
        or re.search(r"[?&]currentJobId=(\d{6,})", url)
    if m:
        p = posting(m.group(1))
        if not p:
            return {"url": f"https://www.linkedin.com/jobs/view/{m.group(1)}/",
                    "error": "LinkedIn didn't show the public page; fill in the details yourself."}
        return {"url": f"https://www.linkedin.com/jobs/view/{m.group(1)}/", "role": p["title"],
                "company": p["company"], "location": p["location"], "remote": p["remote"],
                "evidence": p["evidence"], "closed": p["closed"], "not_permanent": p["not_permanent"]}
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read(1_500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return {"url": url, "closed": exc.code in (404, 410),
                "error": f"The page answered {exc.code}; fill in the details yourself."}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "error": f"Couldn't read the page ({exc}); fill in the details yourself."}

    def meta(prop: str) -> str:
        mm = re.search(r'<meta[^>]+(?:property|name)=["\']' + prop + r'["\'][^>]*content=["\']([^"\']*)', page, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']' + prop, page, re.I)
        return _text(mm.group(1)) if mm else ""
    title = meta("og:title")
    if not title:
        t = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        title = _text(t.group(1)) if t else ""
    company = meta("og:site_name")
    # "Director of Digital - Acme" / "Job Application for X at Acme" are common title shapes.
    at = re.match(r"(?:Job Application for )?(.+?) at (.+?)(?: [|\-–] .*)?$", title)
    if at:
        title, company = at.group(1), company or at.group(2)
    else:
        parts = re.split(r" [|\-–] ", title)
        if len(parts) > 1:
            title, company = parts[0], company or parts[1]
    body = re.sub(r"<(script|style|nav|footer)\b.*?</\1>", " ", page, flags=re.S | re.I)
    text = _text(body)
    remote, evidence = classify(title, text)
    closed = REMOVED.search(text)
    return {"url": url, "role": title[:200], "company": company[:200], "location": "",
            "remote": remote, "evidence": evidence[:200], "closed": bool(closed),
            "not_permanent": not_permanent(title, text)}


def check(job_id: str, timeout: int = 20) -> dict | None:
    """Closed / remote verdict only (used by ingest-alerts.py)."""
    p = posting(job_id, timeout)
    return p and {k: p[k] for k in ("closed", "remote", "evidence", "employment", "not_permanent")}
