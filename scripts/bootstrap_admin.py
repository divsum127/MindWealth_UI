#!/usr/bin/env python3
"""Create the first admin user in config/users.json."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import auth_service as auth_svc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--users-file", default=None, help="Override USERS_FILE path")
    args = parser.parse_args()

    if args.users_file:
        import os

        os.environ["USERS_FILE"] = args.users_file

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match", file=sys.stderr)
        return 1
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 1

    try:
        auth_svc.bootstrap_admin(args.email, password, name=args.name)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Admin created: {args.email.strip().lower()}")
    print(f"Users file: {auth_svc.users_file_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
