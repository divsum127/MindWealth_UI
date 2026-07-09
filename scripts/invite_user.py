#!/usr/bin/env python3
"""Invite a user and print their accept-invite URL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import auth_service as auth_svc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Invite user (invite-only)")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["admin", "user"], default="user")
    parser.add_argument("--users-file", default=None)
    args = parser.parse_args()

    if args.users_file:
        import os

        os.environ["USERS_FILE"] = args.users_file

    try:
        payload = auth_svc.admin_invite(email=args.email, name=args.name, role=args.role)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
