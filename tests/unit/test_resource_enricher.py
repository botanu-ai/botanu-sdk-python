# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for ResourceEnricher + set_bytes_transferred + cloud_provider kwarg.

These exercise the Phase C wiring that makes non-LLM spans actually price
above $0 in the cost worker. Without this path, every S3 PUT, DynamoDB op,
and egress byte lands in cost_infra_usd=0.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from botanu.processors.resource_enricher import (
    ResourceEnricher,
    _infer_bytes_transferred,
    _infer_cloud_provider,
)


def _readable_span(attrs: dict) -> MagicMock:
    """Stand-in for a ReadableSpan. ResourceEnricher only reads `.attributes`
    and calls `.set_attribute`, both of which are easy to mock."""
    span = MagicMock()
    span.attributes = dict(attrs)
    written: dict = {}

    def _set(key, value):
        written[key] = value

    span.set_attribute = MagicMock(side_effect=_set)
    span.written = written
    return span


class TestCloudProviderInference:
    def test_explicit_cloud_provider_wins(self):
        assert _infer_cloud_provider({"cloud.provider": "AWS"}) == "aws"

    def test_aws_service_attr_infers_aws(self):
        assert _infer_cloud_provider({"aws.service": "DynamoDB"}) == "aws"

    def test_aws_rpc_system(self):
        assert _infer_cloud_provider({"rpc.system": "aws-api"}) == "aws"

    def test_gcp_service_attr_infers_gcp(self):
        assert _infer_cloud_provider({"gcp.project_id": "my-proj"}) == "gcp"

    def test_azure_namespace_attr_infers_azure(self):
        assert _infer_cloud_provider({"azure.namespace": "Microsoft.Storage"}) == "azure"

    def test_db_system_dynamodb_infers_aws(self):
        assert _infer_cloud_provider({"db.system": "dynamodb"}) == "aws"

    def test_storage_system_s3_infers_aws(self):
        assert _infer_cloud_provider({"botanu.storage.system": "s3"}) == "aws"

    def test_messaging_system_pubsub_infers_gcp(self):
        assert _infer_cloud_provider({"messaging.system": "pubsub"}) == "gcp"

    def test_unknown_system_returns_none(self):
        assert _infer_cloud_provider({"db.system": "postgresql"}) is None

    def test_empty_attrs_returns_none(self):
        assert _infer_cloud_provider({}) is None


class TestBytesTransferredInference:
    def test_http_request_and_response_summed(self):
        assert _infer_bytes_transferred(
            {"http.request.body.size": 100, "http.response.body.size": 250}
        ) == 350

    def test_http_request_only(self):
        assert _infer_bytes_transferred({"http.request.body.size": 100}) == 100

    def test_botanu_data_bytes_read_fallback(self):
        # Fallback path: no http.* but DBTracker populated bytes_read
        assert _infer_bytes_transferred({"botanu.data.bytes_read": 512}) == 512

    def test_messaging_bytes_transferred_fallback(self):
        assert _infer_bytes_transferred({"botanu.messaging.bytes_transferred": 42}) == 42

    def test_no_bytes_attrs_returns_none(self):
        assert _infer_bytes_transferred({}) is None
        assert _infer_bytes_transferred({"db.system": "postgresql"}) is None

    def test_http_preferred_over_fallback(self):
        """When both http.* and botanu.data.* are present, use http.* only —
        otherwise we'd double-count."""
        attrs = {
            "http.request.body.size": 100,
            "http.response.body.size": 200,
            "botanu.data.bytes_read": 999,
        }
        assert _infer_bytes_transferred(attrs) == 300


class TestResourceEnricherOnEnd:
    def test_writes_inferred_cloud_provider_and_bytes(self):
        enricher = ResourceEnricher()
        span = _readable_span(
            {
                "db.system": "dynamodb",
                "http.request.body.size": 100,
                "http.response.body.size": 200,
            }
        )
        enricher.on_end(span)
        assert span.written == {
            "botanu.cloud_provider": "aws",
            "botanu.bytes_transferred": 300,
        }

    def test_does_not_overwrite_explicit_attrs(self):
        """Explicit set_bytes_transferred / cloud_provider= kwarg must win."""
        enricher = ResourceEnricher()
        span = _readable_span(
            {
                "db.system": "dynamodb",
                "http.response.body.size": 200,
                "botanu.cloud_provider": "azure",  # customer set this explicitly
                "botanu.bytes_transferred": 999,
            }
        )
        enricher.on_end(span)
        # Neither attribute should be overwritten
        assert span.written == {}

    def test_skips_llm_spans(self):
        """LLM spans price via token counts, not bytes. Writing bytes here
        would pollute cost_infra_usd."""
        enricher = ResourceEnricher()
        span = _readable_span(
            {
                "gen_ai.request.model": "claude-opus-4-6",
                "http.request.body.size": 100,
            }
        )
        enricher.on_end(span)
        assert span.written == {}

    def test_no_write_when_nothing_inferable(self):
        enricher = ResourceEnricher()
        span = _readable_span({"http.method": "GET"})
        enricher.on_end(span)
        assert span.written == {}

    def test_writes_cloud_only_when_bytes_unknown(self):
        enricher = ResourceEnricher()
        span = _readable_span({"db.system": "dynamodb"})
        enricher.on_end(span)
        assert span.written == {"botanu.cloud_provider": "aws"}

    def test_on_start_is_noop(self):
        """on_start runs before HTTP response size is known; do nothing there."""
        enricher = ResourceEnricher()
        span = MagicMock()
        span.set_attribute = MagicMock()
        enricher.on_start(span, None)
        span.set_attribute.assert_not_called()


class TestTrackerExplicitAPI:
    def test_db_set_bytes_transferred_sets_combined_attr(self):
        from botanu.tracking.data import DBTracker

        span = MagicMock()
        tracker = DBTracker(system="postgresql", operation="SELECT", span=span)
        tracker.set_bytes_transferred(sent=100, received=200)
        span.set_attribute.assert_called_with("botanu.bytes_transferred", 300)

    def test_storage_set_bytes_transferred(self):
        from botanu.tracking.data import StorageTracker

        span = MagicMock()
        tracker = StorageTracker(system="s3", operation="PUT", span=span)
        tracker.set_bytes_transferred(received=1024)
        span.set_attribute.assert_called_with("botanu.bytes_transferred", 1024)

    def test_messaging_set_bytes_transferred(self):
        from botanu.tracking.data import MessagingTracker

        span = MagicMock()
        tracker = MessagingTracker(
            system="sqs", operation="send", destination="q", span=span
        )
        tracker.set_bytes_transferred(sent=42)
        span.set_attribute.assert_called_with("botanu.bytes_transferred", 42)

    @pytest.mark.asyncio
    async def test_db_cloud_provider_kwarg_sets_attr(self):
        from botanu.tracking.data import track_db_operation

        with track_db_operation("postgresql", "SELECT", cloud_provider="aws"):
            pass
        # Success if the context manager accepted the kwarg without TypeError.


class TestConfigAutoInstrumentResources:
    def test_default_is_on(self):
        from botanu.sdk.config import BotanuConfig

        cfg = BotanuConfig()
        assert cfg.auto_instrument_resources is True

    def test_can_be_disabled(self):
        from botanu.sdk.config import BotanuConfig

        cfg = BotanuConfig(auto_instrument_resources=False)
        assert cfg.auto_instrument_resources is False
