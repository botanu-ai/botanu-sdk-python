# Botanu SDK Documentation

Botanu SDK provides OpenTelemetry-native event-level cost attribution for AI
workflows.

## Overview

Traditional observability tools trace individual requests. But AI workflows are
different — a single business event (resolving a support ticket, processing an
order) might involve multiple runs spanning LLM calls, retries, tool executions,
and data operations across different services and vendors.

Botanu introduces **event-level attribution**: a stable `event_id` that follows
your entire business transaction, enabling you to answer "How much did this
event cost?" and "What was the outcome?"

## Documentation

### Getting Started

- [Installation](getting-started/installation.md) — Install and configure the SDK
- [Quick Start](getting-started/quickstart.md) — Get up and running in 5 minutes
- [Configuration](getting-started/configuration.md) — Environment variables and options

### Core Concepts

- [Run Context](concepts/run-context.md) — Events, runs, and context propagation
- [Context Propagation](concepts/context-propagation.md) — How context flows across services
- [Architecture](concepts/architecture.md) — SDK design and component overview

### Tracking

- [LLM Tracking](tracking/llm-tracking.md) — Track AI model calls and token usage
- [Data Tracking](tracking/data-tracking.md) — Track database, storage, and messaging operations
- [Outcomes](tracking/outcomes.md) — Record business outcomes for ROI calculation

### Integration

- [Auto-Instrumentation](integration/auto-instrumentation.md) — Supported libraries and frameworks
- [Kubernetes Deployment](integration/kubernetes.md) — Zero-code instrumentation at scale
- [Existing OTel Setup](integration/existing-otel.md) — Integrate with existing OpenTelemetry deployments
- [Collector Configuration](integration/collector.md) — Configure the OpenTelemetry Collector

### Patterns

- [Best Practices](patterns/best-practices.md) — Recommended patterns for production use
- [Anti-Patterns](patterns/anti-patterns.md) — Common mistakes to avoid

### API Reference

- [Decorators](api/decorators.md) — `@botanu_workflow` and related decorators
- [Tracking API](api/tracking.md) — Manual tracking context managers
- [Configuration API](api/configuration.md) — `BotanuConfig` and initialization

## Quick Example

```python
from botanu import enable, botanu_workflow, emit_outcome

enable()

@botanu_workflow("my-workflow", event_id="evt-001", customer_id="cust-42")
async def do_work():
    result = await do_something()
    emit_outcome("success")
    return result
```

## License

[Apache License 2.0](https://github.com/botanu-ai/botanu-sdk-python/blob/main/LICENSE)
