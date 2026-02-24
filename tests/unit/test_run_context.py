# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for RunContext model."""

from __future__ import annotations

import os
import re
import time
from unittest import mock

from botanu.models.run_context import (
    RunContext,
    RunStatus,
    generate_run_id,
)


class TestGenerateRunId:
    """Tests for UUIDv7 generation."""

    def test_format_is_uuid(self):
        """run_id should be valid UUID format."""
        run_id = generate_run_id()
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, run_id), f"Invalid UUID format: {run_id}"

    def test_uniqueness(self):
        """Generated IDs should be unique."""
        ids = [generate_run_id() for _ in range(1000)]
        assert len(set(ids)) == 1000

    def test_sortable_by_time(self):
        """IDs generated later should sort after earlier ones."""
        id1 = generate_run_id()
        time.sleep(0.002)
        id2 = generate_run_id()
        assert id1 < id2


class TestRunContextCreate:
    """Tests for RunContext.create factory."""

    def test_creates_with_required_fields(self):
        ctx = RunContext.create(workflow="Customer Support", event_id="evt-1", customer_id="cust-1")
        assert ctx.run_id is not None
        assert ctx.workflow == "Customer Support"
        assert ctx.event_id == "evt-1"
        assert ctx.customer_id == "cust-1"
        assert ctx.environment == "production"  # default
        assert ctx.attempt == 1

    def test_root_run_id_defaults_to_run_id(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1")
        assert ctx.root_run_id == ctx.run_id

    def test_accepts_custom_root_run_id(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1", root_run_id="custom-root")
        assert ctx.root_run_id == "custom-root"

    def test_environment_from_env_var(self):
        with mock.patch.dict(os.environ, {"BOTANU_ENVIRONMENT": "staging"}):
            ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1")
            assert ctx.environment == "staging"

    def test_explicit_environment_overrides_env_var(self):
        with mock.patch.dict(os.environ, {"BOTANU_ENVIRONMENT": "staging"}):
            ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1", environment="production")
            assert ctx.environment == "production"


class TestRunContextRetry:
    """Tests for retry handling."""

    def test_create_retry_increments_attempt(self):
        original = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1")
        retry = RunContext.create_retry(original)

        assert retry.attempt == 2
        assert retry.retry_of_run_id == original.run_id
        assert retry.root_run_id == original.root_run_id
        assert retry.run_id != original.run_id

    def test_create_retry_preserves_event_and_customer(self):
        original = RunContext.create(workflow="test", event_id="ticket-42", customer_id="bigretail")
        retry = RunContext.create_retry(original)

        assert retry.event_id == "ticket-42"
        assert retry.customer_id == "bigretail"

    def test_multiple_retries_preserve_root(self):
        original = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1")
        retry1 = RunContext.create_retry(original)
        retry2 = RunContext.create_retry(retry1)

        assert retry2.attempt == 3
        assert retry2.root_run_id == original.run_id


class TestRunContextDeadline:
    """Tests for deadline handling."""

    def test_deadline_seconds(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1", deadline_seconds=10.0)
        assert ctx.deadline is not None
        assert ctx.deadline > time.time()

    def test_is_past_deadline(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1", deadline_seconds=0.001)
        time.sleep(0.01)
        assert ctx.is_past_deadline() is True

    def test_remaining_time_seconds(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1", deadline_seconds=10.0)
        remaining = ctx.remaining_time_seconds()
        assert remaining is not None
        assert 9.0 < remaining <= 10.0


class TestRunContextCancellation:
    """Tests for cancellation handling."""

    def test_request_cancellation(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1")
        assert ctx.is_cancelled() is False

        ctx.request_cancellation("user")
        assert ctx.is_cancelled() is True
        assert ctx.cancelled_at is not None


class TestRunContextOutcome:
    """Tests for outcome recording."""

    def test_complete_sets_outcome(self):
        ctx = RunContext.create(workflow="test", event_id="evt-1", customer_id="cust-1")
        ctx.complete(
            status=RunStatus.SUCCESS,
            value_type="tickets_resolved",
            value_amount=1.0,
        )

        assert ctx.outcome is not None
        assert ctx.outcome.status == RunStatus.SUCCESS
        assert ctx.outcome.value_type == "tickets_resolved"
        assert ctx.outcome.value_amount == 1.0


class TestRunContextSerialization:
    """Tests for baggage and span attribute serialization."""

    def test_to_baggage_dict_lean_mode(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "lean"}):
            ctx = RunContext.create(
                workflow="Customer Support",
                event_id="ticket-42",
                customer_id="bigretail",
                tenant_id="tenant-123",
            )
            baggage = ctx.to_baggage_dict()

            # Lean mode includes run_id, workflow, event_id, customer_id
            assert "botanu.run_id" in baggage
            assert "botanu.workflow" in baggage
            assert baggage["botanu.event_id"] == "ticket-42"
            assert baggage["botanu.customer_id"] == "bigretail"
            assert "botanu.tenant_id" not in baggage

    def test_to_baggage_dict_full_mode(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "full"}):
            ctx = RunContext.create(
                workflow="Customer Support",
                event_id="ticket-42",
                customer_id="bigretail",
                tenant_id="tenant-123",
            )
            baggage = ctx.to_baggage_dict()

            assert baggage["botanu.event_id"] == "ticket-42"
            assert baggage["botanu.customer_id"] == "bigretail"
            assert baggage["botanu.tenant_id"] == "tenant-123"

    def test_to_span_attributes(self):
        ctx = RunContext.create(
            workflow="Customer Support",
            event_id="ticket-42",
            customer_id="bigretail",
            tenant_id="tenant-123",
        )
        attrs = ctx.to_span_attributes()

        assert attrs["botanu.run_id"] == ctx.run_id
        assert attrs["botanu.workflow"] == "Customer Support"
        assert attrs["botanu.event_id"] == "ticket-42"
        assert attrs["botanu.customer_id"] == "bigretail"
        assert attrs["botanu.tenant_id"] == "tenant-123"

    def test_from_baggage_roundtrip(self):
        original = RunContext.create(
            workflow="test",
            event_id="ticket-42",
            customer_id="bigretail",
            tenant_id="tenant-abc",
        )
        baggage = original.to_baggage_dict(lean_mode=False)
        restored = RunContext.from_baggage(baggage)

        assert restored is not None
        assert restored.run_id == original.run_id
        assert restored.workflow == original.workflow
        assert restored.event_id == original.event_id
        assert restored.customer_id == original.customer_id
        assert restored.tenant_id == original.tenant_id

    def test_from_baggage_returns_none_for_missing_fields(self):
        result = RunContext.from_baggage({})
        assert result is None

        result = RunContext.from_baggage({"botanu.run_id": "some-id"})
        assert result is None
