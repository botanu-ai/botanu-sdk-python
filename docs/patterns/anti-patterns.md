# Anti-Patterns

Patterns that look reasonable at first but break cost-per-outcome attribution or make your dashboards noisy. Each section shows the symptom and the cleaner alternative.

## Splitting one business event into multiple events

One event should cover one business transaction. Internal phases (retrieval, generation, validation) belong inside a single event, marked with `botanu.step(...)`. Otherwise each phase gets counted as a separate event and cost-per-outcome is computed per-phase instead of per-outcome.

```python
# Each phase becomes its own event — event counts and cost-per-outcome
# get split across three unrelated rows in the dashboard.
@botanu.event(workflow="fetch", event_id=..., customer_id=...)
def fetch(req): ...

@botanu.event(workflow="process", event_id=..., customer_id=...)
def process(data): ...

@botanu.event(workflow="send", event_id=..., customer_id=...)
def send(result): ...
```

```python
# One event, three phases. Cost rolls up to one business transaction.
@botanu.event(workflow="Support", event_id=lambda r: r.id, customer_id=lambda r: r.user_id)
def handle(req):
    with botanu.step("fetch"):
        data = fetch(req)
    with botanu.step("process"):
        result = process(data)
    with botanu.step("send"):
        send(result)
```

## Nesting `botanu.event(...)` inside another `botanu.event(...)`

A nested event creates a second `run_id`, so what you meant as one transaction gets counted as two. Wrap at the outermost boundary only; use `botanu.step(...)` for finer granularity.

```python
with botanu.event(event_id="ticket-1", customer_id="acme", workflow="Support"):
    with botanu.event(event_id="ticket-1", customer_id="acme", workflow="Inner"):
        ...
```

```python
with botanu.event(event_id="ticket-1", customer_id="acme", workflow="Support"):
    with botanu.step("classification"):
        ...
```

## Using a random UUID as `event_id`

`event_id` is the join key. When a SoR webhook fires ("Zendesk ticket resolved") or an evaluator verdict lands, those systems need to find the matching event. Using a fresh random UUID each time means nothing ever matches, and your cost-per-outcome will stay at `pending` forever.

Use the identifier your downstream systems already know — the ticket ID, order ID, session ID.

```python
with botanu.event(event_id=uuid.uuid4().hex, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

```python
with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

## High-cardinality workflow names

Workflow names drive filtering in the dashboard. If every request produces a new workflow name, the filter becomes unusable. Keep workflow names stable and descriptive.

```python
workflow = f"request-{request.id}"
workflow = f"Support-{datetime.now().isoformat()}"
```

```python
workflow = "Support"
workflow = "OrderFulfillment"
```

## Manually tracking LLM calls when auto-instrumentation covers them

Inside `botanu.event(...)`, the OpenAI, Anthropic, Vertex, and LangChain auto-instrumentors already produce GenAI-semconv spans for each call. Wrapping those calls in `track_llm_call` creates a duplicate span and duplicate token accounting.

```python
with botanu.event(event_id=..., customer_id=..., workflow="Support"):
    with track_llm_call(provider="openai", model="gpt-4") as tracker:
        resp = openai_client.chat.completions.create(...)
        tracker.set_tokens(...)
```

```python
with botanu.event(event_id=..., customer_id=..., workflow="Support"):
    resp = openai_client.chat.completions.create(...)
```

`track_llm_call` is still useful when you're calling a library OTel doesn't auto-instrument — a custom inference endpoint, a self-hosted model server, or a proprietary SDK.

## Calling `emit_outcome` to report success or failure

`emit_outcome` stamps diagnostic fields — `value_type`, `value_amount`, `reason`, `error_type`. The authoritative outcome (success, failed, partial, etc.) is resolved server-side from SoR connectors, HITL reviews, or eval verdicts. Calling `emit_outcome()` with no fields stamps nothing useful.

```python
with botanu.event(event_id=..., customer_id=..., workflow="Support"):
    agent.run(ticket)
    botanu.emit_outcome()
```

```python
with botanu.event(event_id=..., customer_id=..., workflow="Support"):
    resolved = agent.run(ticket)
    if resolved:
        botanu.emit_outcome(value_type="tickets_resolved", value_amount=1)
```

## Putting secrets or PII in baggage

Baggage travels in plaintext on every outbound HTTP request and through third-party HTTP middleware. User tokens, API keys, and PII should flow through your application's normal auth layer, not through `set_baggage`.

```python
botanu.set_baggage("api_token", user_token)
```

## See also

- [Best Practices](best-practices.md)
- [Context Propagation](../concepts/context-propagation.md)
