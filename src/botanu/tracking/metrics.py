# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Run metrics — reliable aggregates for dashboards and alerts.

Metrics are the "always-on truth" — they're not sampled like spans.

- ``botanu.run.completed`` (counter): Total runs by use_case, status, environment
- ``botanu.run.duration_ms`` (histogram): Run duration distribution
"""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram

logger = logging.getLogger(__name__)

_SDK_METER_NAME = "botanu_sdk"

meter = metrics.get_meter(_SDK_METER_NAME)

_run_completed_counter: Optional[Counter] = None
_run_duration_histogram: Optional[Histogram] = None


def _get_run_completed_counter() -> Counter:
    global _run_completed_counter
    if _run_completed_counter is None:
        _run_completed_counter = meter.create_counter(
            name="botanu.run.completed",
            description="Total number of completed runs",
            unit="1",
        )
    return _run_completed_counter


def _get_run_duration_histogram() -> Histogram:
    global _run_duration_histogram
    if _run_duration_histogram is None:
        _run_duration_histogram = meter.create_histogram(
            name="botanu.run.duration_ms",
            description="Run duration in milliseconds",
            unit="ms",
        )
    return _run_duration_histogram


def record_run_completed(
    use_case: str,
    status: str,
    environment: str,
    duration_ms: float,
    service_name: Optional[str] = None,
    workflow: Optional[str] = None,
) -> None:
    """Record a completed run in metrics.

    Called at the end of every run, regardless of whether the span is sampled.

    Args:
        use_case: Use case name (low cardinality).
        status: Outcome status (success/failure/partial/timeout/canceled).
        environment: Deployment environment.
        duration_ms: Run duration in milliseconds.
        service_name: Service name (optional).
        workflow: Workflow name (optional).
    """
    attrs = {
        "use_case": use_case,
        "status": status,
        "environment": environment,
    }
    if service_name:
        attrs["service.name"] = service_name
    if workflow:
        attrs["workflow"] = workflow

    try:
        _get_run_completed_counter().add(1, attrs)
    except Exception as exc:
        logger.debug("Failed to record run.completed metric: %s", exc)

    try:
        _get_run_duration_histogram().record(duration_ms, attrs)
    except Exception as exc:
        logger.debug("Failed to record run.duration_ms metric: %s", exc)
