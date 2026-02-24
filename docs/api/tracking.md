# Tracking API Reference

## LLM Tracking

### track_llm_call()

Context manager for tracking LLM/model calls.

```python
from botanu.tracking.llm import track_llm_call

with track_llm_call(
    provider: str,
    model: str,
    operation: str = ModelOperation.CHAT,
    client_request_id: Optional[str] = None,
    **kwargs: Any,
) -> Generator[LLMTracker, None, None]:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `str` | Required | LLM provider (openai, anthropic, etc.) |
| `model` | `str` | Required | Model name/ID (gpt-4, claude-3-opus, etc.) |
| `operation` | `str` | `"chat"` | Operation type (see ModelOperation) |
| `client_request_id` | `str` | `None` | Your tracking ID |
| `**kwargs` | `Any` | `{}` | Additional span attributes |

#### Returns

Yields an `LLMTracker` instance.

#### Example

```python
with track_llm_call(provider="openai", model="gpt-4") as tracker:
    response = await client.chat.completions.create(...)
    tracker.set_tokens(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
    tracker.set_request_id(response.id)
```

---

### LLMTracker

Tracker object for recording LLM call details.

#### Methods

##### set_tokens()

```python
def set_tokens(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> LLMTracker
```

Records token usage.

##### set_request_id()

```python
def set_request_id(
    provider_request_id: Optional[str] = None,
    client_request_id: Optional[str] = None,
) -> LLMTracker
```

Records request IDs for billing reconciliation.

##### set_response_model()

```python
def set_response_model(model: str) -> LLMTracker
```

Records the actual model used in response.

##### set_finish_reason()

```python
def set_finish_reason(reason: str) -> LLMTracker
```

Records the stop reason (stop, length, content_filter, etc.).

##### set_streaming()

```python
def set_streaming(is_streaming: bool = True) -> LLMTracker
```

Marks request as streaming.

##### set_cache_hit()

```python
def set_cache_hit(cache_hit: bool = True) -> LLMTracker
```

Marks as a cache hit.

##### set_attempt()

```python
def set_attempt(attempt_number: int) -> LLMTracker
```

Sets retry attempt number.

##### set_request_params()

```python
def set_request_params(
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop_sequences: Optional[List[str]] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
) -> LLMTracker
```

Records request parameters.

##### set_error()

```python
def set_error(error: Exception) -> LLMTracker
```

Records an error.

##### add_metadata()

```python
def add_metadata(**kwargs: Any) -> LLMTracker
```

Adds custom span attributes.

---

### track_tool_call()

Context manager for tracking tool/function calls.

```python
from botanu.tracking.llm import track_tool_call

with track_tool_call(
    tool_name: str,
    tool_call_id: Optional[str] = None,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Generator[ToolTracker, None, None]:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool_name` | `str` | Required | Name of the tool/function |
| `tool_call_id` | `str` | `None` | Tool call ID from LLM response |
| `provider` | `str` | `None` | Tool provider if external |

---

### ModelOperation

Constants for operation types.

| Constant | Value |
|----------|-------|
| `CHAT` | `"chat"` |
| `TEXT_COMPLETION` | `"text_completion"` |
| `EMBEDDINGS` | `"embeddings"` |
| `GENERATE_CONTENT` | `"generate_content"` |
| `EXECUTE_TOOL` | `"execute_tool"` |
| `CREATE_AGENT` | `"create_agent"` |
| `INVOKE_AGENT` | `"invoke_agent"` |
| `RERANK` | `"rerank"` |
| `IMAGE_GENERATION` | `"image_generation"` |
| `SPEECH_TO_TEXT` | `"speech_to_text"` |
| `TEXT_TO_SPEECH` | `"text_to_speech"` |

---

## Data Tracking

### track_db_operation()

Context manager for tracking database operations.

```python
from botanu.tracking.data import track_db_operation

with track_db_operation(
    system: str,
    operation: str,
    database: Optional[str] = None,
    **kwargs: Any,
) -> Generator[DBTracker, None, None]:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `str` | Required | Database system (postgresql, mongodb, etc.) |
| `operation` | `str` | Required | Operation type (SELECT, INSERT, etc.) |
| `database` | `str` | `None` | Database name |

#### Example

```python
with track_db_operation(system="postgresql", operation="SELECT") as db:
    result = await cursor.execute(query)
    db.set_result(rows_returned=len(result))
```

---

### DBTracker

#### Methods

##### set_result()

```python
def set_result(
    rows_returned: int = 0,
    rows_affected: int = 0,
    bytes_read: int = 0,
    bytes_written: int = 0,
) -> DBTracker
```

##### set_table()

```python
def set_table(table_name: str, schema: Optional[str] = None) -> DBTracker
```

##### set_query_id()

```python
def set_query_id(query_id: str) -> DBTracker
```

##### set_bytes_scanned()

```python
def set_bytes_scanned(bytes_scanned: int) -> DBTracker
```

##### set_error()

```python
def set_error(error: Exception) -> DBTracker
```

##### add_metadata()

```python
def add_metadata(**kwargs: Any) -> DBTracker
```

---

### track_storage_operation()

Context manager for tracking object storage operations.

```python
from botanu.tracking.data import track_storage_operation

with track_storage_operation(
    system: str,
    operation: str,
    **kwargs: Any,
) -> Generator[StorageTracker, None, None]:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `str` | Required | Storage system (s3, gcs, azure_blob, etc.) |
| `operation` | `str` | Required | Operation type (GET, PUT, DELETE, etc.) |

---

### StorageTracker

#### Methods

##### set_result()

```python
def set_result(
    objects_count: int = 0,
    bytes_read: int = 0,
    bytes_written: int = 0,
) -> StorageTracker
```

##### set_bucket()

```python
def set_bucket(bucket: str) -> StorageTracker
```

##### set_error()

```python
def set_error(error: Exception) -> StorageTracker
```

##### add_metadata()

```python
def add_metadata(**kwargs: Any) -> StorageTracker
```

---

### track_messaging_operation()

Context manager for tracking messaging operations.

```python
from botanu.tracking.data import track_messaging_operation

with track_messaging_operation(
    system: str,
    operation: str,
    destination: str,
    **kwargs: Any,
) -> Generator[MessagingTracker, None, None]:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `str` | Required | Messaging system (sqs, kafka, pubsub, etc.) |
| `operation` | `str` | Required | Operation type (publish, consume, etc.) |
| `destination` | `str` | Required | Queue/topic name |

---

### MessagingTracker

#### Methods

##### set_result()

```python
def set_result(
    message_count: int = 0,
    bytes_transferred: int = 0,
) -> MessagingTracker
```

##### set_error()

```python
def set_error(error: Exception) -> MessagingTracker
```

##### add_metadata()

```python
def add_metadata(**kwargs: Any) -> MessagingTracker
```

---

## Span Helpers

### emit_outcome()

Emit a business outcome for the current span.

```python
from botanu import emit_outcome

emit_outcome(
    status: str,
    *,
    value_type: Optional[str] = None,
    value_amount: Optional[float] = None,
    confidence: Optional[float] = None,
    reason: Optional[str] = None,
    error_type: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> None
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | `str` | Required | Outcome status: `"success"`, `"partial"`, `"failed"`, `"timeout"`, `"canceled"`, `"abandoned"` |
| `value_type` | `str` | `None` | Type of business value achieved |
| `value_amount` | `float` | `None` | Quantified value amount |
| `confidence` | `float` | `None` | Confidence score (0.0-1.0) |
| `reason` | `str` | `None` | Reason for the outcome |
| `error_type` | `str` | `None` | Error classification (e.g. `"TimeoutError"`) |
| `metadata` | `dict[str, str]` | `None` | Additional key-value metadata |

#### Example

```python
emit_outcome("success", value_type="items_processed", value_amount=1)
emit_outcome("failed", error_type="TimeoutError", reason="LLM took >30s")
```

---

### set_business_context()

Set business context attributes on the current span.

```python
from botanu import set_business_context

set_business_context(
    *,
    customer_id: Optional[str] = None,
    team: Optional[str] = None,
    cost_center: Optional[str] = None,
    region: Optional[str] = None,
) -> None
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `customer_id` | `str` | `None` | Customer identifier |
| `team` | `str` | `None` | Team or department |
| `cost_center` | `str` | `None` | Cost center for financial tracking |
| `region` | `str` | `None` | Geographic region |

---

## Context Helpers

### get_run_id()

Get the current run ID from baggage.

```python
from botanu import get_run_id

run_id = get_run_id()
```

### get_workflow()

Get the current workflow name from baggage.

```python
from botanu import get_workflow

workflow = get_workflow()
```

### get_baggage()

Get a baggage value by key.

```python
from botanu import get_baggage

value = get_baggage("botanu.tenant_id")
```

### set_baggage()

Set a baggage value.

```python
from botanu import set_baggage

set_baggage("botanu.custom_field", "my_value")
```

### get_current_span()

Get the current active span.

```python
from botanu import get_current_span

span = get_current_span()
span.set_attribute("custom.attribute", "value")
```

## See Also

- [LLM Tracking](../tracking/llm-tracking.md) - Detailed LLM tracking guide
- [Data Tracking](../tracking/data-tracking.md) - Data operation tracking
- [Outcomes](../tracking/outcomes.md) - Outcome recording
