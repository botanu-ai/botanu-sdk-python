# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""RunContextEnricher — the only span processor needed in the SDK.

Why this MUST be in SDK (not collector):
- Baggage is process-local (not sent over the wire).
- Only the SDK can read baggage and write it to span attributes.
- The collector only sees spans after they're exported.

All heavy processing should happen in the OTel Collector:
- PII redaction → ``redactionprocessor``
- Cardinality limits → ``attributesprocessor``
- Vendor detection → ``transformprocessor``
"""

from __future__ import annotations

import logging
from typing import ClassVar, List, Optional

from opentelemetry import baggage, context
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import Span

logger = logging.getLogger(__name__)


class RunContextEnricher(SpanProcessor):
    """Enriches ALL spans with run context from baggage.

    This ensures that every span (including auto-instrumented ones)
    gets ``botanu.run_id``, ``botanu.use_case``, etc. attributes.

    Without this processor, only the root ``botanu.run`` span would
    have these attributes.

    In ``lean_mode`` (default), only ``run_id`` and ``use_case`` are
    propagated to minimise per-span overhead.
    """

    BAGGAGE_KEYS_FULL: ClassVar[List[str]] = [
        "botanu.run_id",
        "botanu.use_case",
        "botanu.workflow",
        "botanu.environment",
        "botanu.tenant_id",
        "botanu.parent_run_id",
    ]

    BAGGAGE_KEYS_LEAN: ClassVar[List[str]] = [
        "botanu.run_id",
        "botanu.use_case",
    ]

    def __init__(self, lean_mode: bool = True) -> None:
        self._lean_mode = lean_mode
        self._baggage_keys = self.BAGGAGE_KEYS_LEAN if lean_mode else self.BAGGAGE_KEYS_FULL

    def on_start(
        self,
        span: Span,
        parent_context: Optional[context.Context] = None,
    ) -> None:
        """Called when a span starts — enrich with run context from baggage."""
        ctx = parent_context or context.get_current()

        for key in self._baggage_keys:
            value = baggage.get_baggage(key, ctx)
            if value:
                if not span.attributes or key not in span.attributes:
                    span.set_attribute(key, value)

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
