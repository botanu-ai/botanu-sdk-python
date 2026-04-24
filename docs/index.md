# Botanu Python SDK

OpenTelemetry-native event-level cost attribution for AI workflows.

## What it does

Traditional observability tools trace individual requests. AI workflows are different — one business event (resolving a support ticket, processing an order) usually spans multiple LLM calls, retries, tool executions, and data operations across services and vendors.

The SDK stamps a stable `event_id` on every span produced inside one business event, so cost and outcome can be joined server-side. One wrap around the agent captures everything that happens inside.

## Quickstart

```python
import botanu

with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

That single wrap captures every LLM call, HTTP call, and DB call the agent makes, and ties them to `event_id`. Authentication and endpoint setup come from `BOTANU_API_KEY` in the environment.

See [Quick Start](getting-started/quickstart.md) for the full five-minute walkthrough.

## Documentation

### Getting Started

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Configuration](getting-started/configuration.md)

### Concepts

- [Run Context](concepts/run-context.md) — events, runs, and how context propagates
- [Context Propagation](concepts/context-propagation.md) — how `event_id` flows across services
- [Architecture](concepts/architecture.md)

### Tracking

- [LLM Tracking](tracking/llm-tracking.md)
- [Data Tracking](tracking/data-tracking.md)
- [Content Capture](tracking/content-capture.md) — prompts and responses for eval (opt-in)
- [Outcomes](tracking/outcomes.md) — diagnostic annotations; authoritative outcome resolution

### Integration

- [Auto-Instrumentation](integration/auto-instrumentation.md) — supported libraries
- [Kubernetes Deployment](integration/kubernetes.md)
- [Coexisting with existing OTel / Datadog](integration/existing-otel.md)
- [Collector](integration/collector.md) — endpoints and auth

### Patterns

- [Best Practices](patterns/best-practices.md)
- [Anti-Patterns](patterns/anti-patterns.md)

### API Reference

- [event & step](api/event.md) — the primary API
- [Tracking](api/tracking.md) — manual tracking context managers
- [Configuration](api/configuration.md) — `BotanuConfig` and initialization

## License

[Apache License 2.0](https://github.com/botanu-ai/botanu-sdk-python/blob/main/LICENSE)
