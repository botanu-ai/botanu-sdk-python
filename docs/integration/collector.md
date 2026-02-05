# Collector Configuration

Set up the OpenTelemetry Collector for cost attribution processing.

## Overview

Botanu follows a "thin SDK, smart collector" architecture. The SDK captures raw telemetry; the collector handles:

- **PII redaction** - Remove sensitive data from prompts/responses
- **Cost calculation** - Convert tokens to dollars using pricing tables
- **Vendor normalization** - Standardize provider names
- **Cardinality management** - Limit high-cardinality attributes
- **Aggregation** - Pre-aggregate metrics for dashboards

## Quick Start

### Docker

```bash
docker run -p 4318:4318 -p 4317:4317 \
  -v $(pwd)/otel-config.yaml:/etc/otelcol/config.yaml \
  otel/opentelemetry-collector-contrib:latest
```

### Docker Compose

```yaml
services:
  collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4318:4318"   # OTLP HTTP
      - "4317:4317"   # OTLP gRPC
    volumes:
      - ./otel-config.yaml:/etc/otelcol/config.yaml
```

## Basic Configuration

```yaml
# otel-config.yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    send_batch_size: 1000
    timeout: 10s

exporters:
  debug:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug]
```

## Cost Attribution Configuration

### Full Pipeline

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  # Batch for efficiency
  batch:
    send_batch_size: 1000
    timeout: 10s

  # Normalize vendor names
  transform/vendor:
    trace_statements:
      - context: span
        statements:
          # Normalize provider names to standard format
          - set(attributes["botanu.vendor"], "openai") where attributes["gen_ai.provider.name"] == "openai"
          - set(attributes["botanu.vendor"], "anthropic") where attributes["gen_ai.provider.name"] == "anthropic"
          - set(attributes["botanu.vendor"], "azure.openai") where attributes["gen_ai.provider.name"] == "azure.openai"
          - set(attributes["botanu.vendor"], "gcp.vertex_ai") where attributes["gen_ai.provider.name"] == "gcp.vertex_ai"
          - set(attributes["botanu.vendor"], "aws.bedrock") where attributes["gen_ai.provider.name"] == "aws.bedrock"

  # Calculate costs from tokens
  transform/cost:
    trace_statements:
      - context: span
        statements:
          # GPT-4 pricing (example: $30/$60 per 1M tokens)
          - set(attributes["botanu.cost.input_usd"],
              attributes["gen_ai.usage.input_tokens"] * 0.00003)
            where attributes["gen_ai.request.model"] == "gpt-4"
          - set(attributes["botanu.cost.output_usd"],
              attributes["gen_ai.usage.output_tokens"] * 0.00006)
            where attributes["gen_ai.request.model"] == "gpt-4"

          # GPT-4 Turbo pricing ($10/$30 per 1M tokens)
          - set(attributes["botanu.cost.input_usd"],
              attributes["gen_ai.usage.input_tokens"] * 0.00001)
            where attributes["gen_ai.request.model"] == "gpt-4-turbo"
          - set(attributes["botanu.cost.output_usd"],
              attributes["gen_ai.usage.output_tokens"] * 0.00003)
            where attributes["gen_ai.request.model"] == "gpt-4-turbo"

          # Claude 3 Opus pricing ($15/$75 per 1M tokens)
          - set(attributes["botanu.cost.input_usd"],
              attributes["gen_ai.usage.input_tokens"] * 0.000015)
            where attributes["gen_ai.request.model"] == "claude-3-opus-20240229"
          - set(attributes["botanu.cost.output_usd"],
              attributes["gen_ai.usage.output_tokens"] * 0.000075)
            where attributes["gen_ai.request.model"] == "claude-3-opus-20240229"

          # Calculate total
          - set(attributes["botanu.cost.total_usd"],
              attributes["botanu.cost.input_usd"] + attributes["botanu.cost.output_usd"])
            where attributes["botanu.cost.input_usd"] != nil

  # PII redaction for prompts/responses
  redaction:
    allow_all_keys: true
    blocked_values:
      # Email addresses
      - "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"
      # Phone numbers
      - "\\b\\d{3}[-.]?\\d{3}[-.]?\\d{4}\\b"
      # SSN
      - "\\b\\d{3}-\\d{2}-\\d{4}\\b"
      # Credit card numbers
      - "\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\\b"

  # Cardinality limits
  attributes:
    actions:
      - key: botanu.run_id
        action: hash
        # Keep first 16 chars of hash to reduce cardinality if needed
      - key: gen_ai.content.prompt
        action: delete
        # Remove raw prompts (keep tokens for cost)

exporters:
  # ClickHouse for analytics
  clickhouse:
    endpoint: tcp://clickhouse:9000
    database: botanu
    ttl: 90d
    create_schema: true

  # Also send to your APM
  otlp/apm:
    endpoint: https://your-apm.example.com
    headers:
      Authorization: Bearer ${APM_TOKEN}

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors:
        - batch
        - transform/vendor
        - transform/cost
        - redaction
        - attributes
      exporters: [clickhouse, otlp/apm]
```

## PII Redaction

### Using Redaction Processor

```yaml
processors:
  redaction:
    allow_all_keys: true
    blocked_values:
      # Redact common PII patterns
      - "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"  # Email
      - "\\b\\d{3}[-.]?\\d{3}[-.]?\\d{4}\\b"  # Phone
      - "\\b\\d{3}-\\d{2}-\\d{4}\\b"  # SSN
    summary: debug  # Log redaction summary
```

### Using Transform Processor

```yaml
processors:
  transform/pii:
    trace_statements:
      - context: span
        statements:
          # Remove prompt content entirely
          - delete(attributes["gen_ai.content.prompt"])
          - delete(attributes["gen_ai.content.completion"])

          # Or replace with placeholder
          - replace_pattern(attributes["gen_ai.content.prompt"],
              "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",
              "[REDACTED_EMAIL]")
```

## Pricing Tables

Maintain pricing in the collector config:

```yaml
processors:
  transform/cost:
    trace_statements:
      - context: span
        statements:
          # OpenAI pricing (as of 2024)
          # GPT-4
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.00003)
            where attributes["gen_ai.request.model"] == "gpt-4" or attributes["gen_ai.request.model"] == "gpt-4-0613"
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.00006)
            where attributes["gen_ai.request.model"] == "gpt-4" or attributes["gen_ai.request.model"] == "gpt-4-0613"

          # GPT-4 Turbo
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.00001)
            where IsMatch(attributes["gen_ai.request.model"], "gpt-4-turbo.*")
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.00003)
            where IsMatch(attributes["gen_ai.request.model"], "gpt-4-turbo.*")

          # GPT-4o
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.000005)
            where IsMatch(attributes["gen_ai.request.model"], "gpt-4o.*")
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.000015)
            where IsMatch(attributes["gen_ai.request.model"], "gpt-4o.*")

          # GPT-3.5 Turbo
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.0000005)
            where IsMatch(attributes["gen_ai.request.model"], "gpt-3.5-turbo.*")
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.0000015)
            where IsMatch(attributes["gen_ai.request.model"], "gpt-3.5-turbo.*")

          # Claude 3 Opus
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.000015)
            where IsMatch(attributes["gen_ai.request.model"], "claude-3-opus.*")
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.000075)
            where IsMatch(attributes["gen_ai.request.model"], "claude-3-opus.*")

          # Claude 3 Sonnet
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.000003)
            where IsMatch(attributes["gen_ai.request.model"], "claude-3-sonnet.*")
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.000015)
            where IsMatch(attributes["gen_ai.request.model"], "claude-3-sonnet.*")

          # Claude 3 Haiku
          - set(attributes["botanu.cost.input_usd"], attributes["gen_ai.usage.input_tokens"] * 0.00000025)
            where IsMatch(attributes["gen_ai.request.model"], "claude-3-haiku.*")
          - set(attributes["botanu.cost.output_usd"], attributes["gen_ai.usage.output_tokens"] * 0.00000125)
            where IsMatch(attributes["gen_ai.request.model"], "claude-3-haiku.*")

          # Total cost
          - set(attributes["botanu.cost.total_usd"],
              attributes["botanu.cost.input_usd"] + attributes["botanu.cost.output_usd"])
            where attributes["botanu.cost.input_usd"] != nil and attributes["botanu.cost.output_usd"] != nil
```

## Backend Exporters

### ClickHouse

```yaml
exporters:
  clickhouse:
    endpoint: tcp://clickhouse:9000
    database: botanu
    username: default
    password: ${CLICKHOUSE_PASSWORD}
    ttl: 90d
    create_schema: true
    logs_table_name: otel_logs
    traces_table_name: otel_traces
    metrics_table_name: otel_metrics
```

### PostgreSQL (via OTLP)

Use the collector to forward to a service that writes to PostgreSQL:

```yaml
exporters:
  otlp:
    endpoint: http://postgres-writer:4317
```

### Prometheus (Metrics)

```yaml
exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: botanu
```

### Grafana Tempo

```yaml
exporters:
  otlp:
    endpoint: tempo:4317
    tls:
      insecure: true
```

## Sampling

For cost attribution, avoid sampling. If you must sample:

```yaml
processors:
  probabilistic_sampler:
    sampling_percentage: 100  # Keep 100% for cost attribution

  # Or sample only non-LLM spans
  tail_sampling:
    decision_wait: 10s
    policies:
      # Always keep LLM calls
      - name: always-sample-llm
        type: string_attribute
        string_attribute:
          key: gen_ai.operation.name
          values: [chat, text_completion, embeddings]

      # Sample other spans at 10%
      - name: sample-other
        type: probabilistic
        probabilistic:
          sampling_percentage: 10
```

## High Availability

### Load Balancing

```yaml
# collector-1.yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

exporters:
  loadbalancing:
    protocol:
      otlp:
        tls:
          insecure: true
    resolver:
      dns:
        hostname: collector-pool.svc.cluster.local
        port: 4317
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
spec:
  replicas: 3
  selector:
    matchLabels:
      app: otel-collector
  template:
    spec:
      containers:
        - name: collector
          image: otel/opentelemetry-collector-contrib:latest
          ports:
            - containerPort: 4318
            - containerPort: 4317
          volumeMounts:
            - name: config
              mountPath: /etc/otelcol
      volumes:
        - name: config
          configMap:
            name: otel-collector-config
```

## Monitoring the Collector

Enable internal telemetry:

```yaml
service:
  telemetry:
    logs:
      level: info
    metrics:
      level: detailed
      address: 0.0.0.0:8888
```

Access metrics at `http://collector:8888/metrics`.

## See Also

- [Architecture](../concepts/architecture.md) - SDK architecture
- [Auto-Instrumentation](auto-instrumentation.md) - Library instrumentation
- [Best Practices](../patterns/best-practices.md) - Configuration patterns
