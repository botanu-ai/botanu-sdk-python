# Auto-Instrumentation

Botanu automatically instruments 50+ libraries with zero code changes.

## How It Works

When you call `enable()`, the SDK detects which libraries are installed in your environment and instruments them automatically. Libraries that aren't installed are silently skipped.

```python
from botanu import enable

enable()  # auto-instruments everything that's installed
```

No configuration needed. No import order requirements. Just call `enable()` at startup.

## Supported Libraries

### LLM Providers

| Provider | Instrumentation Package |
|----------|------------------------|
| OpenAI | `opentelemetry-instrumentation-openai-v2` |
| Anthropic | `opentelemetry-instrumentation-anthropic` |
| Vertex AI | `opentelemetry-instrumentation-vertexai` |
| Google GenAI | `opentelemetry-instrumentation-google-generativeai` |
| LangChain | `opentelemetry-instrumentation-langchain` |
| Ollama | `opentelemetry-instrumentation-ollama` |
| CrewAI | `opentelemetry-instrumentation-crewai` |

### Web Frameworks

| Framework | Instrumentation Package |
|-----------|------------------------|
| FastAPI | `opentelemetry-instrumentation-fastapi` |
| Flask | `opentelemetry-instrumentation-flask` |
| Django | `opentelemetry-instrumentation-django` |
| Starlette | `opentelemetry-instrumentation-starlette` |
| Falcon | `opentelemetry-instrumentation-falcon` |
| Pyramid | `opentelemetry-instrumentation-pyramid` |
| Tornado | `opentelemetry-instrumentation-tornado` |

### HTTP Clients

| Library | Instrumentation Package |
|---------|------------------------|
| requests | `opentelemetry-instrumentation-requests` |
| httpx | `opentelemetry-instrumentation-httpx` |
| urllib3 | `opentelemetry-instrumentation-urllib3` |
| urllib | `opentelemetry-instrumentation-urllib` |
| aiohttp (client) | `opentelemetry-instrumentation-aiohttp-client` |
| aiohttp (server) | `opentelemetry-instrumentation-aiohttp-server` |

### Databases

| Database | Instrumentation Package |
|----------|------------------------|
| SQLAlchemy | `opentelemetry-instrumentation-sqlalchemy` |
| psycopg2 | `opentelemetry-instrumentation-psycopg2` |
| psycopg3 | `opentelemetry-instrumentation-psycopg` |
| asyncpg | `opentelemetry-instrumentation-asyncpg` |
| aiopg | `opentelemetry-instrumentation-aiopg` |
| pymongo | `opentelemetry-instrumentation-pymongo` |
| redis | `opentelemetry-instrumentation-redis` |
| MySQL | `opentelemetry-instrumentation-mysql` |
| mysqlclient | `opentelemetry-instrumentation-mysqlclient` |
| PyMySQL | `opentelemetry-instrumentation-pymysql` |
| SQLite3 | `opentelemetry-instrumentation-sqlite3` |
| Elasticsearch | `opentelemetry-instrumentation-elasticsearch` |
| Cassandra | `opentelemetry-instrumentation-cassandra` |
| TortoiseORM | `opentelemetry-instrumentation-tortoiseorm` |
| pymemcache | `opentelemetry-instrumentation-pymemcache` |

### Messaging & Task Queues

| System | Instrumentation Package |
|--------|------------------------|
| Celery | `opentelemetry-instrumentation-celery` |
| kafka-python | `opentelemetry-instrumentation-kafka-python` |
| confluent-kafka | `opentelemetry-instrumentation-confluent-kafka` |
| aiokafka | `opentelemetry-instrumentation-aiokafka` |
| pika (RabbitMQ) | `opentelemetry-instrumentation-pika` |
| aio-pika | `opentelemetry-instrumentation-aio-pika` |

### AWS

| Service | Instrumentation Package |
|---------|------------------------|
| botocore | `opentelemetry-instrumentation-botocore` |
| boto3 SQS | `opentelemetry-instrumentation-boto3sqs` |

### gRPC

| Component | Instrumentation Package |
|-----------|------------------------|
| gRPC Client + Server | `opentelemetry-instrumentation-grpc` |

### Runtime

| Library | Instrumentation Package |
|---------|------------------------|
| logging | `opentelemetry-instrumentation-logging` |
| threading | `opentelemetry-instrumentation-threading` |
| asyncio | `opentelemetry-instrumentation-asyncio` |

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

## See Also

- [Kubernetes Deployment](kubernetes.md) - Zero-code instrumentation at scale
- [Collector Configuration](collector.md) - Collector setup
