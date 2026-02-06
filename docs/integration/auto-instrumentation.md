# Auto-Instrumentation

Automatically instrument common libraries without code changes.

## Installation

```bash
pip install "botanu[all]"
```

## Usage

```python
from botanu import enable, botanu_use_case

enable(service_name="my-service")

@botanu_use_case(name="my_workflow")
def my_function():
    data = db.query(...)
    result = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": data}]
    )
    return result
```

All operations inside are automatically traced.

## Supported Libraries

### HTTP Clients

| Library | Package |
|---------|---------|
| requests | `opentelemetry-instrumentation-requests` |
| httpx | `opentelemetry-instrumentation-httpx` |
| urllib3 | `opentelemetry-instrumentation-urllib3` |
| aiohttp | `opentelemetry-instrumentation-aiohttp-client` |

### Web Frameworks

| Framework | Package |
|-----------|---------|
| FastAPI | `opentelemetry-instrumentation-fastapi` |
| Flask | `opentelemetry-instrumentation-flask` |
| Django | `opentelemetry-instrumentation-django` |
| Starlette | `opentelemetry-instrumentation-starlette` |

### Databases

| Database | Package |
|----------|---------|
| SQLAlchemy | `opentelemetry-instrumentation-sqlalchemy` |
| psycopg2 | `opentelemetry-instrumentation-psycopg2` |
| asyncpg | `opentelemetry-instrumentation-asyncpg` |
| pymongo | `opentelemetry-instrumentation-pymongo` |
| redis | `opentelemetry-instrumentation-redis` |

### Messaging

| System | Package |
|--------|---------|
| Celery | `opentelemetry-instrumentation-celery` |
| Kafka | `opentelemetry-instrumentation-kafka-python` |

### LLM Providers

| Provider | Package |
|----------|---------|
| OpenAI | `opentelemetry-instrumentation-openai-v2` |
| Anthropic | `opentelemetry-instrumentation-anthropic` |
| Vertex AI | `opentelemetry-instrumentation-vertexai` |
| Google GenAI | `opentelemetry-instrumentation-google-genai` |
| LangChain | `opentelemetry-instrumentation-langchain` |

## Context Propagation

HTTP clients automatically propagate `run_id` via W3C Baggage headers:

```
traceparent: 00-{trace_id}-{span_id}-01
baggage: botanu.run_id=019abc12...
```

## Span Attributes

OpenAI calls produce:

```
gen_ai.operation.name: chat
gen_ai.provider.name: openai
gen_ai.request.model: gpt-4
gen_ai.usage.input_tokens: 10
gen_ai.usage.output_tokens: 25
```

Database calls produce:

```
db.system: postgresql
db.operation: SELECT
db.statement: SELECT * FROM orders WHERE id = ?
```

## Troubleshooting

### Spans Not Appearing

Ensure `enable()` is called before library imports:

```python
from botanu import enable
enable(service_name="my-service")

import requests
import openai
```

### Check Instrumentation Status

```python
from opentelemetry.instrumentation.requests import RequestsInstrumentor
print(RequestsInstrumentor().is_instrumented())
```

## See Also

- [Kubernetes Deployment](kubernetes.md) - Zero-code instrumentation at scale
- [Collector Configuration](collector.md) - Collector setup
