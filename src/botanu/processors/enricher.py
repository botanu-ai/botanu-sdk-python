# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""RunContextEnricher — the only span processor needed in the SDK.

Why this MUST be in SDK (not collector):
- Baggage is process-local (not sent over the wire).
- Only the SDK can read baggage and write it to span attributes.
- The collector only sees spans after they're exported.

Heavy non-content processing happens in the OTel Collector:
- Cardinality limits → ``attributesprocessor``
- Vendor detection → ``transformprocessor``
- Belt-and-suspenders PII regex → ``redactionprocessor``

In-process PII scrubbing of content-capture attributes is handled by
:mod:`botanu.sdk.pii` at the tracker methods, not by a span processor.
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

    This ensures that every span (including auto-instrumented ones) gets
    ``botanu.run_id``, ``botanu.workflow``, ``botanu.event_id``,
    ``botanu.customer_id``, ``botanu.environment``, ``botanu.tenant_id``,
    and ``botanu.parent_run_id`` attributes when those baggage keys are
    present on the active OTel context.

    Without this processor, only the root ``botanu.run`` span would carry
    these attributes; downstream auto-instrumented spans (LLM, HTTP, DB)
    would not.
    """

    BAGGAGE_KEYS: ClassVar[List[str]] = [
        "botanu.run_id",
        "botanu.workflow",
        "botanu.event_id",
        "botanu.customer_id",
        "botanu.environment",
        "botanu.tenant_id",
        "botanu.parent_run_id",
    ]

    def on_start(
        self,
        span: Span,
        parent_context: Optional[context.Context] = None,
    ) -> None:
        """Called when a span starts — enrich with run context from baggage."""
        ctx = parent_context or context.get_current()

        for key in self.BAGGAGE_KEYS:
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
