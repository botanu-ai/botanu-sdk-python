# Using botanu with an existing OTel / APM setup

botanu is designed to sit alongside an OTel / Datadog / Jaeger / Honeycomb / New Relic setup you already have. You do not have to migrate off your current APM — on first use, the SDK detects what is already configured and adds itself without stealing spans or changing your sampled volume.

## TL;DR

- **Already on the OTel SDK?** botanu keeps your span processors, preserves your sampling ratio for them, and adds the botanu exporter at 100%. Your existing APM bill does not change.
- **Already on ddtrace (Datadog's Python SDK)?** botanu runs on a separate, parallel TracerProvider. ddtrace is untouched.
- **No existing tracing?** botanu creates a fresh provider and wires everything up.

Integration is a single line per service:

```python
import botanu

with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

---

## What botanu does on first use

On the first `botanu.event(...)` call, the SDK calls `trace.get_tracer_provider()` and branches on what it finds. The logic lives in [`src/botanu/sdk/bootstrap.py`](../../src/botanu/sdk/bootstrap.py).

| What `get_tracer_provider()` returns | What botanu does |
| --- | --- |
| `opentelemetry.sdk.trace.TracerProvider` (the real OTel SDK class) | Creates a new provider, migrates your span processors, wraps ratio-sampled processors in `SampledSpanProcessor`, adds botanu alongside, swaps the global provider. |
| `opentelemetry.trace.ProxyTracerProvider` (no real provider set) | Creates a fresh provider with `ALWAYS_ON` sampling. |
| Anything else (e.g., `ddtrace.opentelemetry.TracerProvider`) | Creates a separate TracerProvider for botanu. Your existing tracer is untouched. |

botanu never mutates your existing provider in place. It either creates a new one and swaps the global, or leaves yours entirely alone.

---

## If you already run the OTel SDK

### What botanu does

1. Detects your existing `TracerProvider`.
2. Reads its sampler. If it's a ratio sampler (e.g., `TraceIdRatioBased(0.1)`), botanu records the ratio.
3. Creates a new provider with `ALWAYS_ON` sampling.
4. Migrates your existing span processors to the new provider.
5. Wraps each migrated processor in `SampledSpanProcessor(ratio)` so your exporters still see their original sampled subset.
6. Adds botanu's own exporter at 100% alongside.
7. Swaps the global provider.

### Result

- Your existing APM keeps getting the same sampled volume it always did. Your bill does not change.
- botanu captures 100% of spans for cost attribution.
- Every span — yours and auto-instrumented — carries the run context from [W3C Baggage](https://www.w3.org/TR/baggage/).

### Sampling preservation

| Your sampler | botanu sees | Your APM sees |
| --- | --- | --- |
| `AlwaysOn` | 100% | 100% |
| `TraceIdRatioBased(0.1)` | 100% | 10% |
| `ParentBased(TraceIdRatioBased(0.1))` | 100% | 10% |
| `AlwaysOff` | 100% | 0% |
| A custom sampler botanu can't introspect | the sampled subset only | unchanged |

The custom-sampler case is the one edge we can't preserve exactly — botanu logs a warning (`could not identify the sampling ratio of X`) and falls back to using your sampler. Cost attribution is still correct, just computed on fewer spans.

---

## If you already run ddtrace

`ddtrace` (Datadog's Python SDK) installs its own tracer that implements the OTel API but extends a different base class than the OTel SDK. botanu detects this via `isinstance(existing, TracerProvider)` returning `False` and falls through to the parallel path.

In the parallel path:

- botanu creates its own `TracerProvider` and does **not** call `trace.set_tracer_provider(...)`.
- ddtrace keeps handling spans for ddtrace decorators and for Datadog auto-instrumentation.
- botanu's API (`botanu.event`, `track_llm_call`, etc.) gets its spans from the botanu provider, which forwards to the botanu collector.

The two tracing systems coexist. Nothing is stolen, nothing is wrapped.

A span will appear in Datadog if it was created inside ddtrace instrumentation, and in botanu if it was created inside botanu instrumentation. To cross-reference a trace between the two dashboards, use `botanu.run_id` — it is set via W3C Baggage on every botanu span, and you can write a small Datadog tag mapper to surface it on ddtrace spans too if you want.

### Longer-term option

If you eventually want a single tracing layer, the migration path is:

1. Today: dual tracing — ddtrace + botanu running in parallel.
2. Later: switch ddtrace off, move to the OTel SDK, configure the OTel Datadog exporter. Now botanu's provider-migration path kicks in and you're back to one provider with two exporters.

We do not require this and there is no deadline — the parallel setup is supported indefinitely.

---

## If you have no existing tracing

If `trace.get_tracer_provider()` returns a `ProxyTracerProvider`, nothing is configured yet. botanu creates a fresh `TracerProvider` with `ALWAYS_ON`, adds `RunContextEnricher` / `ResourceEnricher` / botanu's exporter, and sets it as the global. This is the standard path for first-time users.

---

## Using the botanu API

Regardless of which path the SDK takes on initialisation, the API is the same:

```python
import botanu

@botanu.event(
    workflow="Customer Support",
    event_id=lambda req: req.ticket_id,
    customer_id=lambda req: req.org_id,
)
async def handle_ticket(req):
    result = await process(req)
    botanu.emit_outcome(value_type="tickets_resolved", value_amount=1)
    return result
```

Auto-instrumented spans (OpenAI SDK, HTTP clients, DB drivers) inside the event scope inherit the run context through [W3C Baggage](https://www.w3.org/TR/baggage/), so cost attribution works even for spans your code never directly creates. See [Auto-Instrumentation](auto-instrumentation.md).

---

## Manual integration (advanced, OTel SDK only)

If you want to wire botanu into an existing OTel SDK provider without letting the SDK auto-initialise, you can attach the processors yourself:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from botanu.processors import RunContextEnricher, SampledSpanProcessor

provider = trace.get_tracer_provider()
assert isinstance(provider, TracerProvider), "manual integration requires the OTel SDK provider"

provider.add_span_processor(RunContextEnricher())

botanu_exporter = OTLPSpanExporter(
    endpoint="https://ingest.botanu.ai:4318/v1/traces",
    headers={"Authorization": "Bearer <your-botanu-api-key>"},
)
provider.add_span_processor(BatchSpanProcessor(botanu_exporter))
```

**This does not work for ddtrace.** ddtrace's `TracerProvider` does not expose `add_span_processor()`. If you are on ddtrace, let the SDK auto-initialise and take the parallel path.

Manual integration also skips the `SampledSpanProcessor` preservation logic — if your provider uses ratio sampling and you need botanu to still see 100%, you'd have to duplicate the bootstrap logic. Letting the SDK auto-initialise handles this for you.

---

## Verifying it worked

After your first `botanu.event(...)` call runs, you should see exactly one of these log lines:

| Log line | Means |
| --- | --- |
| `existing TracerProvider detected with N% sampling. Preserved your sampling ratio` | OTel SDK with known sampler. Your APM gets the same volume, botanu gets 100%. |
| `existing TracerProvider detected. Added botanu exporter alongside your existing setup` | OTel SDK with AlwaysOn. Both exporters get 100%. |
| `could not identify the sampling ratio of X. Preserving the original sampler` | OTel SDK with unknown sampler. Both exporters see the sampled subset. |
| (none of the above) | No existing tracing, or ddtrace parallel — check `botanu.is_enabled()`. |

Sanity checks in order:

1. Open your existing APM — confirm span volume is unchanged.
2. Open botanu — confirm spans are arriving. A run created by `botanu.event(...)` carries `botanu.run_id`, `botanu.workflow`, `botanu.event_id`.
3. If both arrive, you're done.

---

## Troubleshooting

### My spans disappeared from Datadog after I installed botanu

Should not happen. Check, in order:

1. Your existing OTel provider was created **before** the first `botanu.event(...)` call. If the SDK initialises first, it won't detect your provider and will replace it.
2. Your existing exporter was actually attached to the provider botanu detected. If you have multiple providers (per-module, per-service), the one `trace.get_tracer_provider()` returns is the one botanu wraps — processors attached to others are unaffected (and therefore invisible to botanu too).

### botanu shows 100% of spans but Datadog only shows 10%

That's the expected behaviour with a ratio sampler. botanu captures 100% for cost attribution; your existing exporter stays on its original ratio so your bill and dashboards are unchanged. Look for the log line starting `Preserved your sampling ratio`.

### `run_id` is missing on auto-instrumented spans

1. Verify an entry-point function or block uses `botanu.event(...)` — the baggage is set on entry and inherited by child spans from there.
2. Verify the W3C Baggage propagator is active: `from opentelemetry import propagate; propagate.get_global_textmap()` should include `baggage` in its composite.

### `could not identify the sampling ratio` warning

Your sampler is a type botanu doesn't recognise. Two options:

1. Accept it — botanu sees only the sampled subset. Cost attribution is still correct, just computed on fewer spans.
2. Switch to `TraceIdRatioBased(...)`, `ParentBased(TraceIdRatioBased(...))`, `AlwaysOn`, or `AlwaysOff` so botanu can preserve your ratio exactly.
