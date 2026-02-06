# Existing OpenTelemetry Setup

Integrate Botanu with your existing OpenTelemetry configuration.

## Overview

If you already have OpenTelemetry configured (via Datadog, Splunk, New Relic, or custom setup), Botanu integrates seamlessly. You only need to add the `RunContextEnricher` span processor.

## Minimal Integration

Add just the span processor to your existing provider:

```python
from opentelemetry import trace
from botanu.processors.enricher import RunContextEnricher

# Your existing TracerProvider
provider = trace.get_tracer_provider()

# Add Botanu's enricher
provider.add_span_processor(RunContextEnricher())
```

That's it. All spans will now receive `run_id` from baggage.

## With Existing Instrumentation

Botanu works alongside any existing instrumentation:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from botanu.processors.enricher import RunContextEnricher

# Your existing setup
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

# Your existing instrumentation
RequestsInstrumentor().instrument()

# Add Botanu enricher (order doesn't matter)
provider.add_span_processor(RunContextEnricher())
```

## With Datadog

```python
from ddtrace import tracer
from ddtrace.opentelemetry import TracerProvider
from opentelemetry import trace

from botanu.processors.enricher import RunContextEnricher

# Datadog's TracerProvider
provider = TracerProvider()
trace.set_tracer_provider(provider)

# Add Botanu enricher
provider.add_span_processor(RunContextEnricher())
```

## With Splunk

```python
from splunk_otel.tracing import start_tracing
from opentelemetry import trace

from botanu.processors.enricher import RunContextEnricher

# Start Splunk tracing
start_tracing()

# Add Botanu enricher
provider = trace.get_tracer_provider()
provider.add_span_processor(RunContextEnricher())
```

## With New Relic

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from botanu.processors.enricher import RunContextEnricher

# New Relic OTLP endpoint
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint="https://otlp.nr-data.net/v1/traces",
            headers={"api-key": "YOUR_LICENSE_KEY"},
        )
    )
)
trace.set_tracer_provider(provider)

# Add Botanu enricher
provider.add_span_processor(RunContextEnricher())
```

## With Jaeger

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

from botanu.processors.enricher import RunContextEnricher

# Jaeger setup
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(
        JaegerExporter(
            agent_host_name="localhost",
            agent_port=6831,
        )
    )
)
trace.set_tracer_provider(provider)

# Add Botanu enricher
provider.add_span_processor(RunContextEnricher())
```

## Multiple Exporters

Send to both your APM and a cost-attribution backend:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from botanu.processors.enricher import RunContextEnricher

provider = TracerProvider()

# Your APM (e.g., Datadog)
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint="https://your-apm.example.com/v1/traces")
    )
)

# Botanu collector for cost attribution
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://botanu-collector:4318/v1/traces")
    )
)

# Botanu enricher (adds run_id to all spans)
provider.add_span_processor(RunContextEnricher())

trace.set_tracer_provider(provider)
```

## How RunContextEnricher Works

The enricher reads baggage and writes to span attributes:

```python
class RunContextEnricher(SpanProcessor):
    def on_start(self, span, parent_context):
        # Read run_id from baggage
        run_id = baggage.get_baggage("botanu.run_id", parent_context)
        if run_id:
            span.set_attribute("botanu.run_id", run_id)

        # Read use_case from baggage
        use_case = baggage.get_baggage("botanu.use_case", parent_context)
        if use_case:
            span.set_attribute("botanu.use_case", use_case)
```

This means:
- Every span gets `run_id` if it exists in baggage
- Auto-instrumented spans are enriched automatically
- No code changes needed in your existing instrumentation

## Using Botanu Decorators

With the enricher in place, use Botanu decorators:

```python
from botanu import botanu_use_case, emit_outcome

@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id: str):
    # All spans created here (by any instrumentation) get run_id
    context = requests.get(f"/api/tickets/{ticket_id}")
    response = await openai_call(context)
    await database.save(response)

    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
```

## Without Botanu Bootstrap

If you don't want to use `enable()`, manually set up propagation:

```python
from opentelemetry import propagate
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator

# Ensure baggage propagation is enabled
propagate.set_global_textmap(
    CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ])
)
```

## Verifying Integration

Check that run_id appears on spans:

```python
from opentelemetry import trace, baggage, context

# Set baggage (normally done by @botanu_use_case)
ctx = baggage.set_baggage("botanu.run_id", "test-123")
token = context.attach(ctx)

try:
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        # Check attribute was set
        print(span.attributes.get("botanu.run_id"))  # Should print "test-123"
finally:
    context.detach(token)
```

## Processor Order

Span processors are called in order. The enricher should be added after your span exporters:

```python
# 1. Exporters (send spans to backends)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

# 2. Enrichers (modify spans before export)
provider.add_span_processor(RunContextEnricher())
```

However, `RunContextEnricher` uses `on_start()`, so it runs before export regardless.

## Troubleshooting

### run_id Not Appearing

1. Check enricher is added:
   ```python
   provider = trace.get_tracer_provider()
   # Verify RunContextEnricher is in the list
   ```

2. Check baggage is set:
   ```python
   from opentelemetry import baggage
   print(baggage.get_baggage("botanu.run_id"))
   ```

3. Ensure `@botanu_use_case` is used at entry points

### Baggage Not Propagating

Check propagators are configured:
```python
from opentelemetry import propagate
print(propagate.get_global_textmap())
```

Should include `W3CBaggagePropagator`.

## See Also

- [Auto-Instrumentation](auto-instrumentation.md) - Library instrumentation
- [Collector Configuration](collector.md) - Collector setup
- [Architecture](../concepts/architecture.md) - SDK design
