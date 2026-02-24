# Botanu SDK for Python

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)


Event-level cost attribution for AI workflows, built on [OpenTelemetry](https://opentelemetry.io/).

An **event** is one business transaction — resolving a support ticket, processing
an order, generating a report. Each event may involve multiple **runs** (LLM calls,
retries, sub-workflows) across multiple services. By correlating every run to a
stable `event_id`, Botanu gives you per-event cost attribution and outcome
tracking without sampling artifacts.

## Getting Started

```bash
pip install botanu
```

One install. Includes OTel SDK, OTLP exporter, and auto-instrumentation for
50+ libraries.

```python
from botanu import enable, botanu_workflow, emit_outcome

enable()  # reads config from environment variables

@botanu_workflow("my-workflow", event_id="evt-001", customer_id="cust-42")
async def do_work():
    result = await do_something()
    emit_outcome("success")
    return result
```

Entry points use `@botanu_workflow`. Every other service only needs `enable()`.
All configuration is via environment variables — zero hardcoded values in code.

See the [Quick Start](./docs/getting-started/quickstart.md) guide for a full walkthrough.

## Documentation

| Topic | Description |
|-------|-------------|
| [Installation](./docs/getting-started/installation.md) | Install and configure the SDK |
| [Quick Start](./docs/getting-started/quickstart.md) | Get up and running in 5 minutes |
| [Configuration](./docs/getting-started/configuration.md) | Environment variables and options |
| [Core Concepts](./docs/concepts/) | Events, runs, context propagation, architecture |
| [LLM Tracking](./docs/tracking/llm-tracking.md) | Track model calls and token usage |
| [Data Tracking](./docs/tracking/data-tracking.md) | Database, storage, and messaging |
| [Outcomes](./docs/tracking/outcomes.md) | Record business outcomes for ROI |
| [Auto-Instrumentation](./docs/integration/auto-instrumentation.md) | Supported libraries and frameworks |
| [Kubernetes](./docs/integration/kubernetes.md) | Zero-code instrumentation at scale |
| [API Reference](./docs/api/) | Decorators, tracking API, configuration |
| [Best Practices](./docs/patterns/best-practices.md) | Recommended patterns |

## Requirements

- Python 3.9+
- OpenTelemetry Collector (recommended for production)

## Contributing

We welcome contributions from the community. Please read our
[Contributing Guide](./CONTRIBUTING.md) before submitting a pull request.

This project requires [DCO sign-off](https://developercertificate.org/) on all
commits:

```bash
git commit -s -m "Your commit message"
```

Looking for a place to start? Check the
[good first issues](https://github.com/botanu-ai/botanu-sdk-python/labels/good%20first%20issue).

## Community

- [GitHub Discussions](https://github.com/botanu-ai/botanu-sdk-python/discussions) — questions, ideas, show & tell
- [GitHub Issues](https://github.com/botanu-ai/botanu-sdk-python/issues) — bug reports and feature requests

## Governance

See [GOVERNANCE.md](./GOVERNANCE.md) for details on roles, decision-making,
and the contributor ladder.

Current maintainers are listed in [MAINTAINERS.md](./MAINTAINERS.md).

## Security

To report a security vulnerability, please use
[GitHub Security Advisories](https://github.com/botanu-ai/botanu-sdk-python/security/advisories/new)
or see [SECURITY.md](./SECURITY.md) for full details. **Do not file a public issue.**

## Code of Conduct

This project follows the
[LF Projects Code of Conduct](https://lfprojects.org/policies/code-of-conduct/).
See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## License

[Apache License 2.0](./LICENSE)

