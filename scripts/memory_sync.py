#!/usr/bin/env python3
"""Harness memory layer — build the machine index and regenerate the views.

The memory layer answers three questions that nothing else in this repo does:

  * which mail thread does this feature's work come from,
  * which Claude Code chat did that work, and
  * what is still owed to prod.

Sources, and how each is read:

  local (this script, no help needed)
    ~/.claude/projects/<slug>/*.jsonl   every Claude Code session for this repo
    docs/dev_to_prod_migration_todos.md dated blocks tagged [PENDING]/[DONE]/...
    docs/mindwealth_ui_job_status.md    dated DONE entries

  Gmail (--fetch-mail)
    scripts/gmail_fetch.py, run under the gmail-mcp virtualenv, which holds the
    read-only OAuth token. Metadata only, and the sender allowlist in
    ~/.gmail-mcp/filters.yaml is re-applied there, so the memory layer can never
    index mail the filter policy hides. No MCP server is involved, so this runs
    unattended from cron as happily as from a chat.

Everything written here is scrubbed first. `docs/cursor_chat_archive/` had to be
gitignored on 2026-08-18 because a live GitHub PAT reached it and blocked a
push; session titles come from the same well, so they go through SECRET_PATTERNS
before they are ever written. Prompt bodies and mail snippets are never stored —
snippets are read for feature classification, then dropped. The raw fetch lands
in docs/memory/.mail_cache.json, which is gitignored for the same reason.

Usage:
    python3 scripts/memory_sync.py                     # local sources + regen views
    python3 scripts/memory_sync.py --fetch-mail        # ... and refresh mail first
    python3 scripts/memory_sync.py --merge-mail m.json # merge an existing dump
    python3 scripts/memory_sync.py --render-only       # regen views from the index
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "docs" / "memory"
INDEX_PATH = MEMORY_DIR / "index.jsonl"
STATE_PATH = MEMORY_DIR / ".sync_state.json"

MIGRATION_DOC = BASE_DIR / "docs" / "dev_to_prod_migration_todos.md"
JOB_STATUS_DOC = BASE_DIR / "docs" / "mindwealth_ui_job_status.md"
INSTRUCTION_DOCS = BASE_DIR / "docs" / "instruction_docs"

SESSION_DIR = Path.home() / ".claude" / "projects" / "-home-ubuntu-uiv2-git-MindWealth-UI"
SESSION_CWD = "/home/ubuntu/uiv2/git/MindWealth_UI"

GMAIL_THREAD_URL = "https://mail.google.com/mail/u/0/#all/{}"


# --------------------------------------------------------------------------
# Secret scrubbing — everything written to disk passes through here.
# --------------------------------------------------------------------------

SECRET_PATTERNS = [
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "[redacted-github-pat]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[redacted-github-pat]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[redacted-github-token]"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "[redacted-anthropic-key]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}"), "[redacted-api-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted-aws-key]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), "[redacted-slack-token]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "[redacted-jwt]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "[redacted-google-key]"),
    (re.compile(r"\b[A-Fa-f0-9]{40,}\b"), "[redacted-hex]"),
]


def scrub(text: str) -> str:
    """Strip anything that looks like a credential. Applied to every stored string."""
    if not text:
        return ""
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# --------------------------------------------------------------------------
# Features. Keyword hits assign a feature when nothing more explicit exists;
# an explicit link always wins over one of these guesses.
# --------------------------------------------------------------------------

FEATURES = {
    "conviction_engine": {
        "dir": "conviction_engine_issues",
        "keywords": ["conviction", "adjusted eps", "yield trap", "dividend",
                     "tier a", "tier b", "earnings multiple", "fundamental slice"],
        "paths": ["src/conviction_engine/", "api/services/conviction_service",
                  "tests/test_conviction"],
    },
    "macro_intelligence": {
        "dir": "macro_intelligence_docs",
        "keywords": ["macro", "runic", "regime", "cftc", "ssi", "fear greed",
                     "naaim", "put/call", "put call", "mcclellan", "squeeze"],
        "paths": ["macro_intelligence/", "api/services/macro", "tests/test_macro",
                  "tests/test_ssi", "tests/test_cftc"],
    },
    "portfolio_page": {
        "dir": "portfolio_page",
        "keywords": ["portfolio", "nav", "four-book", "sizer", "eviction",
                     "ahil", "book rules", "drawdown"],
        "paths": ["src/portfolio_nav/", "api/services/portfolio_service",
                  "api/services/policy_service", "config/portfolio_",
                  "tests/test_portfolio"],
    },
    "signals_master_spec": {
        "dir": "signals_master_spec",
        "keywords": ["masterspec", "master spec", "signal quality", "composite",
                     "timeliness", "r:r", "risk reward", "reward remaining"],
        "paths": ["src/utils/signal_quality", "src/utils/quality_refresh",
                  "api/services/signal_enrichment", "tests/test_quality",
                  "tests/test_signals"],
    },
    "ai_analyst": {
        "dir": "ai_analyst",
        "keywords": ["ai analyst", "analyst page", "chatbot answer", "prompt version"],
        "paths": ["prompts/", "chatbot/", "api/services/analyst"],
    },
    "ssi_and_conviction": {
        "dir": "ssi_and_conviction_updates",
        "keywords": ["fundamental agent", "ssi update", "exclusion label"],
        "paths": ["src/conviction_engine/fundamentals"],
    },
    "chat_ques": {
        "dir": "chat_ques",
        "keywords": ["chat question", "digest", "feedback and priorities"],
        "paths": [],
    },
}

UNASSIGNED = "unassigned"

# A touched file is harder evidence than a word in a title, so it counts double.
PATH_WEIGHT = 2


def guess_feature(*texts: str, paths: set[str] | None = None) -> tuple[str, str]:
    """Return (feature, confidence). Confidence is 'inferred' or 'none'.

    Titles are thin — a 90-character first prompt often names no feature at all.
    Where a transcript tells us which files the session actually edited, that
    signal decides, and the title only breaks ties.
    """
    blob = " ".join(t.lower() for t in texts if t)
    touched = " ".join(sorted(paths)) if paths else ""

    best, best_score = UNASSIGNED, 0
    for name, spec in FEATURES.items():
        score = sum(1 for kw in spec["keywords"] if kw in blob)
        score += PATH_WEIGHT * sum(1 for p in spec.get("paths", []) if p in touched)
        if score > best_score:
            best, best_score = name, score
    return (best, "inferred") if best_score else (UNASSIGNED, "none")


# --------------------------------------------------------------------------
# Index I/O. The index is rewritten whole on every sync, sorted, so git diffs
# stay readable and the file never grows duplicate records.
# --------------------------------------------------------------------------

def load_index() -> dict[tuple[str, str], dict]:
    records: dict[tuple[str, str], dict] = {}
    if not INDEX_PATH.exists():
        return records
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        records[(rec["type"], rec["id"])] = rec
    return records


def save_index(records: dict[tuple[str, str], dict]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    order = {"thread": 0, "message": 1, "session": 2, "job": 3, "migration": 4, "link": 5}
    rows = sorted(records.values(), key=lambda r: (order.get(r["type"], 9), r["id"]))
    with INDEX_PATH.open("w", encoding="utf-8") as fh:
        for rec in rows:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def upsert(records: dict, new: list[dict]) -> int:
    """Merge new records, preserving any explicit link that a guess would overwrite."""
    changed = 0
    for rec in new:
        key = (rec["type"], rec["id"])
        old = records.get(key)
        if old == rec:
            continue
        if old and old.get("conf") == "explicit" and rec.get("conf") == "inferred":
            continue  # never let a heuristic clobber something you stamped by hand
        if old:
            merged = dict(old)
            merged.update(rec)
            rec = merged
        records[key] = rec
        changed += 1
    return changed


def stable_id(prefix: str, date: str, title: str) -> str:
    """Content-addressed id: unique per entry, and stable when the document shifts.

    Line numbers cannot be used here. Both source documents put the newest dated
    section at the top, so inserting today's entry renumbers every older line and
    would churn every id below it. Date plus a title digest survives that, while
    still separating two entries that share a date and an ordinal.
    """
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:6]
    return f"{prefix}_{date.replace('-', '')}_{digest}"


def link_id(src: str, dst: str, rel: str) -> str:
    return f"{src}--{rel}--{dst}"


def make_link(src: str, dst: str, rel: str, conf: str = "inferred", **extra) -> dict:
    return {"type": "link", "id": link_id(src, dst, rel), "from": src,
            "to": dst, "rel": rel, "conf": conf, **extra}


# --------------------------------------------------------------------------
# Source 1 — Claude Code sessions
# --------------------------------------------------------------------------

def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(p for p in parts if p)
    return ""


_PATH_KEYS = ("file_path", "path", "notebook_path")

# Repo work in this environment runs largely through Bash rather than Read/Edit,
# so the file a session touched is usually buried in a shell command string.
# Anchoring on the repo's own top-level directories keeps this from matching
# arbitrary slashes in prose.
_TOP_DIRS = ("src", "api", "chatbot", "macro_intelligence", "prompts", "tests",
             "scripts", "config", "docs", "testing")
_CMD_PATH = re.compile(
    r"\b(?:" + "|".join(_TOP_DIRS) + r")/[A-Za-z0-9_][A-Za-z0-9_./\-]*"
)


def _tool_paths(message: dict) -> set[str]:
    """Repo-relative paths this assistant turn read or wrote, from tool_use inputs."""
    found: set[str] = set()
    content = message.get("content")
    if not isinstance(content, list):
        return found
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        params = block.get("input") or {}
        if not isinstance(params, dict):
            continue
        for key in _PATH_KEYS:
            value = params.get(key)
            if isinstance(value, str) and value:
                found.add(value.replace(SESSION_CWD + "/", ""))
        command = params.get("command")
        if isinstance(command, str) and command:
            found |= set(_CMD_PATH.findall(command))
    return found


def scan_sessions() -> list[dict]:
    """One record per Claude Code session whose cwd is this repo."""
    if not SESSION_DIR.is_dir():
        return []

    out: list[dict] = []
    for path in sorted(SESSION_DIR.glob("*.jsonl")):
        session_id = path.stem
        first_prompt = ""
        prompts = 0
        timestamps: list[str] = []
        branch = cwd = ""
        touched: set[str] = set()

        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                cwd = rec.get("cwd") or cwd
                branch = rec.get("gitBranch") or branch
                if rec.get("timestamp"):
                    timestamps.append(rec["timestamp"])

                if (rec.get("type") == "user"
                        and not rec.get("isSidechain")
                        and (rec.get("origin") or {}).get("kind") == "human"):
                    prompts += 1
                    if not first_prompt:
                        first_prompt = _message_text(rec.get("message") or {})

                if rec.get("type") == "assistant":
                    touched |= _tool_paths(rec.get("message") or {})

        if cwd != SESSION_CWD or not timestamps:
            continue  # sessions from other machines/checkouts are not ours to index

        title = scrub(" ".join(first_prompt.split()))[:90] or "(no human prompt)"
        feature, conf = guess_feature(title, paths=touched)

        out.append({
            "type": "session",
            "id": session_id,
            "title": title,
            "branch": branch,
            "start": min(timestamps)[:19] + "Z" if timestamps else "",
            "end": max(timestamps)[:19] + "Z" if timestamps else "",
            "prompts": prompts,
            "feature": feature,
            "feature_conf": conf,
            "touched": sorted(touched)[:25],
            "transcript": str(path),
            "resume": f"claude --resume {session_id}",
        })
    return out


# --------------------------------------------------------------------------
# Source 2 — dev -> prod migration blocks
# --------------------------------------------------------------------------

MIGRATION_HEADING = re.compile(
    r"^##\s+(?P<date>\d{4}-\d{2}-\d{2})\s+—\s+(?P<title>.*?)\s*`\[(?P<status>[A-Z\-]+)\]`\s*$"
)


def parse_migration() -> list[dict]:
    if not MIGRATION_DOC.exists():
        return []

    lines = MIGRATION_DOC.read_text(encoding="utf-8").splitlines()
    blocks: list[dict] = []
    today = datetime.now(timezone.utc).date()

    for lineno, line in enumerate(lines, start=1):
        m = MIGRATION_HEADING.match(line)
        if not m:
            continue
        date, title, status = m.group("date"), m.group("title").strip(), m.group("status")
        feature, conf = guess_feature(title)
        try:
            age = (today - datetime.strptime(date, "%Y-%m-%d").date()).days
        except ValueError:
            age = -1

        blocks.append({
            "type": "migration",
            "id": stable_id("mig", date, title),
            "date": date,
            "title": scrub(title),
            "status": status,
            "age_days": age,
            "feature": feature,
            "feature_conf": conf,
            "anchor": f"docs/dev_to_prod_migration_todos.md#L{lineno}",
            "line": lineno,
        })

    # DEV-ONLY reverts are the class that causes a prod incident when forgotten,
    # so flag which blocks carry one rather than only counting mentions globally.
    body = "\n".join(lines)
    for block in blocks:
        start = block["line"]
        nxt = [b["line"] for b in blocks if b["line"] > start]
        end = min(nxt) if nxt else len(lines) + 1
        chunk = "\n".join(lines[start - 1:end - 1])
        # Match the status tag, not the bare word — a block whose text merely
        # says "DEV-ONLY: none" carries no revert and must not be flagged.
        block["dev_only"] = "[DEV-ONLY]" in chunk
    _ = body
    return blocks


# --------------------------------------------------------------------------
# Source 3 — job status DONE entries
# --------------------------------------------------------------------------

JOB_DATE = re.compile(r"^###\s+(?P<date>\d{4}-\d{2}-\d{2})\s*$")
JOB_ENTRY = re.compile(r"^(?P<num>\d+)\.\s+(?P<title>.+)$")
JOB_STATUS_TAG = re.compile(r"\b(SUCCESSFUL|UNSUCCESSFUL|PARTIAL)\b")


def parse_job_status() -> list[dict]:
    if not JOB_STATUS_DOC.exists():
        return []

    lines = JOB_STATUS_DOC.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    in_done = False
    current_date = ""

    for lineno, line in enumerate(lines, start=1):
        if line.startswith("## "):
            in_done = line.strip() == "## DONE"
            continue
        if not in_done:
            continue

        d = JOB_DATE.match(line)
        if d:
            current_date = d.group("date")
            continue

        e = JOB_ENTRY.match(line)
        if not e or not current_date:
            continue

        title = e.group("title").strip()
        tag = JOB_STATUS_TAG.search(title)
        feature, conf = guess_feature(title)
        out.append({
            "type": "job",
            "id": stable_id("job", current_date, title),
            "date": current_date,
            "title": scrub(title)[:200],
            "status": tag.group(1) if tag else "UNKNOWN",
            "feature": feature,
            "feature_conf": conf,
            "anchor": f"docs/mindwealth_ui_job_status.md#L{lineno}",
        })
    return out


# --------------------------------------------------------------------------
# Source 4 — mail, staged by the agent (see module docstring)
# --------------------------------------------------------------------------

GMAIL_FETCHER = BASE_DIR / "scripts" / "gmail_fetch.py"
GMAIL_PYTHON = Path("/home/ubuntu/.gmail-mcp/server/.venv/bin/python")


def fetch_mail(limit: int) -> Path:
    """Run the fetcher under the gmail-mcp virtualenv and return the dump path.

    Kept as a subprocess because only that virtualenv has the Google client
    libraries and the read-only OAuth token; importing here would force those
    into the repo's own requirements and therefore into the prod install.
    """
    if not GMAIL_PYTHON.is_file():
        raise SystemExit(f"gmail-mcp virtualenv not found at {GMAIL_PYTHON}; "
                         f"run {GMAIL_FETCHER.name} yourself and pass --merge-mail")

    out = MEMORY_DIR / ".mail_cache.json"
    subprocess.run([str(GMAIL_PYTHON), str(GMAIL_FETCHER), "--max", str(limit),
                    "--out", str(out)], check=True)
    return out


def merge_mail(path: Path) -> list[dict]:
    """Read the agent's Gmail dump: {"emails": [...]} as returned by the MCP server."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    emails = payload.get("emails", payload if isinstance(payload, list) else [])

    threads: dict[str, dict] = {}
    out: list[dict] = []

    for mail in emails:
        thread_id = mail.get("thread_id")
        message_id = mail.get("message_id")
        if not thread_id or not message_id:
            continue

        subject = scrub((mail.get("subject") or "").strip())
        snippet = scrub((mail.get("snippet") or "").strip())
        date = _mail_date(mail.get("date", ""))
        sender = scrub((mail.get("sender") or "").split("<")[0].strip())

        out.append({
            "type": "message",
            "id": message_id,
            "thread": thread_id,
            "from": sender,
            "date": date,
            "subject": subject,
        })

        t = threads.setdefault(thread_id, {
            "type": "thread", "id": thread_id, "subject": subject,
            "first": date, "last": date, "msg_count": 0,
            "url": GMAIL_THREAD_URL.format(thread_id),
        })
        t["msg_count"] += 1
        if date and (not t["first"] or date < t["first"]):
            t["first"] = date
        if date and (not t["last"] or date > t["last"]):
            t["last"] = date
        # The thread's own subject is the one without a Re: prefix.
        if subject and not subject.lower().startswith("re:"):
            t["subject"] = subject
        t.setdefault("_snippets", []).append(snippet)

    for t in threads.values():
        feature, conf = guess_feature(t["subject"], " ".join(t.pop("_snippets", []))[:2000])
        t["feature"] = feature
        t["feature_conf"] = conf
        out.append(t)

    return out


def _mail_date(raw: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(raw.split(" (")[0].strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return ""


# --------------------------------------------------------------------------
# Link inference. Everything here is conf="inferred" and is rendered as such;
# only /link-thread writes conf="explicit".
# --------------------------------------------------------------------------

STOPWORDS = {"the", "and", "for", "with", "your", "you", "our", "from", "this",
             "that", "are", "was", "has", "have", "not", "but", "all", "can",
             "checking", "implementation", "re", "fwd", "mail", "update"}


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_]{4,}", text.lower()) if w not in STOPWORDS}


def infer_links(sessions: list[dict], threads: list[dict],
                jobs: list[dict], migrations: list[dict]) -> list[dict]:
    links: list[dict] = []

    # session <-> thread: shared distinctive words, and the session started on or
    # after the thread's first message but not more than 21 days after its last.
    for session in sessions:
        s_words = _keywords(session["title"])
        if not s_words:
            continue
        for thread in threads:
            t_words = _keywords(thread["subject"])
            overlap = s_words & t_words
            if len(overlap) < 2:
                continue
            if not _within_window(session.get("start", "")[:10], thread.get("first"), thread.get("last")):
                continue
            links.append(make_link(
                f"session:{session['id']}", f"thread:{thread['id']}", "worked_on",
                evidence=sorted(overlap)[:4],
            ))

    # job / migration -> feature, so the views can group without re-guessing.
    for rec, rel in ((jobs, "logged_for"), (migrations, "owed_for")):
        for item in rec:
            if item["feature"] == UNASSIGNED:
                continue
            links.append(make_link(
                f"{item['type']}:{item['id']}", f"feature:{item['feature']}", rel,
                conf=item.get("feature_conf", "inferred"),
            ))

    return links


def _within_window(session_day: str, first: str | None, last: str | None) -> bool:
    """A chat plausibly belongs to a thread if it ran between the thread's first
    message and 21 days past its last — work usually follows the mail, so the
    trailing window matters more than the leading one."""
    if not session_day or not first:
        return False
    try:
        started = datetime.strptime(session_day, "%Y-%m-%d").date()
        opened = datetime.strptime(first, "%Y-%m-%d").date()
        closed = datetime.strptime(last or first, "%Y-%m-%d").date()
    except ValueError:
        return False
    return opened <= started and (started - closed).days <= 21


# --------------------------------------------------------------------------
# Views. All three are generated; never hand-edit them.
# --------------------------------------------------------------------------

BANNER = ("<!-- GENERATED by scripts/memory_sync.py — do not hand-edit. "
          "Delete and re-run to rebuild. -->\n")


def _by_type(records: dict, kind: str) -> list[dict]:
    return [r for r in records.values() if r["type"] == kind]


def render_map(records: dict) -> str:
    threads = sorted(_by_type(records, "thread"), key=lambda r: r.get("last", ""), reverse=True)
    sessions = {s["id"]: s for s in _by_type(records, "session")}
    links = _by_type(records, "link")

    by_thread: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    for link in links:
        if link["rel"] != "worked_on":
            continue
        sid = link["from"].split(":", 1)[1]
        tid = link["to"].split(":", 1)[1]
        if sid in sessions:
            by_thread[tid].append((sessions[sid], link.get("conf", "inferred")))

    out = [BANNER, "# Thread ↔ chat map\n",
           "Source of truth is `docs/memory/index.jsonl`; "
           "sync time is in `docs/memory/.sync_state.json`.\n",
           "*Italic* chats are heuristic matches — confirm with `/link-thread`.\n"]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for thread in threads:
        grouped[thread.get("feature", UNASSIGNED)].append(thread)

    for feature in sorted(grouped):
        out.append(f"\n## {feature}\n")
        out.append("| Thread | Last | Msgs | Claude chats |")
        out.append("|---|---|---|---|")
        for thread in grouped[feature]:
            chats = by_thread.get(thread["id"], [])
            if chats:
                rendered = "<br>".join(
                    (f"`claude --resume {s['id'][:8]}` — {s['title'][:50]}"
                     if conf == "explicit" else
                     f"*`claude --resume {s['id'][:8]}` — {s['title'][:50]}*")
                    for s, conf in sorted(chats, key=lambda c: c[0].get("start", ""))
                )
            else:
                rendered = "— none linked —"
            out.append(f"| [{thread['subject'][:60]}]({thread['url']}) "
                       f"| {thread.get('last', '')} | {thread.get('msg_count', 0)} | {rendered} |")

    orphans = [s for s in sessions.values()
               if not any(l["from"] == f"session:{s['id']}" and l["rel"] == "worked_on" for l in links)]
    out.append(f"\n## Chats with no thread linked ({len(orphans)})\n")
    out.append("| Chat | Started | Prompts | Resume |")
    out.append("|---|---|---|---|")
    for s in sorted(orphans, key=lambda r: r.get("start", ""), reverse=True):
        out.append(f"| {s['title'][:60]} | {s.get('start', '')[:10]} "
                   f"| {s.get('prompts', 0)} | `claude --resume {s['id'][:8]}` |")

    return "\n".join(out) + "\n"


def render_prod_queue(records: dict) -> str:
    migrations = _by_type(records, "migration")
    pending = sorted((m for m in migrations if m["status"] == "PENDING"),
                     key=lambda r: r.get("age_days", 0), reverse=True)
    dev_only = [m for m in pending if m.get("dev_only")]

    out = [BANNER, "# Prod queue\n",
           "Built from `docs/dev_to_prod_migration_todos.md`.\n",
           f"**{len(pending)} pending** · "
           f"**{len(dev_only)} {'carries' if len(dev_only) == 1 else 'carry'} "
           f"a DEV-ONLY revert** · "
           f"oldest **{pending[0]['age_days'] if pending else 0}d**\n"]

    if dev_only:
        out.append("\n## ⚠ Blocks carrying a DEV-ONLY revert\n")
        out.append("These hold a deliberate dev shortcut that must be undone at cutover.\n")
        out.append("| Age | Block | Feature | Anchor |")
        out.append("|---|---|---|---|")
        for m in dev_only:
            out.append(f"| {m['age_days']}d | {m['title'][:70]} | {m['feature']} | `{m['anchor']}` |")

    out.append("\n## All pending\n")
    out.append("| Age | Date | Block | Feature | Anchor |")
    out.append("|---|---|---|---|---|")
    for m in pending:
        out.append(f"| {m['age_days']}d | {m['date']} | {m['title'][:70]} "
                   f"| {m['feature']} | `{m['anchor']}` |")

    done = [m for m in migrations if m["status"] == "DONE"]
    out.append(f"\n{len(done)} block(s) marked DONE.\n")
    return "\n".join(out) + "\n"


def render_features_index(records: dict) -> str:
    threads = _by_type(records, "thread")
    sessions = _by_type(records, "session")
    jobs = _by_type(records, "job")
    migrations = _by_type(records, "migration")

    out = [BANNER, "# Feature index\n",
           "| Feature | Hub | Threads | Chats | Jobs done | Prod pending |",
           "|---|---|---|---|---|---|"]

    names = sorted(set(FEATURES) | {UNASSIGNED})
    for name in names:
        spec = FEATURES.get(name)
        hub = (f"`docs/instruction_docs/{spec['dir']}/_HUB.md`" if spec else "—")
        out.append(
            f"| {name} | {hub} "
            f"| {sum(1 for r in threads if r.get('feature') == name)} "
            f"| {sum(1 for r in sessions if r.get('feature') == name)} "
            f"| {sum(1 for r in jobs if r.get('feature') == name)} "
            f"| {sum(1 for r in migrations if r.get('feature') == name and r['status'] == 'PENDING')} |"
        )
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Feature hubs. Half generated, half yours.
#
# The generated half sits between BEGIN/END markers and is rewritten on every
# sync. Everything outside those markers is preserved verbatim, because the two
# sections that matter most — the decisions ledger and the open questions — are
# written by hand and a regeneration that ate them would make the hub useless.
# --------------------------------------------------------------------------

HUB_BEGIN = "<!-- MEMORY:BEGIN generated — rewritten by scripts/memory_sync.py -->"
HUB_END = "<!-- MEMORY:END generated -->"

HUB_TEMPLATE = """# {feature} — feature hub

> Everything known about this feature: what we were told, what we decided, what
> is still open, and which chat did the work.
>
> Sections between the generated markers are rebuilt by
> `scripts/memory_sync.py`. **Everything below "Decisions ledger" is yours** —
> the sync never touches it.

{begin}
{generated}
{end}

## Decisions ledger

Every row needs a source. `msg:<id>` points at a mail in `index.jsonl`;
`call`/`doc` are fine too, as long as the origin is named.

| Date | Decision | Source | Code ref |
|---|---|---|---|
| | | | |

## Open questions

`status`: `NOT_ASKED` (we owe Rohit the question) · `ASKED` (sent, waiting) ·
`ANSWERED` (fill the answer source). This table is the "what is communicated,
what is not" ledger — keep it honest.

| # | Question | Asked on | Channel | Status | Answer source |
|---|---|---|---|---|---|
| | | | | | |
"""


def render_hub_generated(feature: str, records: dict) -> str:
    spec = FEATURES[feature]
    feature_dir = INSTRUCTION_DOCS / spec["dir"]

    threads = sorted((r for r in _by_type(records, "thread") if r.get("feature") == feature),
                     key=lambda r: r.get("last", ""), reverse=True)
    sessions = sorted((r for r in _by_type(records, "session") if r.get("feature") == feature),
                      key=lambda r: r.get("start", ""), reverse=True)
    jobs = sorted((r for r in _by_type(records, "job") if r.get("feature") == feature),
                  key=lambda r: r.get("date", ""), reverse=True)
    migrations = sorted((r for r in _by_type(records, "migration")
                         if r.get("feature") == feature and r["status"] == "PENDING"),
                        key=lambda r: r.get("age_days", 0), reverse=True)

    out: list[str] = []

    out.append("## Spec sources\n")
    if feature_dir.is_dir():
        files = sorted((p for p in feature_dir.rglob("*")
                        if p.is_file() and p.name != "_HUB.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            out.append("| File | Type | Modified |")
            out.append("|---|---|---|")
            for f in files:
                rel = f.relative_to(BASE_DIR)
                when = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).date().isoformat()
                out.append(f"| `{rel}` | {f.suffix.lstrip('.') or 'file'} | {when} |")
        else:
            out.append("_No spec files in this directory yet._")
    else:
        out.append(f"_Directory `docs/instruction_docs/{spec['dir']}/` does not exist._")

    out.append("\n## Mail threads\n")
    if threads:
        out.append("| Thread | First | Last | Msgs |")
        out.append("|---|---|---|---|")
        for t in threads:
            out.append(f"| [{t['subject'][:65]}]({t['url']}) "
                       f"| {t.get('first', '')} | {t.get('last', '')} | {t.get('msg_count', 0)} |")
    else:
        out.append("_No mail threads classified into this feature yet._")

    out.append("\n## Claude chats\n")
    if sessions:
        out.append("| Started | Chat | Prompts | Resume |")
        out.append("|---|---|---|---|")
        for s in sessions:
            out.append(f"| {s.get('start', '')[:10]} | {s['title'][:60]} "
                       f"| {s.get('prompts', 0)} | `claude --resume {s['id'][:8]}` |")
    else:
        out.append("_No chats classified into this feature yet._")

    out.append("\n## Owed to prod\n")
    if migrations:
        out.append("| Age | Block | Anchor |")
        out.append("|---|---|---|")
        for m in migrations:
            flag = " ⚠ DEV-ONLY" if m.get("dev_only") else ""
            out.append(f"| {m['age_days']}d | {m['title'][:65]}{flag} | `{m['anchor']}` |")
    else:
        out.append("_Nothing pending for prod._")

    out.append(f"\n## Job status entries ({len(jobs)})\n")
    if jobs:
        out.append("| Date | Status | Entry | Anchor |")
        out.append("|---|---|---|---|")
        for j in jobs[:15]:
            out.append(f"| {j['date']} | {j['status']} | {j['title'][:70]} | `{j['anchor']}` |")
        if len(jobs) > 15:
            out.append(f"\n_{len(jobs) - 15} older entries — see `docs/mindwealth_ui_job_status.md`._")
    else:
        out.append("_No job status entries classified into this feature yet._")

    return "\n".join(out)


def write_hubs(records: dict) -> int:
    written = 0
    for feature, spec in FEATURES.items():
        feature_dir = INSTRUCTION_DOCS / spec["dir"]
        if not feature_dir.is_dir():
            continue

        hub = feature_dir / "_HUB.md"
        generated = render_hub_generated(feature, records)

        if hub.exists():
            text = hub.read_text(encoding="utf-8")
            if HUB_BEGIN in text and HUB_END in text:
                head, rest = text.split(HUB_BEGIN, 1)
                _, tail = rest.split(HUB_END, 1)
                text = f"{head}{HUB_BEGIN}\n{generated}\n{HUB_END}{tail}"
            else:
                # Someone removed the markers; append rather than clobber their work.
                text = f"{text}\n\n{HUB_BEGIN}\n{generated}\n{HUB_END}\n"
        else:
            text = HUB_TEMPLATE.format(feature=feature, begin=HUB_BEGIN,
                                       generated=generated, end=HUB_END)

        hub.write_text(text, encoding="utf-8")
        written += 1
    return written


def _resolve(records: dict, kind: str, needle: str) -> dict:
    """Find one record by id prefix, or by a substring of its title/subject.

    Ids are long and nobody retypes them, so `--link 88dac147 conviction` works.
    Ambiguity is an error rather than a guess — linking the wrong chat to a
    thread is worse than being asked again.
    """
    pool = _by_type(records, kind)
    hits = [r for r in pool if r["id"].startswith(needle)]
    if not hits:
        field = "title" if kind == "session" else "subject"
        low = needle.lower()
        hits = [r for r in pool if low in r.get(field, "").lower()]
    if not hits:
        raise SystemExit(f"no {kind} matching {needle!r} — run a sync first?")
    if len(hits) > 1:
        field = "title" if kind == "session" else "subject"
        listing = "\n".join(f"  {r['id'][:12]}  {r.get(field, '')[:60]}" for r in hits[:10])
        raise SystemExit(f"{needle!r} matches {len(hits)} {kind}s:\n{listing}")
    return hits[0]


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch-mail", action="store_true",
                    help="fetch Gmail metadata first (read-only, filters.yaml enforced)")
    ap.add_argument("--mail-limit", type=int, default=250,
                    help="max messages to fetch with --fetch-mail (default 250)")
    ap.add_argument("--merge-mail", type=Path,
                    help="merge an existing Gmail dump instead of fetching one")
    ap.add_argument("--render-only", action="store_true",
                    help="regenerate the views from the existing index, scrape nothing")
    ap.add_argument("--link", nargs=2, metavar=("SESSION", "THREAD"),
                    help="stamp an explicit chat<->thread link (accepts id prefixes)")
    args = ap.parse_args()

    if args.link:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        records = load_index()
        session = _resolve(records, "session", args.link[0])
        thread = _resolve(records, "thread", args.link[1])
        upsert(records, [make_link(f"session:{session['id']}", f"thread:{thread['id']}",
                                   "worked_on", conf="explicit",
                                   ts=datetime.now(timezone.utc).date().isoformat())])
        save_index(records)
        (MEMORY_DIR / "MAP.md").write_text(render_map(records), encoding="utf-8")
        write_hubs(records)
        print(f"linked chat {session['id'][:8]} ({session['title'][:50]})\n"
              f"    -> thread {thread['id']} ({thread['subject'][:50]})")
        return

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    records = load_index()

    if not args.render_only:
        sessions = scan_sessions()
        migrations = parse_migration()
        jobs = parse_job_status()
        mail_dump = args.merge_mail or (fetch_mail(args.mail_limit) if args.fetch_mail else None)
        mail: list[dict] = merge_mail(mail_dump) if mail_dump else []

        changed = upsert(records, sessions + migrations + jobs + mail)

        threads = _by_type(records, "thread")
        changed += upsert(records, infer_links(
            _by_type(records, "session"), threads, jobs, migrations))

        print(f"sessions   {len(sessions):4d}")
        print(f"migrations {len(migrations):4d}  "
              f"({sum(1 for m in migrations if m['status'] == 'PENDING')} pending)")
        print(f"jobs       {len(jobs):4d}")
        print(f"mail recs  {len(mail):4d}")
        print(f"links      {len(_by_type(records, 'link')):4d}")
        print(f"changed    {changed:4d} records")

        STATE_PATH.write_text(json.dumps({
            "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "commit": git_sha(),
            "counts": {k: len(_by_type(records, k))
                       for k in ("thread", "message", "session", "job", "migration", "link")},
        }, indent=2) + "\n", encoding="utf-8")

    save_index(records)
    (MEMORY_DIR / "MAP.md").write_text(render_map(records), encoding="utf-8")
    (MEMORY_DIR / "PROD_QUEUE.md").write_text(render_prod_queue(records), encoding="utf-8")
    (MEMORY_DIR / "features_index.md").write_text(render_features_index(records), encoding="utf-8")
    hubs = write_hubs(records)
    print(f"\nwrote {INDEX_PATH.relative_to(BASE_DIR)} + 3 views + {hubs} feature hubs")


if __name__ == "__main__":
    main()
