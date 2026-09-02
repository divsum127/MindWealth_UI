#!/usr/bin/env python3
"""Fetch Gmail thread metadata for the memory layer. Read-only.

Run under the gmail-mcp server's virtualenv, which already holds the Google
client libraries and the OAuth token:

    /home/ubuntu/.gmail-mcp/server/.venv/bin/python scripts/gmail_fetch.py

`scripts/memory_sync.py` shells out to this rather than importing it, so the
repo's own virtualenv and `requirements.txt` gain no Google dependency and the
prod install is unchanged.

Two rules this script does not get to relax:

  * It reuses `~/.gmail_mcp/token.json`, whose only scope is `gmail.readonly`.
  * It re-applies `~/.gmail-mcp/filters.yaml` — the sender allowlist, the
    date floor and the subject exclusions — so the memory layer can never
    index mail that the filter policy hides from the assistant. The filter is
    ANDed with any caller query, exactly as the MCP server does it.

Only headers are requested (`format=metadata`). Bodies are never fetched.
Output is `{"emails": [...]}` on stdout, shaped like the MCP server's reply.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import yaml

TOKEN_PATH = Path.home() / ".gmail_mcp" / "token.json"
FILTER_PATH = Path.home() / ".gmail-mcp" / "filters.yaml"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
HEADERS = ["From", "Subject", "Date", "To"]


def load_credentials() -> Credentials:
    if not TOKEN_PATH.is_file():
        sys.exit(f"no Gmail token at {TOKEN_PATH} — authorise the gmail-mcp server first")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        sys.exit("Gmail token invalid and could not be refreshed — re-authorise gmail-mcp")
    return creds


def filter_query() -> str:
    """Rebuild the allowlist query from filters.yaml. Never widened by a caller."""
    if not FILTER_PATH.is_file():
        sys.exit(f"no filter config at {FILTER_PATH} — refusing to query unfiltered")

    cfg = yaml.safe_load(FILTER_PATH.read_text(encoding="utf-8")) or {}
    filters = cfg.get("filters") or {}

    senders = [s for s in (filters.get("from_addresses") or []) if s]
    if not senders:
        sys.exit("filters.yaml has an empty sender allowlist — refusing to query unfiltered")

    parts = []
    if len(senders) == 1:
        parts.append(f"from:{senders[0]}")
    else:
        # Gmail's {a b} braces mean OR.
        parts.append("{" + " ".join(f"from:{s}" for s in senders) + "}")

    for label in filters.get("labels") or []:
        parts.append(f"label:{label}")
    if filters.get("date_after"):
        parts.append("after:" + str(filters["date_after"]).replace("-", "/"))
    for term in filters.get("subject_exclude") or []:
        parts.append(f'-subject:"{term}"')

    return " ".join(parts)


def header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def fetch(service, query: str, limit: int) -> list[dict]:
    emails: list[dict] = []
    page_token = None

    while len(emails) < limit:
        resp = service.users().messages().list(
            userId="me", q=query, maxResults=min(500, limit - len(emails)),
            pageToken=page_token,
        ).execute()

        ids = [m["id"] for m in resp.get("messages", [])]
        for message_id in ids:
            msg = service.users().messages().get(
                userId="me", id=message_id, format="metadata",
                metadataHeaders=HEADERS,
            ).execute()
            payload = msg.get("payload", {})
            emails.append({
                "message_id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "sender": header(payload, "From"),
                "subject": header(payload, "Subject"),
                "date": header(payload, "Date"),
                "snippet": msg.get("snippet", ""),
                "labels": msg.get("labelIds", []),
            })
            if len(emails) >= limit:
                break

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return emails


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", default="", help="extra Gmail query, ANDed with the filter")
    ap.add_argument("--max", type=int, default=200, help="max messages to fetch")
    ap.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    args = ap.parse_args()

    query = filter_query()
    if args.query:
        query = f"{query} ({args.query})"

    service = build("gmail", "v1", credentials=load_credentials(), cache_discovery=False)
    emails = fetch(service, query, args.max)

    payload = {"applied_query": query, "count": len(emails), "emails": emails}
    text = json.dumps(payload, ensure_ascii=False, indent=1)

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"{len(emails)} messages -> {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
