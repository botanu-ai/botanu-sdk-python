# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""In-process PII scrubber for LLM content capture.

Runs inside the customer process, before content is written to span
attributes — so prompts and responses never leave the application with
emails, keys, card numbers, etc. intact. Defense-in-depth alongside the
collector regex pass and the evaluator Presidio NER.

Scope is intentionally narrow: this module only scrubs text passed to
``LLMTracker.set_input_content`` / ``LLMTracker.set_output_content`` /
``DBTracker.set_retrieval_content``. Auto-instrumented attributes
(``http.request.body``, ``db.statement``, …) are handled by the
collector denylist.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


_BUILTIN_PATTERNS: Dict[str, str] = {
    # Order-sensitive — specific API-key prefixes must run before the generic
    # openai_key / anthropic_key patterns, and credit_card runs before phone
    # to avoid a long card number being partially captured as a phone.
    "bearer_token": r"Bearer\s+[A-Za-z0-9._\-]+",
    "jwt": r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "github_token": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    "stripe_key": r"\b(?:sk|rk)_live_[A-Za-z0-9]{24,}\b",
    "slack_token": r"\bxox[baprs]-[A-Za-z0-9-]+\b",
    "anthropic_key": r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b",
    "openai_key": r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b",
    "credit_card": r"\b(?:\d[ -]?){12,18}\d\b",
    "ssn_us": r"\b\d{3}-\d{2}-\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "phone_e164": r"\+[1-9]\d{6,14}\b",
    "phone_us": r"(?:\(\d{3}\)\s?\d{3}[-.]\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b)",
    "ipv6": r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b",
    "ipv4": r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
}


def _luhn_valid(digits: str) -> bool:
    """Return True if *digits* passes the Luhn checksum. Strips non-digits."""
    d = [int(c) for c in digits if c.isdigit()]
    if len(d) < 13 or len(d) > 19:
        return False
    checksum = 0
    parity = len(d) % 2
    for i, n in enumerate(d):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        checksum += n
    return checksum % 10 == 0


class PIIScrubber:
    """Stateless regex-based PII scrubber.

    Compile once at construction; call :meth:`scrub` on every content string.
    Credit-card hits are Luhn-validated to reject the 16-digit order IDs and
    nonces that would otherwise trip the pattern.
    """

    def __init__(
        self,
        enabled_patterns: Optional[List[str]] = None,
        disabled_patterns: Optional[List[str]] = None,
        custom_patterns: Optional[Dict[str, str]] = None,
        replacement: str = "[REDACTED]",
    ) -> None:
        self.replacement = replacement
        selected: List[Tuple[str, str]] = []
        disabled = set(disabled_patterns or [])
        for name, pattern in _BUILTIN_PATTERNS.items():
            if enabled_patterns is not None and name not in enabled_patterns:
                continue
            if name in disabled:
                continue
            selected.append((name, pattern))
        for name, pattern in (custom_patterns or {}).items():
            selected.append((name, pattern))
        self._compiled: List[Tuple[str, re.Pattern[str]]] = []
        for name, pattern in selected:
            try:
                self._compiled.append((name, re.compile(pattern)))
            except re.error as exc:
                logger.warning("Botanu PII scrubber: invalid regex for %s: %s", name, exc)

    def scrub(self, text: str) -> str:
        if not text:
            return text
        out = text
        for name, compiled in self._compiled:
            if name == "credit_card":
                out = compiled.sub(
                    lambda m: self.replacement if _luhn_valid(m.group(0)) else m.group(0),
                    out,
                )
            else:
                out = compiled.sub(self.replacement, out)
        return out


_cached_scrubber: Optional[PIIScrubber] = None
_cached_scrubber_key: Optional[Tuple] = None  # type: ignore[type-arg]
_cache_lock = threading.RLock()


def _scrubber_from_config(cfg: object) -> Optional[PIIScrubber]:
    """Return a cached :class:`PIIScrubber` built from *cfg*, or None if disabled.

    Cache key is the subset of config fields the scrubber depends on, so a
    config reload with different PII settings rebuilds automatically without
    recompiling on every call. Lock-guarded for the FastAPI / Celery threaded
    worker case — lock contention is only paid on cache miss (rare).
    """
    global _cached_scrubber, _cached_scrubber_key
    enabled = bool(getattr(cfg, "pii_scrub_enabled", False))
    if not enabled:
        return None
    disabled = tuple(getattr(cfg, "pii_scrub_disable_patterns", None) or ())
    custom_items = getattr(cfg, "pii_scrub_custom_patterns", None) or {}
    custom = tuple(sorted(custom_items.items()))
    replacement = str(getattr(cfg, "pii_scrub_replacement", "[REDACTED]"))
    use_presidio = bool(getattr(cfg, "pii_scrub_use_presidio", False))
    key = (enabled, disabled, custom, replacement, use_presidio)
    # Fast path: read without holding the lock — regex compilation is idempotent
    # so even a torn read at worst returns a scrubber one generation stale.
    if key == _cached_scrubber_key and _cached_scrubber is not None:
        return _cached_scrubber
    with _cache_lock:
        if key != _cached_scrubber_key:
            _cached_scrubber = PIIScrubber(
                disabled_patterns=list(disabled),
                custom_patterns=dict(custom),
                replacement=replacement,
            )
            _cached_scrubber_key = key
        return _cached_scrubber


def apply_scrub(text: str, cfg: object) -> str:
    """Scrub *text* according to *cfg*. Returns *text* unchanged if disabled.

    Called from the three content-capture tracker methods after the content
    sampling gate has already decided to capture. Safe to call on empty /
    None text — returns the input verbatim.
    """
    if not text:
        return text
    scrubber = _scrubber_from_config(cfg)
    if scrubber is None:
        return text
    scrubbed = scrubber.scrub(text)
    if bool(getattr(cfg, "pii_scrub_use_presidio", False)):
        try:
            from botanu.sdk.pii_presidio import presidio_scrub
        except ImportError:
            return scrubbed
        scrubbed = presidio_scrub(scrubbed, replacement=str(getattr(cfg, "pii_scrub_replacement", "[REDACTED]")))
    return scrubbed


def _reset_cache_for_tests() -> None:
    """Test-only hook: drop the cached scrubber so a new config takes effect."""
    global _cached_scrubber, _cached_scrubber_key
    with _cache_lock:
        _cached_scrubber = None
        _cached_scrubber_key = None
