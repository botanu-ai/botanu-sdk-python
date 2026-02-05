# Data Tracking

Track database, storage, and messaging operations for complete cost visibility.

## Overview

Data operations often contribute significantly to AI workflow costs. Botanu provides tracking for:

- **Databases** - SQL, NoSQL, data warehouses
- **Object Storage** - S3, GCS, Azure Blob
- **Messaging** - SQS, Kafka, Pub/Sub

## Database Tracking

### Basic Usage

```python
from botanu.tracking.data import track_db_operation

with track_db_operation(system="postgresql", operation="SELECT") as db:
    result = await cursor.execute("SELECT * FROM users WHERE active = true")
    db.set_result(rows_returned=len(result))
```

### DBTracker Methods

#### set_result()

Record query results:

```python
db.set_result(
    rows_returned=100,    # For SELECT queries
    rows_affected=5,      # For INSERT/UPDATE/DELETE
    bytes_read=10240,     # Data read
    bytes_written=2048,   # Data written
)
```

#### set_table()

Record table information:

```python
db.set_table("users", schema="public")
```

#### set_query_id()

For data warehouses with query IDs:

```python
db.set_query_id("01abc-def-...")
```

#### set_bytes_scanned()

For pay-per-query warehouses:

```python
db.set_bytes_scanned(1073741824)  # 1 GB
```

#### set_error()

Record errors (automatically called on exceptions):

```python
db.set_error(exception)
```

#### add_metadata()

Add custom attributes:

```python
db.add_metadata(
    query_type="aggregation",
    cache_hit=True,
)
```

### Database Operations

Use `DBOperation` constants:

```python
from botanu.tracking.data import track_db_operation, DBOperation

with track_db_operation(system="postgresql", operation=DBOperation.SELECT):
    ...

with track_db_operation(system="postgresql", operation=DBOperation.INSERT):
    ...
```

Available operations:

| Constant | Description |
|----------|-------------|
| `SELECT` | Read queries |
| `INSERT` | Insert data |
| `UPDATE` | Update data |
| `DELETE` | Delete data |
| `UPSERT` | Insert or update |
| `MERGE` | Merge operations |
| `CREATE` | Create tables/indexes |
| `DROP` | Drop objects |
| `ALTER` | Alter schema |
| `INDEX` | Index operations |
| `TRANSACTION` | Transaction control |
| `BATCH` | Batch operations |

### System Normalization

Database systems are automatically normalized:

| Input | Normalized |
|-------|------------|
| `postgresql`, `postgres`, `pg` | `postgresql` |
| `mysql` | `mysql` |
| `mongodb`, `mongo` | `mongodb` |
| `dynamodb` | `dynamodb` |
| `redis` | `redis` |
| `elasticsearch` | `elasticsearch` |
| `snowflake` | `snowflake` |
| `bigquery` | `bigquery` |
| `redshift` | `redshift` |

## Storage Tracking

### Basic Usage

```python
from botanu.tracking.data import track_storage_operation

with track_storage_operation(system="s3", operation="PUT") as storage:
    await s3_client.put_object(Bucket="my-bucket", Key="file.txt", Body=data)
    storage.set_result(bytes_written=len(data))
```

### StorageTracker Methods

#### set_result()

Record operation results:

```python
storage.set_result(
    objects_count=10,      # Number of objects
    bytes_read=1048576,    # Data downloaded
    bytes_written=2097152, # Data uploaded
)
```

#### set_bucket()

Record bucket name:

```python
storage.set_bucket("my-data-bucket")
```

#### set_error()

Record errors:

```python
storage.set_error(exception)
```

#### add_metadata()

Add custom attributes:

```python
storage.add_metadata(
    storage_class="GLACIER",
    encryption="AES256",
)
```

### Storage Operations

| Constant | Description |
|----------|-------------|
| `GET` | Download object |
| `PUT` | Upload object |
| `DELETE` | Delete object |
| `LIST` | List objects |
| `HEAD` | Get metadata |
| `COPY` | Copy object |
| `MULTIPART_UPLOAD` | Multipart upload |

### System Normalization

| Input | Normalized |
|-------|------------|
| `s3`, `aws_s3` | `s3` |
| `gcs`, `google_cloud_storage` | `gcs` |
| `blob`, `azure_blob` | `azure_blob` |
| `minio` | `minio` |

## Messaging Tracking

### Basic Usage

```python
from botanu.tracking.data import track_messaging_operation

with track_messaging_operation(system="sqs", operation="publish", destination="my-queue") as msg:
    await sqs_client.send_message(QueueUrl=queue_url, MessageBody=message)
    msg.set_result(message_count=1, bytes_transferred=len(message))
```

### MessagingTracker Methods

#### set_result()

Record operation results:

```python
msg.set_result(
    message_count=10,
    bytes_transferred=4096,
)
```

#### set_error()

Record errors:

```python
msg.set_error(exception)
```

#### add_metadata()

Add custom attributes:

```python
msg.add_metadata(
    message_group_id="group-1",
    deduplication_id="dedup-123",
)
```

### Messaging Operations

| Constant | Description |
|----------|-------------|
| `publish` | Send message |
| `consume` | Receive and process message |
| `receive` | Receive message |
| `send` | Send message (alias for publish) |
| `subscribe` | Subscribe to topic |

### System Normalization

| Input | Normalized |
|-------|------------|
| `sqs`, `aws_sqs` | `sqs` |
| `sns` | `sns` |
| `kinesis` | `kinesis` |
| `pubsub`, `google_pubsub` | `pubsub` |
| `kafka` | `kafka` |
| `rabbitmq` | `rabbitmq` |
| `celery` | `celery` |

## Standalone Helpers

### set_data_metrics()

Set data metrics on the current span:

```python
from botanu.tracking.data import set_data_metrics

set_data_metrics(
    rows_returned=100,
    rows_affected=5,
    bytes_read=10240,
    bytes_written=2048,
    objects_count=10,
)
```

### set_warehouse_metrics()

For data warehouse queries:

```python
from botanu.tracking.data import set_warehouse_metrics

set_warehouse_metrics(
    query_id="01abc-def-...",
    bytes_scanned=1073741824,
    rows_returned=1000,
    partitions_scanned=5,
)
```

## Example: Complete Data Pipeline

```python
from botanu import botanu_use_case, emit_outcome
from botanu.tracking.data import (
    track_db_operation,
    track_storage_operation,
    track_messaging_operation,
    DBOperation,
)
from botanu.tracking.llm import track_llm_call

@botanu_use_case("ETL Pipeline")
async def process_batch(batch_id: str):
    """Complete ETL pipeline with cost tracking."""

    # 1. Read from data warehouse
    with track_db_operation(system="snowflake", operation=DBOperation.SELECT) as db:
        db.set_query_id(batch_id)
        rows = await snowflake_client.execute(
            "SELECT * FROM raw_data WHERE batch_id = %s",
            batch_id
        )
        db.set_result(rows_returned=len(rows))
        db.set_bytes_scanned(rows.bytes_scanned)

    # 2. Process with LLM
    processed = []
    for row in rows:
        with track_llm_call(provider="openai", model="gpt-4") as llm:
            result = await analyze_row(row)
            llm.set_tokens(input_tokens=result.input_tokens, output_tokens=result.output_tokens)
            processed.append(result)

    # 3. Write to storage
    with track_storage_operation(system="s3", operation="PUT") as storage:
        storage.set_bucket("processed-data")
        await s3_client.put_object(
            Bucket="processed-data",
            Key=f"batch/{batch_id}.json",
            Body=json.dumps(processed)
        )
        storage.set_result(bytes_written=len(json.dumps(processed)))

    # 4. Write to database
    with track_db_operation(system="postgresql", operation=DBOperation.INSERT) as db:
        await pg_client.executemany(
            "INSERT INTO processed_data VALUES (%s, %s, %s)",
            [(r.id, r.result, r.score) for r in processed]
        )
        db.set_result(rows_affected=len(processed))

    # 5. Publish completion event
    with track_messaging_operation(system="sqs", operation="publish", destination="batch-complete") as msg:
        await sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"batch_id": batch_id, "count": len(processed)})
        )
        msg.set_result(message_count=1)

    emit_outcome("success", value_type="batches_processed", value_amount=1)
    return processed
```

## Span Attributes

### Database Spans

| Attribute | Description |
|-----------|-------------|
| `db.system` | Database system (normalized) |
| `db.operation` | Operation type |
| `db.name` | Database name |
| `db.collection.name` | Table/collection name |
| `botanu.vendor` | Vendor for cost attribution |
| `botanu.data.rows_returned` | Rows returned |
| `botanu.data.rows_affected` | Rows modified |
| `botanu.data.bytes_read` | Bytes read |
| `botanu.data.bytes_written` | Bytes written |
| `botanu.warehouse.query_id` | Warehouse query ID |
| `botanu.warehouse.bytes_scanned` | Bytes scanned |

### Storage Spans

| Attribute | Description |
|-----------|-------------|
| `botanu.storage.system` | Storage system |
| `botanu.storage.operation` | Operation type |
| `botanu.storage.bucket` | Bucket name |
| `botanu.vendor` | Vendor for cost attribution |
| `botanu.data.objects_count` | Objects processed |
| `botanu.data.bytes_read` | Bytes downloaded |
| `botanu.data.bytes_written` | Bytes uploaded |

### Messaging Spans

| Attribute | Description |
|-----------|-------------|
| `messaging.system` | Messaging system |
| `messaging.operation` | Operation type |
| `messaging.destination.name` | Queue/topic name |
| `botanu.vendor` | Vendor for cost attribution |
| `botanu.messaging.message_count` | Messages processed |
| `botanu.messaging.bytes_transferred` | Bytes transferred |

## See Also

- [LLM Tracking](llm-tracking.md) - AI model tracking
- [Outcomes](outcomes.md) - Recording business outcomes
- [Best Practices](../patterns/best-practices.md) - Tracking best practices
