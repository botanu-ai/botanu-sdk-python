# Architecture

Thin SDK, smart collector. The SDK does minimal work in the hot path; everything heavy runs in the OpenTelemetry [Collector](https://opentelemetry.io/docs/collector/).

## What the SDK does

- Generates a UUIDv7 `run_id` per event
- Sets seven [W3C Baggage](https://www.w3.org/TR/baggage/) keys on the active [OTel context](https://opentelemetry.io/docs/specs/otel/context/)
- Records token counts as span attributes
- Exports spans via [OTLP/HTTP](https://opentelemetry.io/docs/specs/otlp/)

Target overhead: under 0.5 ms per request.

## What the collector does

- Cost calculation from token counts
- Vendor normalization
- Cardinality management
- Aggregation and sampling
- Belt-and-suspenders PII regex (SDK already scrubs captured content in-process — see [`botanu/sdk/pii.py`](../../src/botanu/sdk/pii.py))

## SDK components

- `BotanuConfig` — configuration dataclass. See [Configuration](../getting-started/configuration.md).
- `RunContext` — run metadata + serialization. See [Run Context](run-context.md).
- `RunContextEnricher` — [OTel SpanProcessor](https://opentelemetry.io/docs/specs/otel/trace/sdk/#span-processor) that reads baggage and stamps span attributes.
- Tracking helpers: `track_llm_call`, `track_db_operation`, `track_storage_operation`, `track_messaging_operation`.

## Integration

```python
from opentelemetry import trace
from botanu.processors.enricher import RunContextEnricher

provider = trace.get_tracer_provider()
provider.add_span_processor(RunContextEnricher())
```

If you already have an OTel setup, the SDK detects it and adds itself alongside. See [Coexisting with existing OTel / Datadog](../integration/existing-otel.md).

## See also

- [Run Context](run-context.md)
- [Context Propagation](context-propagation.md)
- [Collector](../integration/collector.md)
