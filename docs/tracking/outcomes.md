# Outcomes

Record business outcomes to enable cost-per-outcome analysis.

## Overview

Outcomes connect infrastructure costs to business value. By recording what was achieved (tickets resolved, documents processed, leads qualified), you can calculate the true ROI of your AI workflows.

## Basic Usage

```python
from botanu import botanu_use_case, emit_outcome

@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id: str):
    # ... process ticket ...

    # Record the business outcome
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
```

## emit_outcome() Parameters

```python
emit_outcome(
    status: str,                    # Required: "success", "partial", "failed"
    value_type: str = None,         # What was achieved
    value_amount: float = None,     # How much
    confidence: float = None,       # Confidence score (0.0-1.0)
    reason: str = None,             # Why (especially for failures)
)
```

### status

The outcome status:

| Status | Description | Use Case |
|--------|-------------|----------|
| `success` | Fully achieved goal | Ticket resolved, document processed |
| `partial` | Partially achieved | 3 of 5 items processed |
| `failed` | Did not achieve goal | Error, timeout, rejection |

### value_type

A descriptive label for what was achieved:

```python
emit_outcome("success", value_type="tickets_resolved", value_amount=1)
emit_outcome("success", value_type="documents_processed", value_amount=5)
emit_outcome("success", value_type="leads_qualified", value_amount=1)
emit_outcome("success", value_type="revenue_generated", value_amount=499.99)
```

### value_amount

The quantified value:

```python
# Count
emit_outcome("success", value_type="emails_sent", value_amount=100)

# Revenue
emit_outcome("success", value_type="order_value", value_amount=1299.99)

# Score
emit_outcome("success", value_type="satisfaction_score", value_amount=4.5)
```

### confidence

For probabilistic outcomes:

```python
emit_outcome(
    "success",
    value_type="intent_classified",
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

## Outcome Patterns

### Success with Value

```python
@botanu_use_case("Order Processing")
async def process_order(order_id: str):
    order = await fetch_order(order_id)
    await fulfill_order(order)

    emit_outcome(
        "success",
        value_type="orders_fulfilled",
        value_amount=1,
    )
```

### Success with Revenue

```python
@botanu_use_case("Sales Bot")
async def handle_inquiry(inquiry_id: str):
    result = await process_sale(inquiry_id)

    if result.sale_completed:
        emit_outcome(
            "success",
            value_type="revenue_generated",
            value_amount=result.order_total,
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
@botanu_use_case("Batch Processing")
async def process_batch(items: list):
    processed = 0
    for item in items:
        try:
            await process_item(item)
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
@botanu_use_case("Document Analysis")
async def analyze_document(doc_id: str):
    try:
        document = await fetch_document(doc_id)
        if not document:
            emit_outcome("failed", reason="document_not_found")
            return None

        result = await analyze(document)
        emit_outcome("success", value_type="documents_analyzed", value_amount=1)
        return result

    except RateLimitError:
        emit_outcome("failed", reason="rate_limit_exceeded")
        raise
    except TimeoutError:
        emit_outcome("failed", reason="analysis_timeout")
        raise
```

### Classification with Confidence

```python
@botanu_use_case("Intent Classification")
async def classify_intent(message: str):
    result = await classifier.predict(message)

    emit_outcome(
        "success",
        value_type="intents_classified",
        value_amount=1,
        confidence=result.confidence,
    )

    return result.intent
```

## Automatic Outcomes

The `@botanu_use_case` decorator automatically emits outcomes:

```python
@botanu_use_case("My Use Case", auto_outcome_on_success=True)  # Default
async def my_function():
    # If no exception and no explicit emit_outcome, emits "success"
    return result
```

If an exception is raised, it automatically emits `"failed"` with the exception class as the reason.

To disable:

```python
@botanu_use_case("My Use Case", auto_outcome_on_success=False)
async def my_function():
    # Must call emit_outcome explicitly
    emit_outcome("success")
```

## @botanu_outcome Decorator

For sub-functions within a use case:

```python
from botanu import botanu_use_case, botanu_outcome

@botanu_use_case("Data Pipeline")
async def run_pipeline():
    await step_one()
    await step_two()

@botanu_outcome()
async def step_one():
    # Emits "success" on completion, "failed" on exception
    await process_data()

@botanu_outcome(success="data_extracted", failed="extraction_failed")
async def step_two():
    # Custom outcome labels
    await extract_data()
```

## Span Attributes

Outcomes are recorded as span attributes:

| Attribute | Description |
|-----------|-------------|
| `botanu.outcome` | Status (success/partial/failed) |
| `botanu.outcome.value_type` | What was achieved |
| `botanu.outcome.value_amount` | Quantified value |
| `botanu.outcome.confidence` | Confidence score |
| `botanu.outcome.reason` | Reason for outcome |

## Span Events

An event is also emitted for timeline visibility:

```python
# Event: botanu.outcome_emitted
# Attributes:
#   status: "success"
#   value_type: "tickets_resolved"
#   value_amount: 1
```

## Cost-Per-Outcome Analysis

With outcomes recorded, you can calculate:

```sql
-- Cost per successful ticket resolution
SELECT
    AVG(total_cost) as avg_cost_per_resolution
FROM runs
WHERE use_case = 'Customer Support'
  AND outcome_status = 'success'
  AND outcome_value_type = 'tickets_resolved';

-- ROI by use case
SELECT
    use_case,
    SUM(outcome_value_amount * value_per_unit) as total_value,
    SUM(total_cost) as total_cost,
    (SUM(outcome_value_amount * value_per_unit) - SUM(total_cost)) / SUM(total_cost) as roi
FROM runs
GROUP BY use_case;
```

## Best Practices

### 1. Always Record Outcomes

Every use case should emit an outcome:

```python
@botanu_use_case("My Use Case")
async def my_function():
    try:
        result = await do_work()
        emit_outcome("success", value_type="items_processed", value_amount=result.count)
        return result
    except Exception as e:
        emit_outcome("failed", reason=type(e).__name__)
        raise
```

### 2. Use Consistent Value Types

Define standard value types for your organization:

```python
# Good - consistent naming
emit_outcome("success", value_type="tickets_resolved", value_amount=1)
emit_outcome("success", value_type="documents_processed", value_amount=1)

# Bad - inconsistent
emit_outcome("success", value_type="ticket_done", value_amount=1)
emit_outcome("success", value_type="doc processed", value_amount=1)
```

### 3. Quantify When Possible

Include amounts for better analysis:

```python
# Good - quantified
emit_outcome("success", value_type="emails_sent", value_amount=50)

# Less useful - no amount
emit_outcome("success")
```

### 4. Include Reasons for Failures

Always explain why something failed:

```python
emit_outcome("failed", reason="api_rate_limit")
emit_outcome("failed", reason="invalid_input_format")
emit_outcome("failed", reason="model_unavailable")
```

### 5. One Outcome Per Run

Emit only one outcome per use case execution:

```python
@botanu_use_case("Process Items")
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
