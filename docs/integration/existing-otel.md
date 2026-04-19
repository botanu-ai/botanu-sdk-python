# Existing OpenTelemetry Setup

Integrate botanu with your existing OpenTelemetry configuration — Datadog, Jaeger, Grafana Tempo, Splunk, New Relic, or any OTel-compatible backend.

## Automatic Detection (Recommended)

As of SDK v0.1.0, `enable()` **automatically detects your existing TracerProvider** and adds botanu alongside it. No manual processor setup needed:

```python
from botanu import enable
enable()  # Detects existing OTel, adds botanu alongside
```

**What happens under the hood:**

| Your setup | What `enable()` does |
|-----------|---------------------|
| OTel SDK with AlwaysOn sampling | Migrates your processors to a new provider, adds botanu exporter alongside |
| OTel SDK with ratio sampling (e.g., 10%) | Same, but wraps your processors in `SampledSpanProcessor` to preserve your ratio. Your Datadog/Jaeger bill is unchanged. |
| ddtrace (Datadog Python SDK) | Creates a parallel TracerProvider. ddtrace continues unchanged. |
| No existing tracing | Creates a fresh provider (standard greenfield path) |

**Zero disruption guarantee:** Your existing dashboards, bills, and sampling are preserved exactly as they were.

## How Sampling Is Preserved

If your existing provider uses ratio-based sampling (e.g., 10%), botanu needs to change the sampler to AlwaysOn (to capture 100% for cost attribution). But your existing exporter should still see only 10%.

botanu solves this with `SampledSpanProcessor`, which wraps your existing processors and applies your original ratio at the export level:

```
App (AlwaysOn sampler — all spans created)
  → SampledSpanProcessor(0.1) → Your Datadog exporter → Datadog (sees 10%)
  → botanu exporter → botanu collector (sees 100%)
```

This is deterministic — the same trace_id always gets the same sampling decision.

## Manual Integration (Advanced)

If you prefer manual control or want to understand the internals:

```python
from opentelemetry import trace
from botanu.processors import RunContextEnricher, SampledSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Get your existing TracerProvider
provider = trace.get_tracer_provider()

# 1. Add RunContextEnricher (propagates run_id, workflow, event_id to all spans)
provider.add_span_processor(RunContextEnricher())

# 2. Add botanu OTLP exporter (sends traces to botanu collector)
botanu_exporter = OTLPSpanExporter(
    endpoint="https://ingest.botanu.ai:4318/v1/traces",
    headers={"Authorization": "Bearer btnu_live_..."},
)
provider.add_span_processor(BatchSpanProcessor(botanu_exporter))
```

## With Datadog (ddtrace)

ddtrace uses its own tracing system (not OTel SDK). `enable()` detects this and creates a separate TracerProvider for botanu:

```python
# ddtrace continues working unchanged
from ddtrace import tracer  # noqa — ddtrace auto-patches

# botanu creates its own provider alongside ddtrace
from botanu import enable
enable()
```

Both tracing systems run in parallel. No conflicts.

**Migration path** (optional, for simplification):
1. **Phase A** (now): Dual tracing — ddtrace + botanu
2. **Phase C** (later): Configure ddtrace OTLP export, remove botanu auto-instrumentation
3. **Phase D** (long-term): Migrate to OTel SDK + Datadog exporter — single tracing layer

## Using botanu Decorators

With either automatic or manual integration, use botanu decorators for cost attribution:

```python
from botanu import botanu_workflow, emit_outcome

@botanu_workflow(
    name="Customer Support",
    event_id=lambda req: req.ticket_id,
    customer_id=lambda req: req.org_id,
)
async def handle_ticket(req):
    result = await process(req)
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return result
```

All child spans (auto-instrumented OpenAI, database, HTTP calls) inherit the run context automatically via W3C Baggage.

## Troubleshooting

### run_id not appearing on spans
1. Verify `enable()` was called (or `RunContextEnricher` was added manually)
2. Check `@botanu_workflow` is on your entry point functions
3. Verify W3C Baggage propagator is active: `propagate.get_global_textmap()`

### Existing traces missing after adding botanu
This should not happen — `enable()` preserves your existing processors. If it does:
1. Check `enable()` was called ONCE (not multiple times)
2. Check your existing provider was created BEFORE `enable()` runs

### Sampling concerns
If you use ratio sampling and see unexpected volume changes in your APM:
1. Check botanu logs for "Preserved your sampling ratio" message
2. Verify `SampledSpanProcessor` is wrapping your exporter (not replacing it)
