# Botanu SDK Documentation

Botanu SDK is an OpenTelemetry-native library for run-level cost attribution in AI workflows.

## Quick Start

### Installation

```bash
pip install botanu
```

For full SDK capabilities with OTLP export:

```bash
pip install botanu[sdk]
```

### Basic Usage

```python
from botanu import botanu_use_case
from botanu.tracking.llm import track_llm_call

@botanu_use_case("Customer Support")
def handle_ticket(ticket_id: str):
    with track_llm_call(provider="openai", model="gpt-4") as tracker:
        response = openai.chat.completions.create(...)
        tracker.set_tokens(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
    return response

# Every span within handle_ticket is tagged with botanu.run_id
result = handle_ticket("TICKET-123")
```

## Features

- **Run-level Attribution**: Track costs per business transaction, not just per request
- **OpenTelemetry Native**: Built on OTel standards for maximum interoperability
- **Minimal Overhead**: Lightweight SDK with heavy processing in the collector
- **Multi-provider Support**: Works with OpenAI, Anthropic, Bedrock, Vertex AI, and more

## Documentation

- [Configuration](configuration.md)
- [LLM Tracking](llm-tracking.md)
- [Data Tracking](data-tracking.md)
- [API Reference](api-reference.md)

## License

Apache License 2.0
