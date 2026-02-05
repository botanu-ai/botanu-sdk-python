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
