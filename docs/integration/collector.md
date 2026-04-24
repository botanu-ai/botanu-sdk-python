# Botanu Cloud Collector

Botanu hosts a multi-tenant OpenTelemetry Collector — you don't need to deploy or manage any infrastructure.

## How It Works

The SDK sends telemetry to Botanu's hosted collector via OTLP over HTTPS. The collector handles:

- **Tenant isolation** — API key in the OTLP Authorization header identifies your tenant
- **PII scrubbing (belt-and-suspenders)** — Regex pass over `botanu.eval.*` attributes; the SDK already scrubs captured content in-process before it leaves your application
- **Enrichment** — Vendor normalization, span classification
- **Aggregation** — Event-level accumulation (spans → run summaries)
- **Cost computation** — Token-to-dollar conversion using the pricing rate card
- **Durable spooling** — Hybrid local disk + S3 spool ensures zero trace loss

## Endpoints

| Protocol | Endpoint | Port |
|----------|----------|------|
| gRPC | `ingest.botanu.ai:4317` | 4317 |
| HTTP | `ingest.botanu.ai:4318` | 4318 |

The SDK defaults to HTTP (`ingest.botanu.ai:4318`) when `BOTANU_API_KEY` is set.

## Configuration

No collector configuration is needed on your side. Just set the API key:

```bash
export BOTANU_API_KEY=<your-api-key>
```

The SDK reads this at initialisation and routes OTLP exports to `https://ingest.botanu.ai`.

### Override endpoint (advanced)

For development or testing against a local collector:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

### ⚠ The API key is only sent to botanu-trusted endpoints

If you override the endpoint to a non-botanu host (e.g., a self-hosted
collector, Datadog, or any third-party OTLP backend), the SDK **does not
attach your `BOTANU_API_KEY` as an Authorization header**. This prevents a
misconfigured `OTEL_EXPORTER_OTLP_ENDPOINT` from leaking tenant
credentials to another vendor. Trusted hosts are `*.botanu.ai` plus local
dev hosts (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`); everything else
runs unauthenticated unless you pass your own `otlp_headers=`. See the
[Configuration doc](../getting-started/configuration.md#️-the-api-key-is-only-sent-to-botanu-trusted-endpoints)
for the full list.

## Data Flow

```
Your App (SDK)
    │
    │  OTLP/HTTP (TLS)
    │  Authorization: Bearer <your-api-key>
    ▼
ingest.botanu.ai (Botanu-hosted collector)
    │
    │  PII scrub → enrich → aggregate → spool
    ▼
Botanu Cost Engine (api.botanu.ai)
    │
    │  Cost computation → rollups → storage
    ▼
PostgreSQL (Botanu-managed RDS)
    │
    ▼
Dashboard (app.botanu.ai)
```

## PII Handling

PII scrubbing runs in **two layers** — the SDK strips captured content
in-process (your application sees only `[REDACTED]` in exported spans),
and the collector runs a second regex pass as belt-and-suspenders.

**SDK (in-process, first line of defense):**

- Runs on text passed to `set_input_content` / `set_output_content` /
  `set_retrieval_content` and on `botanu.event(...)` auto-captured payloads
- On by default — opt-out via `BOTANU_PII_SCRUB_ENABLED=false`
- See [Content Capture → PII handling](../tracking/content-capture.md#pii-handling)

**Collector (belt-and-suspenders):**

- Email addresses, phone numbers, SSNs, and credit card numbers are redacted
- Raw prompt/completion content is stripped (token counts are preserved for cost)
- Only aggregated summaries (cost, latency, token counts, outcome status) are stored
- Configure additional scrubbing rules via the dashboard at **Settings → Data Privacy**

## Sampling

For cost attribution accuracy, the collector processes 100% of traces. Unlike APM tools, sampling would produce incorrect cost numbers. The SDK sends all spans — the collector handles aggregation efficiently.

## See Also

- [Auto-Instrumentation](auto-instrumentation.md) — Library instrumentation
- [Architecture](../concepts/architecture.md) — SDK architecture
