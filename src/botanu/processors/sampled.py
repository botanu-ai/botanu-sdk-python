# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""SampledSpanProcessor — preserves the customer's sampling ratio.

When botanu changes the TracerProvider sampler to AlwaysOn (to capture 100%),
existing customer processors (Datadog exporter, Jaeger exporter, etc.) would
suddenly see 10x the span volume if the customer had ratio-based sampling.

This processor wraps an existing processor and applies the customer's original
ratio at the export level. Result: the customer's exporter sees the same volume
as before, their bill is unchanged, their dashboards are unchanged.

botanu's own processor is NOT wrapped — it sees 100%.

Sampling is deterministic: the same trace_id always gets the same decision.
This matches OTel's ``TraceIdRatioBasedSampler`` algorithm.
"""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import context
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import Span

logger = logging.getLogger(__name__)


class SampledSpanProcessor(SpanProcessor):
    """Wraps a SpanProcessor with deterministic ratio sampling.

    Args:
        wrapped: The original processor to wrap (e.g., BatchSpanProcessor
            sending to Datadog).
        ratio: Sampling ratio (0.0 to 1.0). 0.1 means 10% of spans are
            forwarded to the wrapped processor.
    """

    def __init__(self, wrapped: SpanProcessor, ratio: float) -> None:
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(f"ratio must be between 0.0 and 1.0, got {ratio}")
        self._wrapped = wrapped
        self._ratio = ratio
        # Pre-compute bound for comparison (avoids per-span float math)
        self._bound = int(ratio * (2**64 - 1))

    def _should_sample(self, trace_id: int) -> bool:
        """Deterministic sampling decision based on trace_id.

        Uses the upper 64 bits of the 128-bit trace_id, matching OTel's
        TraceIdRatioBasedSampler algorithm. Same trace_id always produces
        the same decision.
        """
        if self._ratio >= 1.0:
            return True
        if self._ratio <= 0.0:
            return False
        # Upper 64 bits of trace_id for deterministic comparison
        upper = trace_id >> 64 if trace_id.bit_length() > 64 else trace_id
        return upper <= self._bound

    def on_start(
        self,
        span: Span,
        parent_context: Optional[context.Context] = None,
    ) -> None:
        # Gate on_start with the same decision as on_end. Forwarding on_start
        # unconditionally while gating on_end orphans spans inside wrapped
        # processors (BatchSpanProcessor, Datadog exporter, etc.) — they hold
        # start-time bookkeeping for spans whose on_end never fires. Over time
        # this leaks memory in the customer's process.
        if self._should_sample(span.context.trace_id):
            self._wrapped.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        if self._should_sample(span.context.trace_id):
            self._wrapped.on_end(span)

    def shutdown(self) -> None:
        self._wrapped.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._wrapped.force_flush(timeout_millis)
