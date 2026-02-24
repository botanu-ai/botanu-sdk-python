# Outcomes

Record business outcomes to enable cost-per-outcome analysis.

## Overview

Outcomes connect infrastructure costs to business value. By recording what each event achieved, you can calculate the true ROI of your AI workflows.

**Terminology:**
- An **event** is one business transaction (e.g., a customer request, a pipeline trigger).
- A **run** is one execution attempt within an event.
- An event will have an **outcome** describing what was achieved.

## Basic Usage

```python
from botanu import botanu_workflow, emit_outcome

@botanu_workflow("process-items", event_id=request.id, customer_id=customer.id)
async def handle_request():
    result = await do_work()

    # Record the business outcome
    emit_outcome("success", value_type="items_processed", value_amount=result.count)
```

## emit_outcome() Parameters

```python
emit_outcome(
    status: str,                    # Required: "success", "partial", "failed", "timeout", "canceled", "abandoned"
    *,
    value_type: str = None,         # What was achieved
    value_amount: float = None,     # How much
    confidence: float = None,       # Confidence score (0.0-1.0)
    reason: str = None,             # Why (especially for failures)
    error_type: str = None,         # Error classification
    metadata: dict = None,          # Additional key-value pairs
)
```

### status

The outcome status:

| Status | Description | Example |
|--------|-------------|---------|
| `success` | Fully achieved goal | All items processed |
| `partial` | Partially achieved | 3 of 5 items processed |
| `failed` | Did not achieve goal | Error during processing |
| `timeout` | Timed out before completing | Deadline exceeded |
| `canceled` | Canceled by user or system | User aborted the request |
| `abandoned` | Abandoned without completion | No response from upstream |

### value_type

A descriptive label for what was achieved:

```python
emit_outcome("success", value_type="items_processed", value_amount=1)
emit_outcome("success", value_type="documents_generated", value_amount=5)
emit_outcome("success", value_type="tasks_completed", value_amount=1)
emit_outcome("success", value_type="revenue_generated", value_amount=499.99)
```

### value_amount

The quantified value:

```python
# Count
emit_outcome("success", value_type="records_written", value_amount=100)

# Revenue
emit_outcome("success", value_type="order_value", value_amount=1299.99)

# Score
emit_outcome("success", value_type="quality_score", value_amount=4.5)
```

### confidence

For probabilistic outcomes:

```python
emit_outcome(
    "success",
    value_type="classifications_completed",
    value_amount=1,
    confidence=0.92,
)
```

### reason

Explain the outcome (especially for failures):

```python
emit_outcome("failed", reason="rate_limit_exceeded")
emit_outcome("failed", reason="invalid_input")
emit_outcome("partial", reason="timeout_partial_results", value_amount=3)
```

### error_type

Classify the error for aggregation:

```python
emit_outcome("failed", reason="upstream service unavailable", error_type="ServiceUnavailable")
emit_outcome("timeout", reason="model took too long", error_type="DeadlineExceeded")
```

### metadata

Attach arbitrary key-value pairs:

```python
emit_outcome(
    "success",
    value_type="items_processed",
    value_amount=10,
    metadata={"batch_id": "abc-123", "retry_count": 2},
)
```

## Outcome Patterns

### Success with Value

```python
@botanu_workflow("fulfill-order", event_id=order.id, customer_id=customer.id)
async def process_order():
    result = await do_work()

    emit_outcome(
        "success",
        value_type="orders_fulfilled",
        value_amount=1,
    )
```

### Success with Revenue

```python
@botanu_workflow("handle-inquiry", event_id=inquiry.id, customer_id=customer.id)
async def handle_inquiry():
    result = await process()

    if result.completed:
        emit_outcome(
            "success",
            value_type="revenue_generated",
            value_amount=result.total,
        )
    else:
        emit_outcome(
            "partial",
            value_type="leads_qualified",
            value_amount=1,
        )
```

### Partial Success

```python
@botanu_workflow("batch-process", event_id=batch.id, customer_id=customer.id)
async def process_batch(items: list):
    processed = 0
    for item in items:
        try:
            await do_something(item)
            processed += 1
        except Exception:
            continue

    if processed == len(items):
        emit_outcome("success", value_type="items_processed", value_amount=processed)
    elif processed > 0:
        emit_outcome(
            "partial",
            value_type="items_processed",
            value_amount=processed,
            reason=f"processed_{processed}_of_{len(items)}",
        )
    else:
        emit_outcome("failed", reason="no_items_processed")
```

### Failure with Reason

```python
@botanu_workflow("analyze", event_id=job.id, customer_id=customer.id)
async def analyze(doc_id: str):
    try:
        data = await do_work(doc_id)
        if not data:
            emit_outcome("failed", reason="not_found", error_type="NotFound")
            return None

        result = await process(data)
        emit_outcome("success", value_type="items_analyzed", value_amount=1)
        return result

    except RateLimitError:
        emit_outcome("failed", reason="rate_limit_exceeded", error_type="RateLimitError")
        raise
    except TimeoutError:
        emit_outcome("timeout", reason="analysis_timeout", error_type="TimeoutError")
        raise
```

### Classification with Confidence

```python
@botanu_workflow("classify", event_id=request.id, customer_id=customer.id)
async def classify(message: str):
    result = await do_work(message)

    emit_outcome(
        "success",
        value_type="classifications_completed",
        value_amount=1,
        confidence=result.confidence,
    )

    return result.label
```

## Automatic Outcomes

The `@botanu_workflow` decorator automatically emits outcomes:

```python
@botanu_workflow("my-workflow", event_id=event_id, customer_id=customer_id, auto_outcome_on_success=True)  # Default
async def my_function():
    # If no exception and no explicit emit_outcome, emits "success"
    return result
```

If an exception is raised, it automatically emits `"failed"` with the exception class as the reason.

To disable:

```python
@botanu_workflow("my-workflow", event_id=event_id, customer_id=customer_id, auto_outcome_on_success=False)
async def my_function():
    # Must call emit_outcome explicitly
    emit_outcome("success")
```

## Context Manager Alternative

Use `run_botanu` when you need workflow tracking without a decorator:

```python
from botanu import run_botanu, emit_outcome

async def my_function(event_id: str, customer_id: str):
    async with run_botanu("my-workflow", event_id=event_id, customer_id=customer_id):
        result = await do_work()
        emit_outcome("success", value_type="items_processed", value_amount=result.count)
        return result
```

## Span Attributes

Outcomes are recorded as span attributes:

| Attribute | Description |
|-----------|-------------|
| `botanu.outcome` | Status (success/partial/failed/timeout/canceled/abandoned) |
| `botanu.outcome.value_type` | What was achieved |
| `botanu.outcome.value_amount` | Quantified value |
| `botanu.outcome.confidence` | Confidence score |
| `botanu.outcome.reason` | Reason for outcome |
| `botanu.outcome.error_type` | Error classification |

## Span Events

An event is also emitted for timeline visibility:

```python
# Event: botanu.outcome_emitted
# Attributes:
#   status: "success"
#   value_type: "items_processed"
#   value_amount: 1
```

## Cost-Per-Outcome Analysis

With outcomes recorded, you can calculate:

```sql
-- Cost per successful outcome
SELECT
    AVG(total_cost) as avg_cost_per_success
FROM runs
WHERE workflow = 'fulfill-order'
  AND outcome_status = 'success'
  AND outcome_value_type = 'orders_fulfilled';

-- ROI by workflow
SELECT
    workflow,
    SUM(outcome_value_amount * value_per_unit) as total_value,
    SUM(total_cost) as total_cost,
    (SUM(outcome_value_amount * value_per_unit) - SUM(total_cost)) / SUM(total_cost) as roi
FROM runs
GROUP BY workflow;
```

## Best Practices

### 1. Always Record Outcomes

Every workflow should emit an outcome:

```python
@botanu_workflow("my-workflow", event_id=event_id, customer_id=customer_id)
async def my_function():
    try:
        result = await do_work()
        emit_outcome("success", value_type="items_processed", value_amount=result.count)
        return result
    except Exception as e:
        emit_outcome("failed", reason=type(e).__name__, error_type=type(e).__name__)
        raise
```

### 2. Use Consistent Value Types

Define standard value types for your organization:

```python
# Good - consistent naming
emit_outcome("success", value_type="items_processed", value_amount=1)
emit_outcome("success", value_type="documents_generated", value_amount=1)

# Bad - inconsistent
emit_outcome("success", value_type="item_done", value_amount=1)
emit_outcome("success", value_type="doc processed", value_amount=1)
```

### 3. Quantify When Possible

Include amounts for better analysis:

```python
# Good - quantified
emit_outcome("success", value_type="records_written", value_amount=50)

# Less useful - no amount
emit_outcome("success")
```

### 4. Include Reasons for Failures

Always explain why something failed:

```python
emit_outcome("failed", reason="api_rate_limit", error_type="RateLimitError")
emit_outcome("failed", reason="invalid_input_format", error_type="ValidationError")
emit_outcome("timeout", reason="model_unavailable", error_type="TimeoutError")
```

### 5. One Outcome Per Run

Emit only one outcome per workflow execution:

```python
@botanu_workflow("process-items", event_id=event_id, customer_id=customer_id)
async def process_items(items):
    successful = 0
    for item in items:
        if await process(item):
            successful += 1

    # One outcome at the end
    emit_outcome("success", value_type="items_processed", value_amount=successful)
```

## See Also

- [Run Context](../concepts/run-context.md) - Understanding runs
- [LLM Tracking](llm-tracking.md) - Tracking LLM costs
- [Best Practices](../patterns/best-practices.md) - More patterns
