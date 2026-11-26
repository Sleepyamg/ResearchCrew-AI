"""Error classification and redaction shared by the runner and event tracker."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+|(Bearer\s+)\S+")

# OpenRouter returns the reset moment as a millisecond epoch in the error
# metadata, e.g. {'X-RateLimit-Reset': '1795737600000'}.
_RESET_PATTERN = re.compile(r"x-ratelimit-reset['\"]?\s*[:=]\s*['\"]?(\d{9,13})", re.IGNORECASE)

MESSAGES = {
    "quota": "Daily free-model request limit reached. Try again after your quota resets.",
    "rate_limit": "The free model is temporarily rate limited. Wait a minute and try again.",
    "auth": "The LLM provider rejected the request. Check OPENROUTER_API_KEY in backend/.env.",
    "timeout": "A network request timed out during research.",
    "provider_unavailable": "The model provider is temporarily unavailable. Try again later.",
    "network": "A network error occurred while contacting an external service.",
    "execution": "The research crew stopped with an error.",
}

# Short labels for places with little room (agent cards, log lines).
SHORT_REASONS = {
    "quota": "Daily request limit reached",
    "rate_limit": "Rate limited",
    "auth": "API key rejected",
    "timeout": "Request timed out",
    "provider_unavailable": "Provider unavailable",
    "network": "Network error",
    "execution": "Execution error",
}


def redact(text: str) -> str:
    """Mask anything that looks like an API key or bearer token."""
    return _SECRET_PATTERN.sub(lambda m: (m.group(1) or m.group(2)) + "[redacted]", text)


def error_kind(text: str) -> str:
    lowered = text.lower()
    if "per-day" in lowered or "per day" in lowered or "daily" in lowered:
        return "quota"
    if "429" in lowered or "rate limit" in lowered or "ratelimit" in lowered:
        return "rate_limit"
    if "401" in lowered or "unauthorized" in lowered or "api key" in lowered:
        return "auth"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if any(code in lowered for code in ("502", "503", "504", "unavailable", "overloaded")):
        return "provider_unavailable"
    if "connect" in lowered or "network" in lowered:
        return "network"
    return "execution"


def reset_time(text: str) -> str | None:
    """Return the rate-limit reset time as ISO 8601 UTC, if the error includes it."""
    match = _RESET_PATTERN.search(text)
    if not match:
        return None
    value = int(match.group(1))
    seconds = value / 1000 if value > 10**11 else value
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def short_reason(text: Any) -> str:
    return SHORT_REASONS[error_kind(str(text))]


def classify_error(error: BaseException) -> dict[str, str | None]:
    """Map a failure to a user-facing message plus redacted technical detail."""
    text = str(error)
    kind = error_kind(text)
    detail = redact(" ".join(text.split()))
    if len(detail) > 600:
        detail = detail[:599] + "…"
    return {
        "kind": kind,
        "message": MESSAGES[kind],
        "detail": f"{type(error).__name__}: {detail}",
        "reset_at": reset_time(text) if kind in ("quota", "rate_limit") else None,
    }
