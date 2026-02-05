# Botanu SDK for Python

[![CI](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/botanu.svg)](https://pypi.org/project/botanu/)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/botanu-ai/botanu-sdk-python/badge)](https://scorecard.dev/viewer/?uri=github.com/botanu-ai/botanu-sdk-python)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

OpenTelemetry-native **run-level cost attribution** for AI workflows.

## Overview

Botanu adds **runs** on top of distributed tracing. A run represents a single business execution that may span multiple traces, retries, and services. By correlating all spans to a stable `run_id`, you get accurate cost attribution without sampling artifacts.

## Quick Start

```python
from botanu import enable, botanu_use_case, emit_outcome

enable(service_name="my-app")

@botanu_use_case(name="Customer Support")
async def handle_ticket(ticket_id: str):
    result = await process_ticket(ticket_id)
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return result
```

## Installation

```bash
pip install botanu           # Core (opentelemetry-api only)
pip install botanu[sdk]      # + OTel SDK + OTLP exporter
pip install botanu[all]      # Everything including GenAI instrumentation
```

## Documentation

Full documentation is available at [docs.botanu.ai](https://docs.botanu.ai) and in the [`docs/`](./docs/) folder.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). This project uses [DCO](./DCO) sign-off.

## License

[Apache-2.0](./LICENSE) — see [NOTICE](./NOTICE) for attribution.
