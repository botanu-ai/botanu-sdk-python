# Using botanu with an existing OTel / APM setup

botanu is designed to sit alongside an OTel / Datadog / Jaeger / Honeycomb /
New Relic setup you already have. You do not have to migrate off your current
APM — you call `enable()`, and botanu detects what is already configured and
adds itself without stealing spans or changing your sampled volume.

This page explains exactly what `enable()` does in each of the three
configurations it detects, so you can reason about the outcome before you
install.

## TL;DR

- **Already on the OTel SDK?** `enable()` keeps your span processors, preserves
  your sampling ratio for them, and adds the botanu exporter at 100%.
  Your existing APM bill does not change.
- **Already on ddtrace (Datadog's Python SDK)?** `enable()` creates a
  separate, parallel TracerProvider for botanu. ddtrace is untouched.
- **No existing tracing?** `enable()` creates a fresh provider and wires
  everything up for you.

In all three cases the SDK is a single call:

```python
from botanu import enable
enable()  # reads config from env; no hard-coded values
```

---

## Detection — what `enable()` checks

When you call `enable()`, the SDK calls `trace.get_tracer_provider()` and
branches on what it finds. The logic lives in
[`src/botanu/sdk/bootstrap.py`](../../src/botanu/sdk/bootstrap.py).

| What `get_tracer_provider()` returns | What botanu does |
| --- | --- |
| `opentelemetry.sdk.trace.TracerProvider` (the real OTel SDK class) | Treats as **brownfield OTel**. Creates a new provider, migrates your span processors, wraps ratio-sampled processors in `SampledSpanProcessor`, adds botanu alongside, swaps the global provider. |
| `opentelemetry.trace.ProxyTracerProvider` (no real provider set) | Treats as **greenfield**. Creates a fresh provider with `ALWAYS_ON` sampling. |
| Anything else (e.g., `ddtrace.opentelemetry.TracerProvider`) | Treats as **unknown / parallel**. Creates a separate TracerProvider for botanu. Your existing tracer is untouched. |

botanu never mutates your existing provider in place. It either creates a
new one and swaps the global, or leaves yours entirely alone.

---

## Brownfield: existing OTel SDK

### What botanu does

1. Reads the sampling ratio off your provider using
   `_extract_sampler_ratio()`. This recognises `AlwaysOn`, `AlwaysOff`,
   `TraceIdRatioBased`, and `ParentBased(...)` wrappers around those.
2. Collects the list of processors already attached to your provider.
3. Creates a **new** `TracerProvider` with `ALWAYS_ON`, keeping your
   `Resource`.
4. For each of your existing processors:
   - If your ratio was `< 1.0`, wraps the processor in a
     `SampledSpanProcessor(proc, original_ratio)` so it continues to see
     only the fraction of spans it used to.
   - Otherwise attaches it as-is.
5. Adds `RunContextEnricher` (run_id / workflow / event_id baggage → span
   attributes), `ResourceEnricher`, and botanu's own `BatchSpanProcessor`
   to the new provider — **unwrapped**, so botanu sees 100%.
6. `trace.set_tracer_provider(new_provider)` — this becomes the global.
7. Logs one of:

   ```text
   Botanu SDK: existing TracerProvider detected with 10% sampling.
   Preserved your sampling ratio for existing exporters.
   botanu captures 100%. No impact on your existing observability bill.
   ```

   or, for 100% samplers:

   ```text
   Botanu SDK: existing TracerProvider detected.
   Added botanu exporter alongside your existing setup.
   ```

### Why flip to AlwaysOn internally?

botanu needs 100% of spans to produce accurate cost attribution — you can't
extrapolate token counts or per-span costs from a 10% sample without
distortion. So the new provider is `ALWAYS_ON`. The resulting diagram:

```text
App   (sampler = AlwaysOn → every span created)
 │
 ├─ SampledSpanProcessor(0.10) → your Datadog BatchSpanProcessor → Datadog (sees 10%)
 │                                                                          ↑ same volume as before
 │
 └─ botanu BatchSpanProcessor → botanu collector (sees 100%)
```

`SampledSpanProcessor` is deterministic on `trace_id`, matching OTel's
`TraceIdRatioBasedSampler` algorithm — the same trace always gets the same
decision, so a trace that hits Datadog also hits 100% of botanu spans and
nothing is orphaned.

### Unknown sampler — safety path

If `_extract_sampler_ratio()` cannot identify your sampler (custom
subclass, third-party library), botanu **does not assume 100%**. Instead it:

1. Logs a warning with your sampler's class name.
2. Creates the new provider with your **original sampler** preserved.
3. Attaches your processors unwrapped — they see what they saw before.
4. Attaches botanu's processors also under your original sampler — meaning
   botanu will see only the sampled subset too, not 100%.

This is deliberate. Silently defaulting an unknown sampler to 1.0 would
inflate your existing exporter's volume 10× or 100× and potentially blow up
your observability bill. The cost of the unknown path is that botanu's cost
numbers are computed on the sampled subset; accept that or migrate your
sampler to a known one (`AlwaysOn` / `TraceIdRatioBased` /
`ParentBased(TraceIdRatioBased(...))`).

---

## Parallel: ddtrace

`ddtrace` (Datadog's Python SDK) installs its own tracer that implements
the OTel API but extends a different base class than the OTel SDK. botanu
detects this via `isinstance(existing, TracerProvider)` returning `False`
and falls through to the parallel path.

In the parallel path:

- botanu creates its own `TracerProvider` and does **not** call
  `trace.set_tracer_provider(...)`.
- ddtrace keeps handling spans for ddtrace decorators and for Datadog
  auto-instrumentation.
- botanu's decorators (`@botanu_workflow`, `track_llm_call`, etc.) get
  their spans from the botanu provider, which forwards to the botanu
  collector.

The two tracing systems coexist. Nothing is stolen, nothing is wrapped.

A span will appear in Datadog if it was created inside ddtrace
instrumentation, and in botanu if it was created inside botanu
instrumentation. To cross-reference a trace between the two dashboards, use
`botanu.run_id` — it is set via W3C Baggage on every botanu span, and you
can write a small Datadog tag mapper to surface it on ddtrace spans too if
you want.

### Longer-term option

If you eventually want a single tracing layer, the migration path is:

1. Today: dual tracing — ddtrace + botanu running in parallel.
2. Later: switch ddtrace off, move to the OTel SDK, configure the OTel
   Datadog exporter. Now botanu's brownfield path kicks in and you're back
   to one provider with two exporters.

We do not require this and there is no deadline — the parallel setup is
supported indefinitely.

---

## Greenfield: no existing tracing

If `trace.get_tracer_provider()` returns a `ProxyTracerProvider`, nothing
is configured yet. botanu creates a fresh `TracerProvider` with
`ALWAYS_ON`, adds `RunContextEnricher` / `ResourceEnricher` / botanu's
exporter, and sets it as the global. This is the standard path for
first-time users.

---

## Using botanu decorators

Regardless of which path `enable()` takes, the decorator API is the same:

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

Auto-instrumented spans (OpenAI SDK, HTTP clients, DB drivers) inside the
decorated call inherit the run context through W3C Baggage, so cost
attribution works even for spans your code never directly creates. See
[Auto-Instrumentation](auto-instrumentation.md).

---

## Manual integration (advanced, OTel SDK only)

If you want to wire botanu into an existing OTel SDK provider without
calling `enable()` at all, you can attach the processors yourself:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from botanu.processors import RunContextEnricher, SampledSpanProcessor

provider = trace.get_tracer_provider()
assert isinstance(provider, TracerProvider), "manual integration requires the OTel SDK provider"

# 1. Enrich all spans with run_id / workflow / event_id from baggage.
provider.add_span_processor(RunContextEnricher())

# 2. Send a copy of every span to the botanu collector.
botanu_exporter = OTLPSpanExporter(
    endpoint="https://ingest.botanu.ai:4318/v1/traces",
    headers={"Authorization": "Bearer <your-botanu-api-key>"},
)
provider.add_span_processor(BatchSpanProcessor(botanu_exporter))
```

**This does not work for ddtrace.** ddtrace's `TracerProvider` does not
expose `add_span_processor()`. If you are on ddtrace, use `enable()` and
let the SDK take the parallel path.

Manual integration also skips the `SampledSpanProcessor` preservation
logic — if your provider uses ratio sampling and you need botanu to still
see 100%, you'd have to duplicate the bootstrap logic. Just call
`enable()`; that's what it's for.

---

## Verifying it worked

After installing and calling `enable()`, you should see exactly one of
these log lines:

| Log line | Means |
| --- | --- |
| `existing TracerProvider detected with N% sampling. Preserved your sampling ratio` | Brownfield OTel SDK with known sampler. Your APM gets the same volume, botanu gets 100%. |
| `existing TracerProvider detected. Added botanu exporter alongside your existing setup` | Brownfield OTel SDK with AlwaysOn. Both exporters get 100%. |
| `could not identify the sampling ratio of X. Preserving the original sampler` | Brownfield OTel SDK with unknown sampler. Both exporters see the sampled subset. |
| (no brownfield line) | Greenfield or ddtrace parallel — check the `enable()` return value. |

Sanity checks in order:

1. Open your existing APM — confirm span volume is unchanged.
2. Open botanu — confirm spans are arriving. A run created by
   `@botanu_workflow` carries `botanu.run_id`, `botanu.workflow`,
   `botanu.event_id`.
3. If both arrive, you're done.

---

## Troubleshooting

### My spans disappeared from Datadog after I installed botanu

Should not happen. Check, in order:

1. `enable()` was called exactly once at startup — if called twice, both
   calls no-op after the first, so duplicate calls are safe but indicate a
   confused startup order.
2. Your existing OTel provider was created **before** `enable()` runs. If
   `enable()` runs first, brownfield detection doesn't see you and you'll
   end up on the greenfield path, which blows away an OTel provider set
   afterwards.
3. Your existing exporter was actually attached to the provider botanu
   detected. If you have multiple providers (per-module, per-service), the
   one `trace.get_tracer_provider()` returns is the one botanu wraps —
   processors attached to others are unaffected (and therefore invisible
   to botanu too).

### botanu shows 100% of spans but Datadog only shows 10%

That's the expected brownfield behavior with a ratio sampler. botanu
captures 100% for cost attribution; your existing exporter stays on its
original ratio so your bill and dashboards are unchanged. Look for the log
line starting `Preserved your sampling ratio`.

### `run_id` is missing on auto-instrumented spans

1. Verify `enable()` was called (or `RunContextEnricher` was attached
   manually).
2. Verify an entry-point function is wrapped in `@botanu_workflow` — the
   baggage is set on entry and inherited by child spans from there.
3. Verify the W3C Baggage propagator is active:
   `from opentelemetry import propagate; propagate.get_global_textmap()`
   should include `baggage` in its composite.

### `could not identify the sampling ratio` warning

Your sampler is a type botanu doesn't recognise. Two options:

1. Accept it — botanu sees only the sampled subset. Cost attribution is
   still correct, just computed on fewer spans.
2. Switch to `TraceIdRatioBased(...)`, `ParentBased(TraceIdRatioBased(...))`,
   `AlwaysOn`, or `AlwaysOff` on your `TracerProvider`. botanu will then
   take the normal brownfield path and preserve your ratio for existing
   processors while capturing 100% for itself.

## See also

- [Collector](collector.md) — where botanu's spans go next
- [Auto-Instrumentation](auto-instrumentation.md) — the span sources
- [Configuration](../getting-started/configuration.md) — env vars, endpoint trust
- Source of truth: [`src/botanu/sdk/bootstrap.py`](../../src/botanu/sdk/bootstrap.py) and [`src/botanu/processors/sampled.py`](../../src/botanu/processors/sampled.py)
