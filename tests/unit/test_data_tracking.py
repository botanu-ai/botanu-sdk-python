# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for data tracking (DB, storage, messaging)."""

from __future__ import annotations

import pytest

from botanu.tracking.data import (
    DBOperation,
    MessagingOperation,
    StorageOperation,
    track_db_operation,
    track_messaging_operation,
    track_storage_operation,
)


class TestTrackDBOperation:
    """Tests for track_db_operation context manager."""

    def test_creates_span_with_operation(self, memory_exporter):
        with track_db_operation(
            system="postgresql",
            operation=DBOperation.SELECT,
            database="mydb",
        ) as tracker:
            tracker.set_result(rows_returned=10)

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert "db" in spans[0].name.lower() or "select" in spans[0].name.lower()

    def test_records_db_attributes(self, memory_exporter):
        with track_db_operation(
            system="postgresql",
            operation=DBOperation.INSERT,
            database="users_db",
        ) as tracker:
            tracker.set_result(rows_affected=1)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("db.system") == "postgresql"
        assert attrs.get("db.name") == "users_db"

    def test_records_error_on_exception(self, memory_exporter):
        with pytest.raises(ValueError):
            with track_db_operation(
                system="mysql",
                operation=DBOperation.SELECT,
            ):
                raise ValueError("Connection failed")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.data.error") == "ValueError"

    def test_set_table(self, memory_exporter):
        with track_db_operation(
            system="postgresql",
            operation=DBOperation.SELECT,
        ) as tracker:
            tracker.set_table("users", schema="public")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("db.collection.name") == "users"
        assert attrs.get("db.schema") == "public"

    def test_set_query_id(self, memory_exporter):
        with track_db_operation(
            system="snowflake",
            operation=DBOperation.SELECT,
        ) as tracker:
            tracker.set_query_id("01abc123-def4-5678")
            tracker.set_bytes_scanned(1024000)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.warehouse.query_id") == "01abc123-def4-5678"
        assert attrs.get("botanu.warehouse.bytes_scanned") == 1024000


class TestTrackStorageOperation:
    """Tests for track_storage_operation context manager."""

    def test_creates_span_for_read(self, memory_exporter):
        with track_storage_operation(
            system="s3",
            operation=StorageOperation.GET,
        ) as tracker:
            tracker.set_result(bytes_read=1024)

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1

    def test_records_storage_attributes(self, memory_exporter):
        with track_storage_operation(
            system="gcs",
            operation=StorageOperation.PUT,
        ) as tracker:
            tracker.set_bucket("data-bucket")
            tracker.set_result(bytes_written=2048)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.storage.system") == "gcs"
        assert attrs.get("botanu.storage.bucket") == "data-bucket"

    def test_records_error(self, memory_exporter):
        with pytest.raises(IOError):
            with track_storage_operation(
                system="s3",
                operation=StorageOperation.GET,
            ):
                raise OSError("Access denied")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.storage.error") == "OSError"  # IOError is alias for OSError

    def test_objects_count(self, memory_exporter):
        with track_storage_operation(
            system="s3",
            operation=StorageOperation.LIST,
        ) as tracker:
            tracker.set_result(objects_count=50)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.data.objects_count") == 50


class TestTrackMessagingOperation:
    """Tests for track_messaging_operation context manager."""

    def test_creates_span_for_publish(self, memory_exporter):
        with track_messaging_operation(
            system="kafka",
            operation=MessagingOperation.PUBLISH,
            destination="orders-topic",
        ) as tracker:
            tracker.set_result(message_count=1)

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1

    def test_records_messaging_attributes(self, memory_exporter):
        with track_messaging_operation(
            system="sqs",
            operation=MessagingOperation.RECEIVE,
            destination="my-queue",
        ) as tracker:
            tracker.set_result(message_count=5)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("messaging.system") == "sqs"
        assert attrs.get("messaging.destination.name") == "my-queue"

    def test_records_error(self, memory_exporter):
        with pytest.raises(TimeoutError):
            with track_messaging_operation(
                system="rabbitmq",
                operation=MessagingOperation.PUBLISH,
                destination="events",
            ):
                raise TimeoutError("Queue full")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.messaging.error") == "TimeoutError"

    def test_consume_operation(self, memory_exporter):
        with track_messaging_operation(
            system="kafka",
            operation=MessagingOperation.CONSUME,
            destination="events-topic",
        ) as tracker:
            tracker.set_result(message_count=10, bytes_transferred=4096)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("messaging.operation") == "consume"
        assert attrs.get("botanu.messaging.message_count") == 10
        assert attrs.get("botanu.messaging.bytes_transferred") == 4096


class TestOperationEnums:
    """Tests for operation type enums."""

    def test_db_operations(self):
        assert DBOperation.SELECT == "SELECT"
        assert DBOperation.INSERT == "INSERT"
        assert DBOperation.UPDATE == "UPDATE"
        assert DBOperation.DELETE == "DELETE"

    def test_storage_operations(self):
        assert StorageOperation.GET == "GET"
        assert StorageOperation.PUT == "PUT"
        assert StorageOperation.DELETE == "DELETE"
        assert StorageOperation.LIST == "LIST"

    def test_messaging_operations(self):
        assert MessagingOperation.PUBLISH == "publish"
        assert MessagingOperation.RECEIVE == "receive"
        assert MessagingOperation.CONSUME == "consume"


class TestSystemNormalization:
    """Tests for system name normalization maps."""

    def test_db_system_aliases(self, memory_exporter):
        from botanu.tracking.data import DB_SYSTEMS

        assert DB_SYSTEMS["postgres"] == "postgresql"
        assert DB_SYSTEMS["pg"] == "postgresql"
        assert DB_SYSTEMS["mongo"] == "mongodb"
        assert DB_SYSTEMS["sqlserver"] == "mssql"

    def test_storage_system_aliases(self):
        from botanu.tracking.data import STORAGE_SYSTEMS

        assert STORAGE_SYSTEMS["aws_s3"] == "s3"
        assert STORAGE_SYSTEMS["google_cloud_storage"] == "gcs"
        assert STORAGE_SYSTEMS["blob"] == "azure_blob"

    def test_messaging_system_aliases(self):
        from botanu.tracking.data import MESSAGING_SYSTEMS

        assert MESSAGING_SYSTEMS["aws_sqs"] == "sqs"
        assert MESSAGING_SYSTEMS["google_pubsub"] == "pubsub"
        assert MESSAGING_SYSTEMS["azure_servicebus"] == "servicebus"

    def test_db_alias_used_in_span(self, memory_exporter):
        """Alias 'pg' should normalize to 'postgresql' in the span."""
        with track_db_operation(system="pg", operation="SELECT") as tracker:
            tracker.set_result(rows_returned=1)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["db.system"] == "postgresql"

    def test_unknown_system_passthrough(self, memory_exporter):
        """Unknown systems should pass through as lowercase."""
        with track_db_operation(system="CockroachDB", operation="SELECT"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["db.system"] == "cockroachdb"


class TestDBTrackerMetadata:
    """Tests for DBTracker.add_metadata and set_bytes_scanned."""

    def test_add_metadata(self, memory_exporter):
        with track_db_operation(system="postgresql", operation="SELECT") as tracker:
            tracker.add_metadata(query_plan="seq_scan", cost_estimate=42.5)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.data.query_plan"] == "seq_scan"
        assert attrs["botanu.data.cost_estimate"] == 42.5

    def test_add_metadata_preserves_botanu_prefix(self, memory_exporter):
        with track_db_operation(system="postgresql", operation="SELECT") as tracker:
            tracker.add_metadata(**{"botanu.custom_key": "custom_val"})

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.custom_key"] == "custom_val"

    def test_set_bytes_scanned(self, memory_exporter):
        with track_db_operation(system="bigquery", operation="SELECT") as tracker:
            tracker.set_bytes_scanned(5_000_000)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.warehouse.bytes_scanned"] == 5_000_000
        assert tracker.bytes_read == 5_000_000

    def test_duration_finalized(self, memory_exporter):
        with track_db_operation(system="postgresql", operation="INSERT"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "botanu.data.duration_ms" in attrs
        assert attrs["botanu.data.duration_ms"] >= 0


class TestStorageTrackerMetadata:
    """Tests for StorageTracker.add_metadata."""

    def test_add_metadata(self, memory_exporter):
        with track_storage_operation(system="s3", operation="PUT") as tracker:
            tracker.add_metadata(content_type="application/json", region="us-east-1")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.storage.content_type"] == "application/json"
        assert attrs["botanu.storage.region"] == "us-east-1"

    def test_duration_finalized(self, memory_exporter):
        with track_storage_operation(system="gcs", operation="GET"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "botanu.storage.duration_ms" in attrs


class TestMessagingTrackerMetadata:
    """Tests for MessagingTracker.add_metadata and span kind."""

    def test_add_metadata(self, memory_exporter):
        with track_messaging_operation(
            system="kafka",
            operation="publish",
            destination="events",
        ) as tracker:
            tracker.add_metadata(partition=3, key="order-123")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.messaging.partition"] == 3
        assert attrs["botanu.messaging.key"] == "order-123"

    def test_publish_uses_producer_span_kind(self, memory_exporter):
        from opentelemetry.trace import SpanKind

        with track_messaging_operation(
            system="kafka",
            operation="publish",
            destination="topic",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        assert spans[0].kind == SpanKind.PRODUCER

    def test_consume_uses_consumer_span_kind(self, memory_exporter):
        from opentelemetry.trace import SpanKind

        with track_messaging_operation(
            system="kafka",
            operation="consume",
            destination="topic",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        assert spans[0].kind == SpanKind.CONSUMER

    def test_send_uses_producer_span_kind(self, memory_exporter):
        from opentelemetry.trace import SpanKind

        with track_messaging_operation(
            system="sqs",
            operation="send",
            destination="queue",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        assert spans[0].kind == SpanKind.PRODUCER

    def test_duration_finalized(self, memory_exporter):
        with track_messaging_operation(
            system="sqs",
            operation="receive",
            destination="q",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "botanu.messaging.duration_ms" in attrs


class TestStandaloneHelpers:
    """Tests for set_data_metrics and set_warehouse_metrics."""

    def test_set_data_metrics(self, memory_exporter):
        from opentelemetry import trace as otl_trace

        from botanu.tracking.data import set_data_metrics

        tracer = otl_trace.get_tracer("test")
        with tracer.start_as_current_span("test-data-metrics"):
            set_data_metrics(rows_returned=100, bytes_read=8192)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.data.rows_returned"] == 100
        assert attrs["botanu.data.bytes_read"] == 8192

    def test_set_data_metrics_no_active_span(self):
        from botanu.tracking.data import set_data_metrics

        # Should not raise when no recording span
        set_data_metrics(rows_returned=10)

    def test_set_warehouse_metrics(self, memory_exporter):
        from opentelemetry import trace as otl_trace

        from botanu.tracking.data import set_warehouse_metrics

        tracer = otl_trace.get_tracer("test")
        with tracer.start_as_current_span("test-warehouse"):
            set_warehouse_metrics(
                query_id="q-001",
                bytes_scanned=10_000_000,
                rows_returned=500,
                partitions_scanned=12,
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.warehouse.query_id"] == "q-001"
        assert attrs["botanu.warehouse.bytes_scanned"] == 10_000_000
        assert attrs["botanu.data.rows_returned"] == 500
        assert attrs["botanu.warehouse.partitions_scanned"] == 12

    def test_set_warehouse_metrics_no_active_span(self):
        from botanu.tracking.data import set_warehouse_metrics

        # Should not raise when no recording span
        set_warehouse_metrics(query_id="q-002", bytes_scanned=1000)


class TestKwargsPassthrough:
    """Tests for additional kwargs passed to context managers."""

    def test_db_operation_kwargs(self, memory_exporter):
        with track_db_operation(
            system="postgresql",
            operation="SELECT",
            statement="SELECT 1",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.data.statement"] == "SELECT 1"

    def test_storage_operation_kwargs(self, memory_exporter):
        with track_storage_operation(
            system="s3",
            operation="GET",
            bucket="my-bucket",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.storage.bucket"] == "my-bucket"

    def test_messaging_operation_kwargs(self, memory_exporter):
        with track_messaging_operation(
            system="kafka",
            operation="publish",
            destination="topic",
            partition_key="order-1",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.messaging.partition_key"] == "order-1"
