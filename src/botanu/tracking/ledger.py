# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Attempt Ledger — durable event log for invisible cost tracking.

An append-only event log that is NEVER sampled and survives crashes.
Uses OTel Logs API to emit structured events.

Event Types:
- ``attempt.started``: Run/attempt began
- ``llm.attempted``: LLM call attempt (with tokens, cost)
- ``tool.attempted``: Tool execution attempt
- ``attempt.ended``: Run/attempt completed
- ``cancellation.requested``: Cancellation was requested
- ``zombie.detected``: Work continued after timeout
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Optional

from opentelemetry import trace

logger = logging.getLogger(__name__)


class LedgerEventType(str, Enum):
    ATTEMPT_STARTED = "attempt.started"
    ATTEMPT_ENDED = "attempt.ended"
    LLM_ATTEMPTED = "llm.attempted"
    TOOL_ATTEMPTED = "tool.attempted"
    CANCEL_REQUESTED = "cancellation.requested"
    CANCEL_ACKNOWLEDGED = "cancellation.acknowledged"
    ZOMBIE_DETECTED = "zombie.detected"
    REDELIVERY_DETECTED = "redelivery.detected"


class AttemptStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"


@dataclass
class AttemptLedger:
    """Durable event ledger for cost tracking.

    Emits structured log records that are never sampled, providing a
    reliable source of truth for attempt counts, token costs, and zombie work.
    """

    service_name: str = field(
        default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "unknown"),
    )
    otlp_endpoint: Optional[str] = field(default=None)
    _logger: Any = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._initialize_logger()

    def _initialize_logger(self) -> None:
        try:
            from opentelemetry._logs import get_logger_provider, set_logger_provider
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            from opentelemetry.sdk._logs import LoggerProvider
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

            provider = get_logger_provider()

            endpoint = self.otlp_endpoint
            if not endpoint:
                traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                if traces_endpoint:
                    endpoint = f"{traces_endpoint.rstrip('/')}/v1/logs"
                else:
                    endpoint = "http://localhost:4318/v1/logs"

            if provider is None or not hasattr(provider, "get_logger"):
                new_provider = LoggerProvider()
                exporter = OTLPLogExporter(endpoint=endpoint)
                new_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
                set_logger_provider(new_provider)
                provider = new_provider

            self._logger = provider.get_logger("botanu.attempt_ledger")
            self._initialized = True
            logger.debug("AttemptLedger initialized with endpoint: %s", endpoint)

        except Exception as exc:
            logger.warning("Failed to initialize AttemptLedger: %s", exc)
            self._initialized = False

    def _get_trace_context(self) -> Dict[str, str]:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
        return {}

    def _emit(
        self,
        event_type: LedgerEventType,
        severity: Any,
        attributes: Dict[str, Any],
    ) -> None:
        if not self._initialized or not self._logger:
            return

        try:
            from opentelemetry.sdk._logs import LogRecord

            attrs = {
                "event.name": event_type.value,
                "service.name": self.service_name,
                "timestamp_ms": int(time.time() * 1000),
                **self._get_trace_context(),
                **attributes,
            }

            self._logger.emit(
                LogRecord(
                    timestamp=int(time.time_ns()),
                    severity_number=severity,
                    severity_text=severity.name,
                    body=event_type.value,
                    attributes=attrs,
                )
            )
        except Exception as exc:
            logger.debug("Failed to emit ledger event: %s", exc)

    # -----------------------------------------------------------------
    # Attempt Lifecycle
    # -----------------------------------------------------------------

    def attempt_started(
        self,
        run_id: str,
        use_case: str,
        attempt: int = 1,
        root_run_id: Optional[str] = None,
        workflow: Optional[str] = None,
        tenant_id: Optional[str] = None,
        deadline_ts: Optional[float] = None,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.ATTEMPT_STARTED,
            SeverityNumber.INFO,
            {
                "botanu.run_id": run_id,
                "botanu.use_case": use_case,
                "botanu.attempt": attempt,
                "botanu.root_run_id": root_run_id or run_id,
                "botanu.workflow": workflow,
                "botanu.tenant_id": tenant_id,
                "botanu.deadline_ts": deadline_ts,
            },
        )

    def attempt_ended(
        self,
        run_id: str,
        status: str,
        duration_ms: Optional[float] = None,
        error_class: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.ATTEMPT_ENDED,
            SeverityNumber.INFO if status == "success" else SeverityNumber.WARN,
            {
                "botanu.run_id": run_id,
                "status": status,
                "duration_ms": duration_ms,
                "error_class": error_class,
                "reason_code": reason_code,
            },
        )

    # -----------------------------------------------------------------
    # LLM Attempt Events
    # -----------------------------------------------------------------

    def llm_attempted(
        self,
        run_id: str,
        provider: str,
        model: str,
        operation: str = "chat",
        attempt_number: int = 1,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        duration_ms: Optional[float] = None,
        status: str = "success",
        error_class: Optional[str] = None,
        provider_request_id: Optional[str] = None,
        estimated_cost_usd: Optional[float] = None,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.LLM_ATTEMPTED,
            SeverityNumber.INFO if status == "success" else SeverityNumber.WARN,
            {
                "botanu.run_id": run_id,
                "gen_ai.provider.name": provider,
                "gen_ai.request.model": model,
                "gen_ai.operation.name": operation,
                "botanu.attempt": attempt_number,
                "gen_ai.usage.input_tokens": input_tokens,
                "gen_ai.usage.output_tokens": output_tokens,
                "botanu.usage.cached_tokens": cached_tokens,
                "duration_ms": duration_ms,
                "status": status,
                "error_class": error_class,
                "gen_ai.response.id": provider_request_id,
                "botanu.cost.estimated_usd": estimated_cost_usd,
            },
        )

    def tool_attempted(
        self,
        run_id: str,
        tool_name: str,
        tool_call_id: Optional[str] = None,
        attempt_number: int = 1,
        duration_ms: Optional[float] = None,
        status: str = "success",
        error_class: Optional[str] = None,
        items_returned: int = 0,
        bytes_processed: int = 0,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.TOOL_ATTEMPTED,
            SeverityNumber.INFO if status == "success" else SeverityNumber.WARN,
            {
                "botanu.run_id": run_id,
                "gen_ai.tool.name": tool_name,
                "gen_ai.tool.call.id": tool_call_id,
                "botanu.attempt": attempt_number,
                "duration_ms": duration_ms,
                "status": status,
                "error_class": error_class,
                "items_returned": items_returned,
                "bytes_processed": bytes_processed,
            },
        )

    # -----------------------------------------------------------------
    # Cancellation & Zombie Detection
    # -----------------------------------------------------------------

    def cancel_requested(
        self,
        run_id: str,
        reason: str = "user",
        requested_at_ms: Optional[float] = None,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.CANCEL_REQUESTED,
            SeverityNumber.WARN,
            {
                "botanu.run_id": run_id,
                "cancellation.reason": reason,
                "cancellation.requested_at_ms": requested_at_ms or int(time.time() * 1000),
            },
        )

    def cancel_acknowledged(
        self,
        run_id: str,
        acknowledged_by: str,
        latency_ms: Optional[float] = None,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.CANCEL_ACKNOWLEDGED,
            SeverityNumber.INFO,
            {
                "botanu.run_id": run_id,
                "cancellation.acknowledged_by": acknowledged_by,
                "cancellation.latency_ms": latency_ms,
            },
        )

    def zombie_detected(
        self,
        run_id: str,
        deadline_ts: float,
        actual_end_ts: float,
        zombie_duration_ms: float,
        component: str,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.ZOMBIE_DETECTED,
            SeverityNumber.ERROR,
            {
                "botanu.run_id": run_id,
                "deadline_ts": deadline_ts,
                "actual_end_ts": actual_end_ts,
                "zombie_duration_ms": zombie_duration_ms,
                "zombie_component": component,
            },
        )

    def redelivery_detected(
        self,
        run_id: str,
        queue_name: str,
        delivery_count: int,
        original_message_id: Optional[str] = None,
    ) -> None:
        from opentelemetry._logs import SeverityNumber

        self._emit(
            LedgerEventType.REDELIVERY_DETECTED,
            SeverityNumber.WARN,
            {
                "botanu.run_id": run_id,
                "queue.name": queue_name,
                "delivery_count": delivery_count,
                "original_message_id": original_message_id,
            },
        )

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def flush(self, timeout_ms: int = 5000) -> bool:
        if not self._initialized:
            return True
        try:
            from opentelemetry._logs import get_logger_provider

            provider = get_logger_provider()
            if hasattr(provider, "force_flush"):
                return provider.force_flush(timeout_ms)
            return True
        except Exception as exc:
            logger.debug("Failed to flush AttemptLedger: %s", exc)
            return False

    def shutdown(self) -> None:
        if not self._initialized:
            return
        try:
            from opentelemetry._logs import get_logger_provider

            provider = get_logger_provider()
            if hasattr(provider, "shutdown"):
                provider.shutdown()
        except Exception as exc:
            logger.debug("Failed to shutdown AttemptLedger: %s", exc)


# =========================================================================
# Global ledger
# =========================================================================

_global_ledger: Optional[AttemptLedger] = None


@lru_cache(maxsize=1)
def _create_default_ledger() -> AttemptLedger:
    """Create default ledger instance (thread-safe via lru_cache)."""
    return AttemptLedger()


def get_ledger() -> AttemptLedger:
    """Get the global attempt ledger instance (thread-safe)."""
    if _global_ledger is not None:
        return _global_ledger
    return _create_default_ledger()


def set_ledger(ledger: AttemptLedger) -> None:
    """Set the global attempt ledger instance."""
    global _global_ledger
    _global_ledger = ledger


def record_attempt_started(**kwargs: Any) -> None:
    get_ledger().attempt_started(**kwargs)


def record_attempt_ended(**kwargs: Any) -> None:
    get_ledger().attempt_ended(**kwargs)


def record_llm_attempted(**kwargs: Any) -> None:
    get_ledger().llm_attempted(**kwargs)


def record_tool_attempted(**kwargs: Any) -> None:
    get_ledger().tool_attempted(**kwargs)
