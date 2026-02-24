# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Run Context - The core data model for Botanu runs.

A "Run" is orthogonal to tracing:
- Trace context (W3C): ties distributed spans together (trace_id, span_id)
- Run context (Botanu): ties business execution together (run_id, workflow, outcome)

Invariant: A run can span multiple traces (retries, async fanout).
The run_id must remain stable across those boundaries.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Union


def generate_run_id() -> str:
    """Generate a UUIDv7-style sortable run ID.

    UUIDv7 provides:
    - Sortable by time (first 48 bits are millisecond timestamp)
    - Globally unique
    - Compatible with UUID format

    Uses ``os.urandom()`` for ~2x faster generation than ``secrets``.
    """
    timestamp_ms = int(time.time() * 1000)

    uuid_bytes = bytearray(16)
    uuid_bytes[0] = (timestamp_ms >> 40) & 0xFF
    uuid_bytes[1] = (timestamp_ms >> 32) & 0xFF
    uuid_bytes[2] = (timestamp_ms >> 24) & 0xFF
    uuid_bytes[3] = (timestamp_ms >> 16) & 0xFF
    uuid_bytes[4] = (timestamp_ms >> 8) & 0xFF
    uuid_bytes[5] = timestamp_ms & 0xFF

    random_bytes = os.urandom(10)
    uuid_bytes[6] = 0x70 | (random_bytes[0] & 0x0F)
    uuid_bytes[7] = random_bytes[1]
    uuid_bytes[8] = 0x80 | (random_bytes[2] & 0x3F)
    uuid_bytes[9:16] = random_bytes[3:10]

    hex_str = uuid_bytes.hex()
    return f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"


class RunStatus(str, Enum):
    """Run outcome status."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELED = "canceled"


@dataclass
class RunOutcome:
    """Outcome attached at run completion."""

    status: RunStatus
    reason_code: Optional[str] = None
    error_class: Optional[str] = None
    value_type: Optional[str] = None
    value_amount: Optional[float] = None
    confidence: Optional[float] = None


@dataclass
class RunContext:
    """Canonical run context data model.

    Propagated via W3C Baggage and stored as span attributes.

    Retry model:
        Each attempt gets a NEW run_id for clean cost accounting.
        ``root_run_id`` stays stable across all attempts.
    """

    run_id: str
    workflow: str
    event_id: str
    customer_id: str
    environment: str
    workflow_version: Optional[str] = None
    tenant_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    root_run_id: Optional[str] = None
    attempt: int = 1
    retry_of_run_id: Optional[str] = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: Optional[float] = None
    cancelled: bool = False
    cancelled_at: Optional[float] = None
    outcome: Optional[RunOutcome] = None

    def __post_init__(self) -> None:
        if self.root_run_id is None:
            object.__setattr__(self, "root_run_id", self.run_id)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        workflow: str,
        event_id: str,
        customer_id: str,
        workflow_version: Optional[str] = None,
        environment: Optional[str] = None,
        tenant_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        root_run_id: Optional[str] = None,
        attempt: int = 1,
        retry_of_run_id: Optional[str] = None,
        deadline_seconds: Optional[float] = None,
    ) -> RunContext:
        """Create a new RunContext with auto-generated run_id."""
        env = environment or os.getenv("BOTANU_ENVIRONMENT") or os.getenv("DEPLOYMENT_ENVIRONMENT") or "production"
        run_id = generate_run_id()
        deadline = None
        if deadline_seconds is not None:
            deadline = time.time() + deadline_seconds

        return cls(
            run_id=run_id,
            workflow=workflow,
            event_id=event_id,
            customer_id=customer_id,
            environment=env,
            workflow_version=workflow_version,
            tenant_id=tenant_id,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id or run_id,
            attempt=attempt,
            retry_of_run_id=retry_of_run_id,
            deadline=deadline,
        )

    @classmethod
    def create_retry(cls, previous: RunContext) -> RunContext:
        """Create a new RunContext for a retry attempt."""
        return cls.create(
            workflow=previous.workflow,
            event_id=previous.event_id,
            customer_id=previous.customer_id,
            workflow_version=previous.workflow_version,
            environment=previous.environment,
            tenant_id=previous.tenant_id,
            parent_run_id=previous.parent_run_id,
            root_run_id=previous.root_run_id,
            attempt=previous.attempt + 1,
            retry_of_run_id=previous.run_id,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_past_deadline(self) -> bool:
        if self.deadline is None:
            return False
        return time.time() > self.deadline

    def is_cancelled(self) -> bool:
        return self.cancelled or self.is_past_deadline()

    def request_cancellation(self, reason: str = "user") -> None:
        self.cancelled = True
        self.cancelled_at = time.time()

    def remaining_time_seconds(self) -> Optional[float]:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - time.time())

    def complete(
        self,
        status: RunStatus,
        reason_code: Optional[str] = None,
        error_class: Optional[str] = None,
        value_type: Optional[str] = None,
        value_amount: Optional[float] = None,
        confidence: Optional[float] = None,
    ) -> None:
        self.outcome = RunOutcome(
            status=status,
            reason_code=reason_code,
            error_class=error_class,
            value_type=value_type,
            value_amount=value_amount,
            confidence=confidence,
        )

    @property
    def duration_ms(self) -> Optional[float]:
        if self.outcome is None:
            return None
        return (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_baggage_dict(self, lean_mode: Optional[bool] = None) -> Dict[str, str]:
        """Convert to dict for W3C Baggage propagation."""
        if lean_mode is None:
            env_mode = os.getenv("BOTANU_PROPAGATION_MODE", "lean")
            lean_mode = env_mode != "full"

        baggage: Dict[str, str] = {
            "botanu.run_id": self.run_id,
            "botanu.workflow": self.workflow,
            "botanu.event_id": self.event_id,
            "botanu.customer_id": self.customer_id,
        }
        if lean_mode:
            return baggage

        baggage["botanu.environment"] = self.environment
        if self.tenant_id:
            baggage["botanu.tenant_id"] = self.tenant_id
        if self.parent_run_id:
            baggage["botanu.parent_run_id"] = self.parent_run_id
        if self.root_run_id and self.root_run_id != self.run_id:
            baggage["botanu.root_run_id"] = self.root_run_id
        if self.attempt > 1:
            baggage["botanu.attempt"] = str(self.attempt)
        if self.retry_of_run_id:
            baggage["botanu.retry_of_run_id"] = self.retry_of_run_id
        if self.deadline is not None:
            baggage["botanu.deadline"] = str(int(self.deadline * 1000))
        if self.cancelled:
            baggage["botanu.cancelled"] = "true"
        return baggage

    def to_span_attributes(self) -> Dict[str, Union[str, float, int, bool]]:
        """Convert to dict for span attributes."""
        attrs: Dict[str, Union[str, float, int, bool]] = {
            "botanu.run_id": self.run_id,
            "botanu.workflow": self.workflow,
            "botanu.event_id": self.event_id,
            "botanu.customer_id": self.customer_id,
            "botanu.environment": self.environment,
            "botanu.run.start_time": self.start_time.isoformat(),
        }
        if self.workflow_version:
            attrs["botanu.workflow.version"] = self.workflow_version
        if self.tenant_id:
            attrs["botanu.tenant_id"] = self.tenant_id
        if self.parent_run_id:
            attrs["botanu.parent_run_id"] = self.parent_run_id
        attrs["botanu.root_run_id"] = self.root_run_id or self.run_id
        attrs["botanu.attempt"] = self.attempt
        if self.retry_of_run_id:
            attrs["botanu.retry_of_run_id"] = self.retry_of_run_id
        if self.deadline is not None:
            attrs["botanu.run.deadline_ts"] = self.deadline
        if self.cancelled:
            attrs["botanu.run.cancelled"] = True
            if self.cancelled_at:
                attrs["botanu.run.cancelled_at"] = self.cancelled_at
        if self.outcome:
            attrs["botanu.outcome.status"] = self.outcome.status.value
            if self.outcome.reason_code:
                attrs["botanu.outcome.reason_code"] = self.outcome.reason_code
            if self.outcome.error_class:
                attrs["botanu.outcome.error_class"] = self.outcome.error_class
            if self.outcome.value_type:
                attrs["botanu.outcome.value_type"] = self.outcome.value_type
            if self.outcome.value_amount is not None:
                attrs["botanu.outcome.value_amount"] = self.outcome.value_amount
            if self.outcome.confidence is not None:
                attrs["botanu.outcome.confidence"] = self.outcome.confidence
            if self.duration_ms is not None:
                attrs["botanu.run.duration_ms"] = self.duration_ms
        return attrs

    @classmethod
    def from_baggage(cls, baggage: Dict[str, str]) -> Optional[RunContext]:
        """Reconstruct RunContext from baggage dict."""
        run_id = baggage.get("botanu.run_id")
        workflow = baggage.get("botanu.workflow")
        if not run_id or not workflow:
            return None

        attempt_str = baggage.get("botanu.attempt", "1")
        try:
            attempt = int(attempt_str)
        except ValueError:
            attempt = 1

        deadline: Optional[float] = None
        deadline_str = baggage.get("botanu.deadline")
        if deadline_str:
            try:
                deadline = float(deadline_str) / 1000.0
            except ValueError:
                pass

        cancelled = baggage.get("botanu.cancelled", "").lower() == "true"

        event_id = baggage.get("botanu.event_id", "")
        customer_id = baggage.get("botanu.customer_id", "")

        return cls(
            run_id=run_id,
            workflow=workflow,
            event_id=event_id,
            customer_id=customer_id,
            environment=baggage.get("botanu.environment", "unknown"),
            tenant_id=baggage.get("botanu.tenant_id"),
            parent_run_id=baggage.get("botanu.parent_run_id"),
            root_run_id=baggage.get("botanu.root_run_id") or run_id,
            attempt=attempt,
            retry_of_run_id=baggage.get("botanu.retry_of_run_id"),
            deadline=deadline,
            cancelled=cancelled,
        )
