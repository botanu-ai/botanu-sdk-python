# Best Practices

Patterns that produce clean cost-per-outcome attribution and dashboards that stay readable over time.

## One event per business outcome

An event is one business transaction — a support ticket resolved, an order fulfilled, a document summarized. Use `botanu.step(...)` for internal phases so everything rolls up to a single outcome.

```python
import botanu

with botanu.event(event_id=order.id, customer_id=order.customer_id, workflow="OrderFulfillment"):
    with botanu.step("validate"):
        validate(order)
    with botanu.step("charge"):
        charge_card(order)
    with botanu.step("ship"):
        create_shipment(order)
```

## Use real business IDs for `event_id`

`event_id` is the join key. When a SoR webhook fires (Zendesk ticket reopened, Stripe refund issued) or an evaluator verdict lands, the server matches it against `event_id` to resolve the outcome. Pass the identifier your downstream systems already use — ticket ID, order ID, session ID.

```python
with botanu.event(event_id=ticket.id, customer_id=ticket.user_id, workflow="Support"):
    agent.run(ticket)
```

If your internal ID differs from the SoR ID, add the correlation explicitly:

```python
with botanu.event(event_id=session.id, customer_id=user.id, workflow="Support"):
    botanu.set_correlation(zendesk_ticket_id=session.zendesk_ticket_id)
    agent.run(session)
```

## Pick stable, low-cardinality workflow names

Workflow names drive filtering and grouping in the dashboard. Keep them stable across deployments and descriptive of the business purpose.

```python
@botanu.event(workflow="Support", event_id=lambda t: t.id, customer_id=lambda t: t.user_id)
def handle_ticket(ticket): ...

@botanu.event(workflow="DocumentAnalysis", event_id=lambda d: d.id, customer_id=lambda d: d.tenant)
def analyze_doc(doc): ...
```

## Let OTel auto-instrumentation do the heavy lifting

Inside `botanu.event(...)`, the OTel auto-instrumentors already cover OpenAI, Anthropic, Vertex, LangChain, httpx, requests, SQLAlchemy, psycopg2, asyncpg, Redis, Celery, Kafka, and boto3. Each call automatically produces a span with the right semconv attributes and inherits the event's run context.

You only need `track_llm_call` or `track_db_operation` when:

- The library you're calling isn't auto-instrumented (custom inference server, niche vector DB, proprietary queue).
- You need to stamp semantic metrics the instrumentor doesn't capture, like `set_bytes_scanned` on a warehouse query.

## Annotate business value

Use `emit_outcome` to stamp diagnostic fields that the dashboard can render alongside cost-per-outcome. The authoritative outcome is resolved server-side; these fields add colour.

```python
with botanu.event(event_id=ticket.id, customer_id=ticket.user_id, workflow="Support"):
    resolved = agent.run(ticket)
    if resolved:
        botanu.emit_outcome(value_type="tickets_resolved", value_amount=1)
```

Quantified examples:

```python
botanu.emit_outcome(value_type="revenue_generated", value_amount=1299.99)
botanu.emit_outcome(value_type="documents_processed", value_amount=10)
botanu.emit_outcome(reason="rate_limit_exceeded", error_type="RateLimitError")
```

## Multi-tenant apps: always pass `tenant_id`

```python
with botanu.event(
    event_id=request.id,
    customer_id=request.user_id,
    workflow="Support",
    tenant_id=request.org_id,
):
    ...
```

`tenant_id` propagates via baggage and appears as a filter dimension in the dashboard.

## Configuration belongs in the environment

Keep secrets and endpoints out of code:

```bash
export BOTANU_API_KEY=<from app.botanu.ai>
export OTEL_SERVICE_NAME=support-service
export BOTANU_ENVIRONMENT=production
```

For multi-environment setups, a YAML file works too — see [Configuration](../getting-started/configuration.md).

## See also

- [Anti-Patterns](anti-patterns.md)
- [Outcomes](../tracking/outcomes.md)
- [Context Propagation](../concepts/context-propagation.md)
