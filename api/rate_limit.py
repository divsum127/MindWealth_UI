"""HTTP rate limiting (slowapi + limits middleware, identity: user > apikey > ip)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable

from fastapi import Request
from limits import parse_many
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from api.rate_limit_config import RateLimitConfig, get_config, reload_config
from api.services import auth_service as auth_svc

log = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

_storage = MemoryStorage()
_moving = MovingWindowRateLimiter(_storage)


def rate_limit_enabled() -> bool:
    return get_config().enabled


def reset_rate_limit_storage() -> None:
    """Clear in-memory counters (tests)."""
    global _storage, _moving
    _storage = MemoryStorage()
    _moving = MovingWindowRateLimiter(_storage)


def reload_rules() -> None:
    """Rebuild route rules and config after env/file change (tests)."""
    global _RULES
    _RULES = None
    reload_config()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get("mw_access_token")


def get_request_role(request: Request) -> str:
    """admin | user | apikey | ip (unauthenticated)."""
    token = _token_from_request(request)
    if token:
        try:
            payload = auth_svc.decode_access_token(token)
            if str(payload.get("role", "")).lower() == "admin":
                return "admin"
            return "user"
        except ValueError:
            pass
    if request.headers.get("X-API-Key") or request.headers.get("x-api-key"):
        return "apikey"
    return "ip"


def get_identity_key(request: Request) -> str:
    token = _token_from_request(request)
    if token:
        try:
            payload = auth_svc.decode_access_token(token)
            email = str(payload.get("sub", "")).lower().strip()
            if email:
                role = str(payload.get("role", "user")).lower()
                return f"user:{role}:{email}"
        except ValueError:
            pass
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if api_key:
        digest = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"apikey:{digest}"
    return f"ip:{get_client_ip(request)}"


def get_ip_key(request: Request) -> str:
    return f"ip:{get_client_ip(request)}"


async def get_login_email_key(request: Request) -> str:
    cached = getattr(request.state, "rate_limit_login_email", None)
    if cached is not None:
        return f"login_email:{cached}" if cached else get_ip_key(request)
    email = ""
    body = getattr(request.state, "_cached_body", None)
    if body is None:
        body = await request.body()
        request.state._cached_body = body
    try:
        if body:
            data = json.loads(body)
            email = str(data.get("email", "")).lower().strip()
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        email = ""
    request.state.rate_limit_login_email = email
    if email:
        return f"login_email:{email}"
    return get_ip_key(request)


KeyFunc = Callable[[Request], str]
AsyncKeyFunc = Callable[[Request], Awaitable[str]]


@dataclass(frozen=True)
class RateRule:
    methods: frozenset[str]
    pattern: re.Pattern[str]
    limit_key: str
    key_func: KeyFunc | None = None
    async_key_func: AsyncKeyFunc | None = None


def _limits_for_rule(cfg: RateLimitConfig, role: str, limit_key: str) -> tuple[str, ...]:
    if limit_key == "read":
        if role == "apikey":
            return tuple(part.strip() for part in cfg.apikey_read.split(";") if part.strip())
        effective = role if role in ("admin", "user") else "user"
        return cfg.role_limits(effective).read_parts()

    shared_map = {
        "auth_login_ip": cfg.auth_login_ip,
        "auth_login_email": cfg.auth_login_email,
        "auth_accept_invite_ip": cfg.auth_accept_invite_ip,
        "health": cfg.health,
    }
    if limit_key in shared_map:
        return (shared_map[limit_key],)

    effective = role if role in ("admin", "user") else "user"
    rl = cfg.role_limits(effective)
    field_map = {
        "chat_messages": rl.chat_messages,
        "chat_presets": rl.chat_presets,
        "chat_job_poll": rl.chat_job_poll,
        "chat_session_create": rl.chat_session_create,
        "chat_read": rl.chat_read,
        "auth_session": rl.auth_session,
        "auth_admin": rl.auth_admin,
        "auth_change_password": rl.auth_change_password,
        "write_expensive": rl.write_expensive,
        "macro_nightly": rl.macro_nightly,
        "monitored_trades_write": rl.monitored_trades_write,
        "activity_events": rl.activity_events,
    }
    raw = field_map.get(limit_key, "60/minute")
    return tuple(part.strip() for part in raw.split(";") if part.strip())


def _global_user_limit(cfg: RateLimitConfig, role: str) -> str:
    if role == "admin":
        return cfg.admin.global_user_per_minute
    if role == "apikey":
        return "600/minute"
    return cfg.user.global_user_per_minute


def _build_rules() -> list[RateRule]:
    p = API_PREFIX
    return [
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/auth/login$"), "auth_login_ip", key_func=get_ip_key),
        RateRule(
            frozenset({"POST"}),
            re.compile(rf"^{re.escape(p)}/auth/login$"),
            "auth_login_email",
            async_key_func=get_login_email_key,
        ),
        RateRule(
            frozenset({"POST"}),
            re.compile(rf"^{re.escape(p)}/auth/accept-invite$"),
            "auth_accept_invite_ip",
            key_func=get_ip_key,
        ),
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/auth/change-password$"), "auth_change_password"),
        RateRule(frozenset({"GET", "POST"}), re.compile(rf"^{re.escape(p)}/auth/(me|logout)$"), "auth_session"),
        RateRule(frozenset({"POST", "GET", "PATCH"}), re.compile(rf"^{re.escape(p)}/auth/admin/"), "auth_admin"),
        RateRule(
            frozenset({"POST"}),
            re.compile(rf"^{re.escape(p)}/chatbot/sessions/[^/]+/messages$"),
            "chat_messages",
        ),
        RateRule(
            frozenset({"POST"}),
            re.compile(rf"^{re.escape(p)}/chatbot/(analyze-asset|signal-insights|breadth-analysis)$"),
            "chat_presets",
        ),
        RateRule(frozenset({"GET"}), re.compile(rf"^{re.escape(p)}/chatbot/jobs/[^/]+$"), "chat_job_poll"),
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/chatbot/sessions$"), "chat_session_create"),
        RateRule(
            frozenset({"GET", "POST", "PATCH", "DELETE"}),
            re.compile(
                rf"^{re.escape(p)}/chatbot/(?!sessions/[^/]+/messages$|analyze-asset$|signal-insights$|breadth-analysis$)"
            ),
            "chat_read",
        ),
        RateRule(
            frozenset({"POST", "PATCH"}),
            re.compile(
                rf"^{re.escape(p)}/conviction/(signals/evaluate|signals/overlay-file|pipeline/daily|tickers/[^/]+/(recalculate|daily))$"
            ),
            "write_expensive",
        ),
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/macro/run-nightly$"), "macro_nightly"),
        RateRule(frozenset({"POST", "DELETE"}), re.compile(rf"^{re.escape(p)}/monitored-trades"), "monitored_trades_write"),
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/portfolio/risk/analyze$"), "write_expensive"),
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/signals/check-degradation$"), "write_expensive"),
        RateRule(frozenset({"GET"}), re.compile(rf"^{re.escape(p)}/health$"), "health", key_func=get_identity_key),
        RateRule(frozenset({"POST"}), re.compile(rf"^{re.escape(p)}/activity/events$"), "activity_events"),
        RateRule(
            frozenset({"GET"}),
            re.compile(rf"^{re.escape(p)}/(signals|portfolio|macro|analytics|conviction|virtual_trading)(/|$)"),
            "read",
        ),
    ]


_RULES: list[RateRule] | None = None


def _rules() -> list[RateRule]:
    global _RULES
    if _RULES is None:
        _RULES = _build_rules()
    return _RULES


def _limit_parts(limit_strings: Iterable[str]) -> list:
    parts: list = []
    for limit_str in limit_strings:
        parts.extend(parse_many(limit_str))
    return parts


def _retry_after_seconds(lim, key: str) -> int:
    stats = _moving.get_window_stats(lim, key)
    return max(int(stats.reset_time - time.time()) + 1, 1)


def check_limits(key: str, limit_strings: Iterable[str]) -> int | None:
    """Return Retry-After seconds when limited, else None."""
    limits = _limit_parts(limit_strings)
    for lim in limits:
        if not _moving.test(lim, key):
            retry = _retry_after_seconds(lim, key)
            log.warning("rate_limit hit key=%s limit=%s", key, lim)
            return retry
    for lim in limits:
        _moving.hit(lim, key)
    return None


async def _resolve_key(request: Request, rule: RateRule) -> str:
    if rule.async_key_func is not None:
        return await rule.async_key_func(request)
    if rule.key_func is not None:
        return rule.key_func(request)
    return get_identity_key(request)


async def _collect_checks(request: Request, method: str, path: str, cfg: RateLimitConfig) -> list[tuple[str, tuple[str, ...]]]:
    checks: list[tuple[str, tuple[str, ...]]] = []
    role = get_request_role(request)
    identity_key = get_identity_key(request)
    ip_key = get_ip_key(request)

    if not path.endswith("/health"):
        checks.append((ip_key, (cfg.global_ip_per_minute,)))
        if role in ("admin", "user", "apikey"):
            checks.append((identity_key, (_global_user_limit(cfg, role),)))

    for rule in _rules():
        if method not in rule.methods:
            continue
        if not rule.pattern.search(path):
            continue
        limits = _limits_for_rule(cfg, role, rule.limit_key)
        key = await _resolve_key(request, rule)
        checks.append((key, limits))

    deduped: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for item in checks:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    retry = getattr(exc, "retry_after", None) or 60
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
        headers={"Retry-After": str(retry)},
    )


limiter = Limiter(key_func=get_identity_key, enabled=rate_limit_enabled(), storage_uri="memory://")


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not rate_limit_enabled():
            return await call_next(request)

        path = request.url.path
        if not path.startswith(API_PREFIX):
            return await call_next(request)

        method = request.method.upper()
        if method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            request.state._cached_body = body

            async def receive() -> dict:
                return {"type": "http.request", "body": body, "more_body": False}

            request = Request(request.scope, receive)

        cfg = get_config()
        checks = await _collect_checks(request, method, path, cfg)

        for key, limit_strings in checks:
            retry = check_limits(key, limit_strings)
            if retry is not None:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry)},
                )

        return await call_next(request)
