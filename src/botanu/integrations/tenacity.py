# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tenacity retry integration — automatic attempt tracking for LLM calls.

Stamps ``botanu.request.attempt`` on every span created inside a tenacity
retry loop so the collector and cost engine can see how many attempts an
event required.

Usage::

    from tenacity import retry, stop_after_attempt, wait_exponential
    from botanu.integrations.tenacity import botanu_before, botanu_after_all
    from botanu.tracking.llm import track_llm_call

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        before=botanu_before,
        after=botanu_after_all,   # optional — resets attempt counter
    )
    def call_llm():
        with track_llm_call("openai", "gpt-4") as tracker:
            response = openai.chat.completions.create(...)
            tracker.set_tokens(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
            return response

The ``track_llm_call`` context manager reads the attempt number
automatically — no need to call ``tracker.set_attempt()`` manually.
"""

from __future__ import annotations

from typing import Any

from botanu.tracking.llm import _retry_attempt


def botanu_before(retry_state: Any) -> None:
    """Tenacity ``before`` callback — sets the current attempt number.

    Use as ``@retry(before=botanu_before)`` so that every
    ``track_llm_call`` inside the retried function automatically
    gets the correct attempt number on its span.
    """
    _retry_attempt.set(retry_state.attempt_number)


def botanu_after_all(retry_state: Any) -> None:
    """Tenacity ``after`` callback — resets the attempt counter.

    Optional but recommended. Prevents a stale attempt number from
    leaking into subsequent non-retried calls on the same thread.

    Use as ``@retry(after=botanu_after_all)``.
    """
    _retry_attempt.set(0)
