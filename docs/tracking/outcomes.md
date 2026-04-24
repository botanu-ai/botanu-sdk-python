# Outcomes

Event outcome is resolved **server-side** from, in priority order:

1. A System-of-Record (SoR) connector (Zendesk, Stripe, custom webhook)
2. A human-in-the-loop reviewer verdict
3. The evaluator's LLM-as-judge verdict rollup for the event's runs
4. `pending` if none of the above has fired yet

The SDK does not set the authoritative outcome. It stamps diagnostic fields that appear alongside cost-per-outcome in the dashboard.

## `emit_outcome()`

```python
import botanu

botanu.emit_outcome(
    value_type="tickets_resolved",
    value_amount=1,
    confidence=0.92,
)
```

All parameters are optional and diagnostic-only:

| Parameter | Description |
| --- | --- |
| `value_type` | Free-form business-value label (e.g. `"tickets_resolved"`, `"revenue_generated"`) |
| `value_amount` | Quantified value amount |
| `confidence` | Confidence score, `0.0`–`1.0` |
| `reason` | Free-form diagnostic string |
| `error_type` | Error classification (e.g. `"TimeoutError"`) |
| `metadata` | Arbitrary key-value dict |

### Span attributes stamped

| Attribute | Source |
| --- | --- |
| `botanu.outcome.value_type` | `value_type` |
| `botanu.outcome.value_amount` | `value_amount` |
| `botanu.outcome.confidence` | `confidence` |
| `botanu.outcome.reason` | `reason` |
| `botanu.outcome.error_type` | `error_type` |
| `botanu.outcome.metadata.<k>` | each `metadata` key |

There is no `botanu.outcome.status` attribute. Authoritative outcome lives in `events.final_outcome` server-side.

## Examples

```python
botanu.emit_outcome(value_type="tickets_resolved", value_amount=1)
botanu.emit_outcome(value_type="revenue_generated", value_amount=1299.99)
botanu.emit_outcome(reason="upstream_unavailable", error_type="ServiceUnavailable")
botanu.emit_outcome(
    value_type="items_processed",
    value_amount=10,
    metadata={"batch_id": "abc-123"},
)
```

## Usage inside an event

```python
import botanu

with botanu.event(event_id=order.id, customer_id=order.customer_id, workflow="Fulfillment"):
    result = process_order(order)
    botanu.emit_outcome(value_type="orders_fulfilled", value_amount=1)
```

If you don't need diagnostic fields, skip `emit_outcome` entirely. The platform resolves the outcome from the signals above.

## Cost-per-outcome

Cost-per-outcome is computed server-side from:

- `runs.cost_total_usd` — populated by the cost engine
- `events.final_outcome` — populated by the outcome resolver

Annotate with `value_type` and `value_amount` so a business-value column appears alongside cost-per-outcome in the dashboard.

## See also

- [Run Context](../concepts/run-context.md)
- [LLM Tracking](llm-tracking.md)
- [Content Capture](content-capture.md)
