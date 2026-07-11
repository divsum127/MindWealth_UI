"""Rate limit configuration — YAML file + optional env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _ROOT / "config" / "rate_limits.yaml"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _split_limits(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(";") if part.strip())


@dataclass(frozen=True)
class RoleLimits:
    global_user_per_minute: str
    read: str
    chat_messages: str
    chat_presets: str
    chat_job_poll: str
    chat_session_create: str
    chat_read: str
    auth_session: str
    auth_admin: str
    auth_change_password: str
    write_expensive: str
    macro_nightly: str
    monitored_trades_write: str
    activity_events: str

    def read_parts(self) -> tuple[str, ...]:
        return _split_limits(self.read)

    def chat_messages_parts(self) -> tuple[str, ...]:
        return _split_limits(self.chat_messages)

    def chat_presets_parts(self) -> tuple[str, ...]:
        return _split_limits(self.chat_presets)


@dataclass(frozen=True)
class RateLimitConfig:
    config_path: Path
    enabled: bool
    global_ip_per_minute: str
    auth_login_ip: str
    auth_login_email: str
    auth_accept_invite_ip: str
    health: str
    apikey_read: str
    admin: RoleLimits
    user: RoleLimits

    def role_limits(self, role: str) -> RoleLimits:
        if role == "admin":
            return self.admin
        return self.user

    # Backward-compatible aliases (user role defaults)
    @property
    def GLOBAL_IP_PER_MINUTE(self) -> str:
        return self.global_ip_per_minute

    @property
    def GLOBAL_USER_PER_MINUTE(self) -> str:
        return self.user.global_user_per_minute

    @property
    def READ_USER(self) -> str:
        return self.user.read

    @property
    def READ_APIKEY(self) -> str:
        return self.apikey_read

    @property
    def CHAT_MESSAGES(self) -> str:
        return self.user.chat_messages

    @property
    def CHAT_PRESETS(self) -> str:
        return self.user.chat_presets

    @property
    def CHAT_JOB_POLL(self) -> str:
        return self.user.chat_job_poll

    @property
    def CHAT_SESSION_CREATE(self) -> str:
        return self.user.chat_session_create

    @property
    def CHAT_READ(self) -> str:
        return self.user.chat_read

    @property
    def AUTH_LOGIN_IP(self) -> str:
        return self.auth_login_ip

    @property
    def AUTH_LOGIN_EMAIL(self) -> str:
        return self.auth_login_email

    @property
    def AUTH_ACCEPT_INVITE_IP(self) -> str:
        return self.auth_accept_invite_ip

    @property
    def AUTH_CHANGE_PASSWORD(self) -> str:
        return self.user.auth_change_password

    @property
    def AUTH_SESSION(self) -> str:
        return self.user.auth_session

    @property
    def AUTH_ADMIN(self) -> str:
        return self.user.auth_admin

    @property
    def WRITE_EXPENSIVE(self) -> str:
        return self.user.write_expensive

    @property
    def MACRO_NIGHTLY(self) -> str:
        return self.user.macro_nightly

    @property
    def MONITORED_TRADES_WRITE(self) -> str:
        return self.user.monitored_trades_write

    @property
    def HEALTH(self) -> str:
        return self.health

    @property
    def ACTIVITY_EVENTS(self) -> str:
        return self.user.activity_events


def _role_from_dict(data: dict[str, Any], role: str, prefix: str) -> RoleLimits:
    """Build RoleLimits from YAML dict with optional RATE_LIMIT_{ROLE}_* env overrides."""

    def pick(key: str, default: str) -> str:
        env_key = f"RATE_LIMIT_{prefix}_{key}".upper()
        legacy = ""
        if prefix == "USER":
            legacy_map = {
                "READ": "RATE_LIMIT_READ_USER",
                "CHAT_MESSAGES": "RATE_LIMIT_CHAT_MESSAGES",
                "CHAT_PRESETS": "RATE_LIMIT_CHAT_PRESETS",
                "CHAT_JOB_POLL": "RATE_LIMIT_CHAT_JOB_POLL",
                "CHAT_SESSION_CREATE": "RATE_LIMIT_CHAT_SESSION_CREATE",
                "CHAT_READ": "RATE_LIMIT_CHAT_READ",
                "GLOBAL_USER_PER_MINUTE": "RATE_LIMIT_GLOBAL_USER_PER_MINUTE",
                "AUTH_CHANGE_PASSWORD": "RATE_LIMIT_CHANGE_PASSWORD_PER_MINUTE",
                "AUTH_SESSION": "RATE_LIMIT_AUTH_SESSION_PER_MINUTE",
                "AUTH_ADMIN": "RATE_LIMIT_AUTH_ADMIN_PER_MINUTE",
                "WRITE_EXPENSIVE": "RATE_LIMIT_WRITE_EXPENSIVE_PER_MINUTE",
                "MACRO_NIGHTLY": "RATE_LIMIT_MACRO_NIGHTLY",
                "MONITORED_TRADES_WRITE": "RATE_LIMIT_MONITORED_TRADES_WRITE_PER_MINUTE",
                "ACTIVITY_EVENTS": "RATE_LIMIT_ACTIVITY_EVENTS_PER_MINUTE",
            }
            legacy = _env(legacy_map.get(key, ""))
        return _env(env_key) or legacy or str(data.get(_yaml_key(key), default))

    def _yaml_key(key: str) -> str:
        return key.lower()

    defaults = RoleLimits(
        global_user_per_minute="400/minute",
        read="30/10seconds;300/minute",
        chat_messages="3/minute;30/hour",
        chat_presets="3/minute;20/hour",
        chat_job_poll="120/minute",
        chat_session_create="20/minute",
        chat_read="60/minute",
        auth_session="60/minute",
        auth_admin="20/minute",
        auth_change_password="5/minute",
        write_expensive="10/minute",
        macro_nightly="2/hour",
        monitored_trades_write="30/minute",
        activity_events="30/minute",
    )
    return RoleLimits(
        global_user_per_minute=pick("GLOBAL_USER_PER_MINUTE", defaults.global_user_per_minute),
        read=pick("READ", defaults.read),
        chat_messages=pick("CHAT_MESSAGES", defaults.chat_messages),
        chat_presets=pick("CHAT_PRESETS", defaults.chat_presets),
        chat_job_poll=pick("CHAT_JOB_POLL", defaults.chat_job_poll),
        chat_session_create=pick("CHAT_SESSION_CREATE", defaults.chat_session_create),
        chat_read=pick("CHAT_READ", defaults.chat_read),
        auth_session=pick("AUTH_SESSION", defaults.auth_session),
        auth_admin=pick("AUTH_ADMIN", defaults.auth_admin),
        auth_change_password=pick("AUTH_CHANGE_PASSWORD", defaults.auth_change_password),
        write_expensive=pick("WRITE_EXPENSIVE", defaults.write_expensive),
        macro_nightly=pick("MACRO_NIGHTLY", defaults.macro_nightly),
        monitored_trades_write=pick("MONITORED_TRADES_WRITE", defaults.monitored_trades_write),
        activity_events=pick("ACTIVITY_EVENTS", defaults.activity_events),
    )


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def load_config() -> RateLimitConfig:
    config_path = Path(_env("RATE_LIMIT_CONFIG_FILE", str(_DEFAULT_CONFIG_PATH)))
    raw = _load_yaml_config(config_path)
    shared = raw.get("shared", {}) if isinstance(raw.get("shared"), dict) else {}
    apikey = raw.get("apikey", {}) if isinstance(raw.get("apikey"), dict) else {}
    admin_raw = raw.get("admin", {}) if isinstance(raw.get("admin"), dict) else {}
    user_raw = raw.get("user", {}) if isinstance(raw.get("user"), dict) else {}

    enabled_env = _env("RATE_LIMIT_ENABLED")
    if enabled_env:
        enabled = enabled_env.lower() not in {"0", "false", "no"}
    else:
        enabled = bool(raw.get("enabled", True))

    return RateLimitConfig(
        config_path=config_path,
        enabled=enabled,
        global_ip_per_minute=_env("RATE_LIMIT_GLOBAL_IP_PER_MINUTE") or str(
            shared.get("global_ip_per_minute", "600/minute")
        ),
        auth_login_ip=_env("RATE_LIMIT_LOGIN_PER_MINUTE") or str(shared.get("auth_login_ip", "10/minute")),
        auth_login_email=_env("RATE_LIMIT_LOGIN_EMAIL_PER_MINUTE")
        or str(shared.get("auth_login_email", "5/minute")),
        auth_accept_invite_ip=_env("RATE_LIMIT_ACCEPT_INVITE_PER_MINUTE")
        or str(shared.get("auth_accept_invite_ip", "5/minute")),
        health=_env("RATE_LIMIT_HEALTH_PER_MINUTE") or str(shared.get("health", "120/minute")),
        apikey_read=_env("RATE_LIMIT_READ_APIKEY") or str(apikey.get("read", "60/10seconds;600/minute")),
        admin=_role_from_dict(admin_raw, "admin", "ADMIN"),
        user=_role_from_dict(user_raw, "user", "USER"),
    )


@lru_cache(maxsize=1)
def get_config() -> RateLimitConfig:
    return load_config()


def reload_config() -> None:
    get_config.cache_clear()
