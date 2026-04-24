# Botanu SDK for Python

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

Event-level cost attribution for AI workflows, built on [OpenTelemetry](https://opentelemetry.io/).

An **event** is one business transaction — resolving a support ticket, processing an order, generating a report. Each event may involve multiple **runs** (LLM calls, retries, sub-workflows) across multiple services. By correlating every run to a stable `event_id`, Botanu gives you per-event cost attribution and outcome tracking without sampling artefacts.

## Install

```bash
pip install botanu
```

One install. Includes the OTel SDK, the OTLP exporter, and auto-instrumentation for 50+ libraries (OpenAI, Anthropic, Vertex, LangChain, httpx, requests, SQLAlchemy, psycopg2, Redis, Celery, Kafka, boto3, and more).

## Quickstart

Set your API key:

```bash
export BOTANU_API_KEY=<your-api-key>
```

Wrap your agent:

```python
import botanu

with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

That single wrap captures every LLM call, HTTP call, and DB call inside and stamps them with `event_id`, `customer_id`, and `workflow`.

### Decorator form

```python
import botanu

@botanu.event(
    workflow="Support",
    event_id=lambda ticket: ticket.id,
    customer_id=lambda ticket: ticket.user_id,
)
def handle_ticket(ticket):
    return agent.run(ticket)
```

Works for both sync and `async def` functions.

### Multi-phase workflows

```python
with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    with botanu.step("retrieval"):
        docs = vector_db.query(ticket.query)
    with botanu.step("generation"):
        response = llm.complete(docs)
```

See the [Quickstart](./docs/getting-started/quickstart.md) for the full five-minute walkthrough.

## Documentation

| Topic | |
| --- | --- |
| [Installation](./docs/getting-started/installation.md) | Install and configure |
| [Quickstart](./docs/getting-started/quickstart.md) | Zero-to-first-trace in five minutes |
| [Configuration](./docs/getting-started/configuration.md) | Env vars, YAML, trusted-host auth |
| [Run Context](./docs/concepts/run-context.md) | Events, runs, retries, baggage |
| [Context Propagation](./docs/concepts/context-propagation.md) | Cross-service and queue propagation |
| [Architecture](./docs/concepts/architecture.md) | SDK + collector split |
| [LLM Tracking](./docs/tracking/llm-tracking.md) | Manual LLM instrumentation (usually not needed) |
| [Data Tracking](./docs/tracking/data-tracking.md) | DB, storage, messaging (usually not needed) |
| [Content Capture](./docs/tracking/content-capture.md) | Prompt/response capture for eval, with PII scrubbing |
| [Outcomes](./docs/tracking/outcomes.md) | Diagnostic annotations and server-side resolution |
| [Auto-Instrumentation](./docs/integration/auto-instrumentation.md) | Supported libraries |
| [Kubernetes](./docs/integration/kubernetes.md) | Zero-code instrumentation at scale |
| [Existing OTel / Datadog](./docs/integration/existing-otel.md) | Brownfield coexistence |
| [`event` / `step` API](./docs/api/event.md) | Primary API reference |
| [Best Practices](./docs/patterns/best-practices.md) | Patterns that work |
| [Anti-Patterns](./docs/patterns/anti-patterns.md) | Patterns that break cost attribution |

## Requirements

- Python 3.9 or newer
- An OpenTelemetry Collector (Botanu Cloud runs one for you; self-hosted is supported too)

## Contributing

Contributions are welcome. Read the [Contributing Guide](./CONTRIBUTING.md) before opening a pull request.

All commits require [DCO sign-off](https://developercertificate.org/):

```bash
git commit -s -m "Your commit message"
```

Looking for a place to start? See the [good first issues](https://github.com/botanu-ai/botanu-sdk-python/labels/good%20first%20issue).

## Community

- [GitHub Discussions](https://github.com/botanu-ai/botanu-sdk-python/discussions) — questions, ideas, show & tell
- [GitHub Issues](https://github.com/botanu-ai/botanu-sdk-python/issues) — bugs and feature requests

## Governance

See [GOVERNANCE.md](./GOVERNANCE.md) for roles, decision-making, and the contributor ladder. Current maintainers are in [MAINTAINERS.md](./MAINTAINERS.md).

## Security

Report security vulnerabilities via [GitHub Security Advisories](https://github.com/botanu-ai/botanu-sdk-python/security/advisories/new) or see [SECURITY.md](./SECURITY.md). **Do not file a public issue.**

## Code of Conduct

This project follows the [LF Projects Code of Conduct](https://lfprojects.org/policies/code-of-conduct/). See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## License

[Apache License 2.0](./LICENSE)
