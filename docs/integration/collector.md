# Botanu Cloud Collector

Botanu hosts a multi-tenant OpenTelemetry Collector — you don't need to deploy or manage any infrastructure.

## How It Works

The SDK sends telemetry to Botanu's hosted collector via OTLP over HTTPS. The collector handles:

- **Tenant isolation** — API key in the OTLP Authorization header identifies your tenant
- **PII scrubbing** — Configurable redaction of sensitive data patterns
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
export BOTANU_API_KEY="btnu_live_..."
```

```python
from botanu import enable

enable()  # reads BOTANU_API_KEY from env
```

### Override endpoint (advanced)

For development or testing against a local collector:

```python
enable(otlp_endpoint="http://localhost:4318")
```

Or via environment variable:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

## Data Flow

```
Your App (SDK)
    │
    │  OTLP/HTTP (TLS)
    │  Authorization: Bearer btnu_live_...
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

The collector applies PII scrubbing rules before data is stored. By default:

- Email addresses, phone numbers, SSNs, and credit card numbers are redacted
- Raw prompt/completion content is stripped (token counts are preserved for cost)
- Only aggregated summaries (cost, latency, token counts, outcome status) are stored

Configure additional scrubbing rules via the dashboard at **Settings → Data Privacy**.

## Sampling

For cost attribution accuracy, the collector processes 100% of traces. Unlike APM tools, sampling would produce incorrect cost numbers. The SDK sends all spans — the collector handles aggregation efficiently.

## See Also

- [Auto-Instrumentation](auto-instrumentation.md) — Library instrumentation
- [Architecture](../concepts/architecture.md) — SDK architecture
