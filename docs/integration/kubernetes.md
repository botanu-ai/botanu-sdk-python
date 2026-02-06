# Kubernetes Deployment

Zero-code instrumentation for large-scale deployments.

## Overview

For organizations with thousands of applications, modifying code in every repo is impractical. This guide covers zero-code instrumentation using Kubernetes-native approaches.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ App A       │  │ App B       │  │ App C       │             │
│  │ (entry)     │  │ (no change) │  │ (no change) │             │
│  │ @use_case   │  │             │  │             │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         │    OTel auto-injected via Operator                   │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │   OTel Collector      │                          │
│              │   (DaemonSet)         │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │ OTLP
                           ▼
                    Observability Backend
```

## Option 1: OTel Operator (Recommended)

The OpenTelemetry Operator automatically injects instrumentation into pods.

### Install Operator

```bash
# Install cert-manager (required)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# Install OTel Operator
kubectl apply -f https://github.com/open-telemetry/opentelemetry-operator/releases/latest/download/opentelemetry-operator.yaml
```

### Create Instrumentation Resource

```yaml
# instrumentation.yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: botanu-instrumentation
  namespace: default
spec:
  exporter:
    endpoint: http://otel-collector:4318
  propagators:
    - tracecontext
    - baggage
  python:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:latest
    env:
      - name: OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED
        value: "true"
```

```bash
kubectl apply -f instrumentation.yaml
```

### Annotate Deployments

Add a single annotation to enable instrumentation:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  template:
    metadata:
      annotations:
        instrumentation.opentelemetry.io/inject-python: "true"
    spec:
      containers:
        - name: app
          image: my-service:latest
          env:
            - name: OTEL_SERVICE_NAME
              value: "my-service"
```

No code changes required. The operator injects instrumentation at pod startup.

## Option 2: Environment Variables Only

For apps without operator, use environment variables:

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: app
          image: my-service:latest
          command: ["opentelemetry-instrument", "python", "app.py"]
          env:
            - name: OTEL_SERVICE_NAME
              value: "my-service"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector:4318"
            - name: OTEL_EXPORTER_OTLP_PROTOCOL
              value: "http/protobuf"
            - name: OTEL_PROPAGATORS
              value: "tracecontext,baggage"
            - name: OTEL_TRACES_EXPORTER
              value: "otlp"
            - name: OTEL_METRICS_EXPORTER
              value: "none"
            - name: OTEL_LOGS_EXPORTER
              value: "none"
```

Base image must include:
```dockerfile
RUN pip install opentelemetry-distro opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-requests \
    opentelemetry-instrumentation-openai-v2
```

## Option 3: Init Container

Inject instrumentation via init container:

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      initContainers:
        - name: otel-init
          image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:latest
          command: ["/bin/sh", "-c"]
          args:
            - cp -r /autoinstrumentation/. /otel-auto-instrumentation/
          volumeMounts:
            - name: otel-auto-instrumentation
              mountPath: /otel-auto-instrumentation
      containers:
        - name: app
          image: my-service:latest
          env:
            - name: PYTHONPATH
              value: "/otel-auto-instrumentation"
            - name: OTEL_SERVICE_NAME
              value: "my-service"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector:4318"
          volumeMounts:
            - name: otel-auto-instrumentation
              mountPath: /otel-auto-instrumentation
      volumes:
        - name: otel-auto-instrumentation
          emptyDir: {}
```

## OTel Collector Setup

Deploy collector as DaemonSet:

```yaml
# collector.yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel-collector
spec:
  mode: daemonset
  config: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    processors:
      batch:
        timeout: 5s
        send_batch_size: 1000

      # Extract run_id from baggage for querying
      attributes:
        actions:
          - key: botanu.run_id
            from_context: baggage
            action: upsert

    exporters:
      otlp:
        endpoint: "your-backend:4317"
        tls:
          insecure: false

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch, attributes]
          exporters: [otlp]
```

## Entry Point Service

Only the entry point service needs the Botanu decorator:

```python
# entry-service/app.py
from botanu import enable, botanu_use_case, emit_outcome

enable(service_name="entry-service")

@botanu_use_case(name="Customer Support")
async def handle_request(request_id: str):
    # Calls to downstream services propagate run_id automatically
    result = await call_service_b(request_id)
    emit_outcome("success")
    return result
```

Downstream services (B, C, D, etc.) need zero code changes.

## Helm Chart

For production deployments, use the Botanu Helm chart:

```bash
helm repo add botanu https://charts.botanu.ai
helm install botanu-collector botanu/collector \
  --set exporter.endpoint=your-backend:4317
```

Values:

```yaml
# values.yaml
collector:
  mode: daemonset
  resources:
    limits:
      cpu: 500m
      memory: 512Mi

instrumentation:
  enabled: true
  python:
    enabled: true
  propagators:
    - tracecontext
    - baggage

exporter:
  endpoint: "your-backend:4317"
  tls:
    enabled: true
```

## GitOps Integration

Add annotations via Kustomize:

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

patches:
  - patch: |
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: any
      spec:
        template:
          metadata:
            annotations:
              instrumentation.opentelemetry.io/inject-python: "true"
    target:
      kind: Deployment
      labelSelector: "instrumentation=enabled"
```

Label deployments to opt-in:

```yaml
metadata:
  labels:
    instrumentation: enabled
```

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name | `my-service` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector endpoint | `http://collector:4318` |
| `OTEL_PROPAGATORS` | Context propagators | `tracecontext,baggage` |
| `OTEL_TRACES_EXPORTER` | Trace exporter | `otlp` |
| `OTEL_RESOURCE_ATTRIBUTES` | Additional attributes | `deployment.environment=prod` |

## Rollout Strategy

For 2000+ applications:

1. **Phase 1**: Deploy OTel Collector (DaemonSet)
2. **Phase 2**: Install OTel Operator
3. **Phase 3**: Create Instrumentation resource
4. **Phase 4**: Add annotations via GitOps (batch by team/namespace)
5. **Phase 5**: Instrument entry points with `@botanu_use_case`

Each phase is independent. Annotations can be rolled out gradually.

## Troubleshooting

### Verify Injection

```bash
kubectl describe pod my-pod | grep -A5 "Init Containers"
```

### Check Instrumentation Logs

```bash
kubectl logs my-pod -c opentelemetry-auto-instrumentation
```

### Verify Collector Receiving

```bash
kubectl logs -l app=otel-collector | grep "TracesExporter"
```

## See Also

- [Collector Configuration](collector.md)
- [Auto-Instrumentation](auto-instrumentation.md)
- [Context Propagation](../concepts/context-propagation.md)
