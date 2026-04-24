# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Content capture sampling gate for eval.

MVP: simple ``random.random() < rate`` check. The ``event_id`` parameter is
accepted now so that a Month 2+ upgrade to hash-based deterministic sampling
(SHA-256 of ``tenant_id || event_id``) won't break callers. Deterministic
sampling matters for replays and backfills; simple random is sufficient for
MVP volume.
"""

from __future__ import annotations

import random
from typing import Optional


def should_capture_content(rate: float, event_id: Optional[str] = None) -> bool:
    """Return True if this call's content should be captured.

    Args:
        rate: Capture rate in [0.0, 1.0]. 0.0 disables capture (default,
            privacy-safe). 1.0 captures everything (sandbox/shadow).
            Production typically uses 0.10–0.20.
        event_id: Currently unused. Present so a future deterministic-hash
            implementation can be swapped in without API churn.

    Examples:
        >>> should_capture_content(0.0)
        False
        >>> should_capture_content(1.0)
        True
    """
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return random.random() < rate  # noqa: S311
