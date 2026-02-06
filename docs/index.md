# Botanu SDK Documentation

Botanu SDK provides OpenTelemetry-native run-level cost attribution for AI workflows.

## Overview

Traditional observability tools trace individual requests. But AI workflows are different — a single business outcome (resolving a support ticket, processing an order) might span multiple LLM calls, retries, tool executions, and data operations across different vendors.

Botanu introduces **run-level attribution**: a unique `run_id` that follows your entire workflow, enabling you to answer "How much did this outcome cost?"

## Documentation

### Getting Started

- [Installation](getting-started/installation.md) - Install and configure the SDK
- [Quick Start](getting-started/quickstart.md) - Get up and running in 5 minutes
- [Configuration](getting-started/configuration.md) - Configuration options and environment variables

### Core Concepts

- [Run Context](concepts/run-context.md) - Understanding `run_id` and context propagation
- [Context Propagation](concepts/context-propagation.md) - How context flows through your application
- [Architecture](concepts/architecture.md) - SDK design and component overview

### Tracking

- [LLM Tracking](tracking/llm-tracking.md) - Track AI model calls and token usage
- [Data Tracking](tracking/data-tracking.md) - Track database, storage, and messaging operations
- [Outcomes](tracking/outcomes.md) - Record business outcomes for ROI calculation

### Integration

- [Auto-Instrumentation](integration/auto-instrumentation.md) - Automatic instrumentation for common libraries
- [Existing OTel Setup](integration/existing-otel.md) - Integrate with existing OpenTelemetry deployments
- [Collector Configuration](integration/collector.md) - Configure the OpenTelemetry Collector

### Patterns

- [Best Practices](patterns/best-practices.md) - Recommended patterns for production use
- [Anti-Patterns](patterns/anti-patterns.md) - Common mistakes to avoid

### API Reference

- [Decorators](api/decorators.md) - `@botanu_use_case` and related decorators
- [Tracking API](api/tracking.md) - Manual tracking context managers
- [Configuration API](api/configuration.md) - `BotanuConfig` and initialization

## Quick Example

```python
from botanu import init_botanu, botanu_use_case
from botanu.tracking.llm import track_llm_call

# Initialize once at startup
init_botanu(service_name="support-agent")

@botanu_use_case("Customer Support")
def handle_ticket(ticket_id: str):
    # Every operation inside gets the same run_id
    with track_llm_call(provider="openai", model="gpt-4") as tracker:
        response = openai.chat.completions.create(...)
        tracker.set_tokens(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
    return response
```

## License

Apache License 2.0. See [LICENSE](https://github.com/botanu-ai/botanu-sdk-python/blob/main/LICENSE).
