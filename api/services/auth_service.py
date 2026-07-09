"""User authentication and invite management."""

from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

_ROOT = Path(__file__).resolve().parents[2]
_USERS_FILE = Path(os.getenv("USERS_FILE", str(_ROOT / "config" / "users.json")))
_INVITE_BASE_URL = os.getenv("INVITE_BASE_URL", "http://localhost:8512").rstrip("/")
_JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-in-production")
_JWT_ALGORITHM = "HS256"
_JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "60"))
_INVITE_EXPIRE_DAYS = int(os.getenv("INVITE_EXPIRE_DAYS", "7"))

UserStatus = Literal["invited", "active", "disabled"]
UserRole = Literal["admin", "user"]


def users_file_path() -> Path:
    return _USERS_FILE


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


_file_lock = threading.Lock()


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _load_users_unlocked() -> list[dict[str, Any]]:
    path = users_file_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return data


def _save_users_unlocked(users: list[dict[str, Any]]) -> None:
    path = users_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_users() -> list[dict[str, Any]]:
    with _file_lock:
        return _load_users_unlocked()


def save_users(users: list[dict[str, Any]]) -> None:
    with _file_lock:
        _save_users_unlocked(users)


def find_user(email: str) -> dict[str, Any] | None:
    key = email.strip().lower()
    for user in load_users():
        if str(user.get("email", "")).lower() == key:
            return user
    return None


def create_access_token(*, email: str, name: str, role: UserRole) -> str:
    expires = _utcnow() + timedelta(minutes=_JWT_ACCESS_MINUTES)
    payload = {
        "sub": email.lower(),
        "name": name,
        "role": role,
        "exp": expires,
        "iat": _utcnow(),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def login(email: str, password: str) -> dict[str, Any]:
    user = find_user(email)
    if user is None or user.get("status") != "active":
        raise ValueError("Invalid email or password")
    if not verify_password(password, user.get("password_hash")):
        raise ValueError("Invalid email or password")
    token = create_access_token(
        email=user["email"],
        name=str(user.get("name") or user["email"]),
        role=user.get("role", "user"),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": user["email"],
        "name": str(user.get("name") or user["email"]),
        "role": user.get("role", "user"),
    }


def user_profile(email: str) -> dict[str, Any]:
    user = find_user(email)
    if user is None or user.get("status") == "disabled":
        raise ValueError("User not found")
    return {
        "email": user["email"],
        "name": str(user.get("name") or user["email"]),
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
        "activity_logging_enabled": bool(user.get("activity_logging_enabled")),
    }


def accept_invite(token: str, password: str) -> dict[str, Any]:
    users = load_users()
    now = _utcnow()
    matched: dict[str, Any] | None = None
    for user in users:
        if user.get("invite_token") == token and user.get("status") == "invited":
            matched = user
            break
    if matched is None:
        raise ValueError("Invalid or expired invite link")
    expires = _parse_iso(matched.get("invite_expires_at"))
    if expires is not None and now > expires:
        raise ValueError("Invalid or expired invite link")
    matched["password_hash"] = hash_password(password)
    matched["status"] = "active"
    matched["invite_token"] = None
    matched["invite_expires_at"] = None
    save_users(users)
    return login(matched["email"], password)


def change_password(email: str, current_password: str, new_password: str) -> None:
    user = find_user(email)
    if user is None or user.get("status") != "active":
        raise ValueError("Invalid email or password")
    if not verify_password(current_password, user.get("password_hash")):
        raise ValueError("Invalid email or password")
    users = load_users()
    for row in users:
        if str(row.get("email", "")).lower() == email.lower():
            row["password_hash"] = hash_password(new_password)
            break
    save_users(users)


def _invite_url(token: str) -> str:
    return f"{_INVITE_BASE_URL}/accept-invite?token={token}"


def admin_invite(*, email: str, name: str, role: UserRole = "user") -> dict[str, Any]:
    key = email.strip().lower()
    users = load_users()
    if any(str(u.get("email", "")).lower() == key for u in users):
        raise ValueError("User already exists")
    token = secrets.token_urlsafe(32)
    expires = _utcnow() + timedelta(days=_INVITE_EXPIRE_DAYS)
    users.append(
        {
            "email": key,
            "name": name.strip(),
            "role": role,
            "status": "invited",
            "password_hash": None,
            "invite_token": token,
            "invite_expires_at": _iso(expires),
            "activity_logging_enabled": False,
        }
    )
    save_users(users)
    return {
        "email": key,
        "invite_token": token,
        "invite_expires_at": _iso(expires),
        "invite_url": _invite_url(token),
    }


def admin_list_users() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for user in load_users():
        out.append(
            {
                "email": user.get("email"),
                "name": user.get("name"),
                "role": user.get("role", "user"),
                "status": user.get("status", "active"),
                "invite_expires_at": user.get("invite_expires_at"),
                "activity_logging_enabled": bool(user.get("activity_logging_enabled")),
            }
        )
    return sorted(out, key=lambda row: str(row.get("email", "")).lower())


def admin_patch_user(
    email: str,
    *,
    status: UserStatus | None = None,
    resend_invite: bool = False,
    name: str | None = None,
    role: UserRole | None = None,
    activity_logging_enabled: bool | None = None,
) -> dict[str, Any]:
    users = load_users()
    matched: dict[str, Any] | None = None
    for user in users:
        if str(user.get("email", "")).lower() == email.lower():
            matched = user
            break
    if matched is None:
        raise ValueError("User not found")
    if name is not None:
        matched["name"] = name.strip()
    if role is not None:
        matched["role"] = role
    if activity_logging_enabled is not None:
        matched["activity_logging_enabled"] = activity_logging_enabled
    if status is not None:
        matched["status"] = status
    if resend_invite:
        token = secrets.token_urlsafe(32)
        expires = _utcnow() + timedelta(days=_INVITE_EXPIRE_DAYS)
        matched["invite_token"] = token
        matched["invite_expires_at"] = _iso(expires)
        matched["status"] = "invited"
        matched["password_hash"] = None
    save_users(users)
    result: dict[str, Any] = {
        "email": matched.get("email"),
        "name": matched.get("name"),
        "role": matched.get("role", "user"),
        "status": matched.get("status", "active"),
        "invite_expires_at": matched.get("invite_expires_at"),
        "activity_logging_enabled": bool(matched.get("activity_logging_enabled")),
    }
    if resend_invite and matched.get("invite_token"):
        result["invite_url"] = _invite_url(str(matched["invite_token"]))
        result["invite_token"] = matched["invite_token"]
    return result


def bootstrap_admin(email: str, password: str, name: str = "Admin") -> None:
    users = load_users()
    key = email.strip().lower()
    if any(str(u.get("email", "")).lower() == key for u in users):
        raise ValueError("User already exists")
    users.append(
        {
            "email": key,
            "name": name,
            "role": "admin",
            "status": "active",
            "password_hash": hash_password(password),
            "invite_token": None,
            "invite_expires_at": None,
            "activity_logging_enabled": False,
        }
    )
    save_users(users)
