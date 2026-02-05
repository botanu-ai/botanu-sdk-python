# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Data Tracking — Track database, storage, and messaging operations.

Usage::

    from botanu.tracking.data import track_db_operation, track_storage_operation

    with track_db_operation(system="postgresql", operation="SELECT") as db:
        result = cursor.execute("SELECT * FROM users WHERE active = true")
        db.set_result(rows_returned=len(result))
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

# =========================================================================
# System Normalization Maps
# =========================================================================

DB_SYSTEMS: Dict[str, str] = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "pg": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mssql": "mssql",
    "sqlserver": "mssql",
    "oracle": "oracle",
    "sqlite": "sqlite",
    "mongodb": "mongodb",
    "mongo": "mongodb",
    "dynamodb": "dynamodb",
    "cassandra": "cassandra",
    "couchdb": "couchdb",
    "firestore": "firestore",
    "cosmosdb": "cosmosdb",
    "redis": "redis",
    "memcached": "memcached",
    "elasticache": "elasticache",
    "elasticsearch": "elasticsearch",
    "opensearch": "opensearch",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "redshift": "redshift",
    "databricks": "databricks",
    "athena": "athena",
    "synapse": "synapse",
    "influxdb": "influxdb",
    "timescaledb": "timescaledb",
    "neo4j": "neo4j",
    "neptune": "neptune",
}

STORAGE_SYSTEMS: Dict[str, str] = {
    "s3": "s3",
    "aws_s3": "s3",
    "gcs": "gcs",
    "google_cloud_storage": "gcs",
    "blob": "azure_blob",
    "azure_blob": "azure_blob",
    "minio": "minio",
    "ceph": "ceph",
    "nfs": "nfs",
    "efs": "efs",
}

MESSAGING_SYSTEMS: Dict[str, str] = {
    "sqs": "sqs",
    "aws_sqs": "sqs",
    "sns": "sns",
    "kinesis": "kinesis",
    "eventbridge": "eventbridge",
    "pubsub": "pubsub",
    "google_pubsub": "pubsub",
    "servicebus": "servicebus",
    "azure_servicebus": "servicebus",
    "eventhub": "eventhub",
    "kafka": "kafka",
    "rabbitmq": "rabbitmq",
    "nats": "nats",
    "redis_pubsub": "redis_pubsub",
    "celery": "celery",
}


class DBOperation:
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    UPSERT = "UPSERT"
    MERGE = "MERGE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    INDEX = "INDEX"
    TRANSACTION = "TRANSACTION"
    BATCH = "BATCH"


class StorageOperation:
    GET = "GET"
    PUT = "PUT"
    DELETE = "DELETE"
    LIST = "LIST"
    HEAD = "HEAD"
    COPY = "COPY"
    MULTIPART_UPLOAD = "MULTIPART_UPLOAD"


class MessagingOperation:
    PUBLISH = "publish"
    CONSUME = "consume"
    RECEIVE = "receive"
    SEND = "send"
    SUBSCRIBE = "subscribe"


# =========================================================================
# Database Tracker
# =========================================================================


@dataclass
class DBTracker:
    """Tracks database operations."""

    system: str
    operation: str
    span: Optional[Span] = field(default=None, repr=False)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    rows_returned: int = 0
    rows_affected: int = 0
    bytes_read: int = 0
    bytes_written: int = 0

    def set_result(
        self,
        rows_returned: int = 0,
        rows_affected: int = 0,
        bytes_read: int = 0,
        bytes_written: int = 0,
    ) -> DBTracker:
        self.rows_returned = rows_returned
        self.rows_affected = rows_affected
        self.bytes_read = bytes_read
        self.bytes_written = bytes_written
        if self.span:
            if rows_returned > 0:
                self.span.set_attribute("botanu.data.rows_returned", rows_returned)
            if rows_affected > 0:
                self.span.set_attribute("botanu.data.rows_affected", rows_affected)
            if bytes_read > 0:
                self.span.set_attribute("botanu.data.bytes_read", bytes_read)
            if bytes_written > 0:
                self.span.set_attribute("botanu.data.bytes_written", bytes_written)
        return self

    def set_table(self, table_name: str, schema: Optional[str] = None) -> DBTracker:
        if self.span:
            self.span.set_attribute("db.collection.name", table_name)
            if schema:
                self.span.set_attribute("db.schema", schema)
        return self

    def set_query_id(self, query_id: str) -> DBTracker:
        if self.span:
            self.span.set_attribute("botanu.warehouse.query_id", query_id)
        return self

    def set_bytes_scanned(self, bytes_scanned: int) -> DBTracker:
        self.bytes_read = bytes_scanned
        if self.span:
            self.span.set_attribute("botanu.warehouse.bytes_scanned", bytes_scanned)
        return self

    def set_error(self, error: Exception) -> DBTracker:
        if self.span:
            self.span.set_status(Status(StatusCode.ERROR, str(error)))
            self.span.set_attribute("botanu.data.error", type(error).__name__)
            self.span.record_exception(error)
        return self

    def add_metadata(self, **kwargs: Any) -> DBTracker:
        if self.span:
            for key, value in kwargs.items():
                attr_key = key if key.startswith("botanu.") else f"botanu.data.{key}"
                self.span.set_attribute(attr_key, value)
        return self

    def _finalize(self) -> None:
        if not self.span:
            return
        duration_ms = (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000
        self.span.set_attribute("botanu.data.duration_ms", duration_ms)


@contextmanager
def track_db_operation(
    system: str,
    operation: str,
    database: Optional[str] = None,
    **kwargs: Any,
) -> Generator[DBTracker, None, None]:
    """Track a database operation.

    Args:
        system: Database system (postgresql, mysql, mongodb, …).
        operation: Type of operation (SELECT, INSERT, …).
        database: Database name (optional).
    """
    tracer = trace.get_tracer("botanu.data")
    normalized_system = DB_SYSTEMS.get(system.lower(), system.lower())

    with tracer.start_as_current_span(
        name=f"db.{normalized_system}.{operation.lower()}",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("db.system", normalized_system)
        span.set_attribute("db.operation", operation.upper())
        span.set_attribute("botanu.vendor", normalized_system)
        if database:
            span.set_attribute("db.name", database)
        for key, value in kwargs.items():
            span.set_attribute(f"botanu.data.{key}", value)

        tracker = DBTracker(system=normalized_system, operation=operation, span=span)
        try:
            yield tracker
        except Exception as exc:
            tracker.set_error(exc)
            raise
        finally:
            tracker._finalize()


# =========================================================================
# Storage Tracker
# =========================================================================


@dataclass
class StorageTracker:
    """Tracks storage operations."""

    system: str
    operation: str
    span: Optional[Span] = field(default=None, repr=False)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    objects_count: int = 0
    bytes_read: int = 0
    bytes_written: int = 0

    def set_result(
        self,
        objects_count: int = 0,
        bytes_read: int = 0,
        bytes_written: int = 0,
    ) -> StorageTracker:
        self.objects_count = objects_count
        self.bytes_read = bytes_read
        self.bytes_written = bytes_written
        if self.span:
            if objects_count > 0:
                self.span.set_attribute("botanu.data.objects_count", objects_count)
            if bytes_read > 0:
                self.span.set_attribute("botanu.data.bytes_read", bytes_read)
            if bytes_written > 0:
                self.span.set_attribute("botanu.data.bytes_written", bytes_written)
        return self

    def set_bucket(self, bucket: str) -> StorageTracker:
        if self.span:
            self.span.set_attribute("botanu.storage.bucket", bucket)
        return self

    def set_error(self, error: Exception) -> StorageTracker:
        if self.span:
            self.span.set_status(Status(StatusCode.ERROR, str(error)))
            self.span.set_attribute("botanu.storage.error", type(error).__name__)
            self.span.record_exception(error)
        return self

    def add_metadata(self, **kwargs: Any) -> StorageTracker:
        if self.span:
            for key, value in kwargs.items():
                attr_key = key if key.startswith("botanu.") else f"botanu.storage.{key}"
                self.span.set_attribute(attr_key, value)
        return self

    def _finalize(self) -> None:
        if not self.span:
            return
        duration_ms = (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000
        self.span.set_attribute("botanu.storage.duration_ms", duration_ms)


@contextmanager
def track_storage_operation(
    system: str,
    operation: str,
    **kwargs: Any,
) -> Generator[StorageTracker, None, None]:
    """Track a storage operation.

    Args:
        system: Storage system (s3, gcs, azure_blob, …).
        operation: Type of operation (GET, PUT, DELETE, …).
    """
    tracer = trace.get_tracer("botanu.storage")
    normalized_system = STORAGE_SYSTEMS.get(system.lower(), system.lower())

    with tracer.start_as_current_span(
        name=f"storage.{normalized_system}.{operation.lower()}",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("botanu.storage.system", normalized_system)
        span.set_attribute("botanu.storage.operation", operation.upper())
        span.set_attribute("botanu.vendor", normalized_system)
        for key, value in kwargs.items():
            span.set_attribute(f"botanu.storage.{key}", value)

        tracker = StorageTracker(system=normalized_system, operation=operation, span=span)
        try:
            yield tracker
        except Exception as exc:
            tracker.set_error(exc)
            raise
        finally:
            tracker._finalize()


# =========================================================================
# Messaging Tracker
# =========================================================================


@dataclass
class MessagingTracker:
    """Tracks messaging operations."""

    system: str
    operation: str
    destination: str
    span: Optional[Span] = field(default=None, repr=False)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    message_count: int = 0
    bytes_transferred: int = 0

    def set_result(
        self,
        message_count: int = 0,
        bytes_transferred: int = 0,
    ) -> MessagingTracker:
        self.message_count = message_count
        self.bytes_transferred = bytes_transferred
        if self.span:
            if message_count > 0:
                self.span.set_attribute("botanu.messaging.message_count", message_count)
            if bytes_transferred > 0:
                self.span.set_attribute("botanu.messaging.bytes_transferred", bytes_transferred)
        return self

    def set_error(self, error: Exception) -> MessagingTracker:
        if self.span:
            self.span.set_status(Status(StatusCode.ERROR, str(error)))
            self.span.set_attribute("botanu.messaging.error", type(error).__name__)
            self.span.record_exception(error)
        return self

    def add_metadata(self, **kwargs: Any) -> MessagingTracker:
        if self.span:
            for key, value in kwargs.items():
                attr_key = key if key.startswith("botanu.") else f"botanu.messaging.{key}"
                self.span.set_attribute(attr_key, value)
        return self

    def _finalize(self) -> None:
        if not self.span:
            return
        duration_ms = (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000
        self.span.set_attribute("botanu.messaging.duration_ms", duration_ms)


@contextmanager
def track_messaging_operation(
    system: str,
    operation: str,
    destination: str,
    **kwargs: Any,
) -> Generator[MessagingTracker, None, None]:
    """Track a messaging operation.

    Args:
        system: Messaging system (sqs, kafka, pubsub, …).
        operation: Type of operation (publish, consume, …).
        destination: Queue/topic name.
    """
    tracer = trace.get_tracer("botanu.messaging")
    normalized_system = MESSAGING_SYSTEMS.get(system.lower(), system.lower())
    span_kind = SpanKind.PRODUCER if operation in ("publish", "send") else SpanKind.CONSUMER

    with tracer.start_as_current_span(
        name=f"messaging.{normalized_system}.{operation.lower()}",
        kind=span_kind,
    ) as span:
        span.set_attribute("messaging.system", normalized_system)
        span.set_attribute("messaging.operation", operation.lower())
        span.set_attribute("messaging.destination.name", destination)
        span.set_attribute("botanu.vendor", normalized_system)
        for key, value in kwargs.items():
            span.set_attribute(f"botanu.messaging.{key}", value)

        tracker = MessagingTracker(
            system=normalized_system,
            operation=operation,
            destination=destination,
            span=span,
        )
        try:
            yield tracker
        except Exception as exc:
            tracker.set_error(exc)
            raise
        finally:
            tracker._finalize()


# =========================================================================
# Standalone Helpers
# =========================================================================


def set_data_metrics(
    rows_returned: int = 0,
    rows_affected: int = 0,
    bytes_read: int = 0,
    bytes_written: int = 0,
    objects_count: int = 0,
    span: Optional[Span] = None,
) -> None:
    """Set data operation metrics on the current span."""
    target_span = span or trace.get_current_span()
    if not target_span or not target_span.is_recording():
        return

    if rows_returned > 0:
        target_span.set_attribute("botanu.data.rows_returned", rows_returned)
    if rows_affected > 0:
        target_span.set_attribute("botanu.data.rows_affected", rows_affected)
    if bytes_read > 0:
        target_span.set_attribute("botanu.data.bytes_read", bytes_read)
    if bytes_written > 0:
        target_span.set_attribute("botanu.data.bytes_written", bytes_written)
    if objects_count > 0:
        target_span.set_attribute("botanu.data.objects_count", objects_count)


def set_warehouse_metrics(
    query_id: str,
    bytes_scanned: int,
    rows_returned: int = 0,
    partitions_scanned: int = 0,
    span: Optional[Span] = None,
) -> None:
    """Set data warehouse query metrics on the current span."""
    target_span = span or trace.get_current_span()
    if not target_span or not target_span.is_recording():
        return

    target_span.set_attribute("botanu.warehouse.query_id", query_id)
    target_span.set_attribute("botanu.warehouse.bytes_scanned", bytes_scanned)
    if rows_returned > 0:
        target_span.set_attribute("botanu.data.rows_returned", rows_returned)
    if partitions_scanned > 0:
        target_span.set_attribute("botanu.warehouse.partitions_scanned", partitions_scanned)
