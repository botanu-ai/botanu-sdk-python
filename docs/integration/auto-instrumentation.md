# Auto-Instrumentation

Automatically instrument common libraries for seamless tracing.

## Overview

Botanu leverages OpenTelemetry's auto-instrumentation ecosystem. When enabled, your HTTP clients, web frameworks, databases, and LLM providers are automatically traced without code changes.

## Enabling Auto-Instrumentation

```python
from botanu import enable

enable(
    service_name="my-service",
    auto_instrument=True,  # Default
)
```

Or with specific packages:

```python
enable(
    service_name="my-service",
    auto_instrument_packages=["requests", "fastapi", "openai_v2"],
)
```

## Supported Libraries

### HTTP Clients

| Library | Package | Notes |
|---------|---------|-------|
| requests | `opentelemetry-instrumentation-requests` | Sync HTTP |
| httpx | `opentelemetry-instrumentation-httpx` | Sync/async HTTP |
| urllib3 | `opentelemetry-instrumentation-urllib3` | Low-level HTTP |
| aiohttp | `opentelemetry-instrumentation-aiohttp-client` | Async HTTP |

### Web Frameworks

| Framework | Package | Notes |
|-----------|---------|-------|
| FastAPI | `opentelemetry-instrumentation-fastapi` | ASGI framework |
| Flask | `opentelemetry-instrumentation-flask` | WSGI framework |
| Django | `opentelemetry-instrumentation-django` | Full-stack framework |
| Starlette | `opentelemetry-instrumentation-starlette` | ASGI toolkit |

### Databases

| Database | Package | Notes |
|----------|---------|-------|
| SQLAlchemy | `opentelemetry-instrumentation-sqlalchemy` | ORM/Core |
| psycopg2 | `opentelemetry-instrumentation-psycopg2` | PostgreSQL |
| asyncpg | `opentelemetry-instrumentation-asyncpg` | Async PostgreSQL |
| pymongo | `opentelemetry-instrumentation-pymongo` | MongoDB |
| redis | `opentelemetry-instrumentation-redis` | Redis |

### Messaging

| System | Package | Notes |
|--------|---------|-------|
| Celery | `opentelemetry-instrumentation-celery` | Task queue |
| kafka-python | `opentelemetry-instrumentation-kafka-python` | Kafka client |

### GenAI / LLM Providers

| Provider | Package | Notes |
|----------|---------|-------|
| OpenAI | `opentelemetry-instrumentation-openai-v2` | ChatGPT, GPT-4 |
| Anthropic | `opentelemetry-instrumentation-anthropic` | Claude |
| Vertex AI | `opentelemetry-instrumentation-vertexai` | Google Vertex |
| Google GenAI | `opentelemetry-instrumentation-google-genai` | Gemini |
| LangChain | `opentelemetry-instrumentation-langchain` | LangChain |

### Other

| Library | Package | Notes |
|---------|---------|-------|
| gRPC | `opentelemetry-instrumentation-grpc` | RPC framework |
| logging | `opentelemetry-instrumentation-logging` | Python logging |

## Installation

Install the instrumentation packages you need:

```bash
# Full suite
pip install "botanu[instruments,genai]"

# Or individual packages
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-openai-v2
```

## How It Works

1. **At startup**, Botanu calls each instrumentor's `instrument()` method
2. **Instrumented libraries** automatically create spans for operations
3. **RunContextEnricher** adds `run_id` to every span via baggage
4. **All spans** are linked to the current run, enabling cost attribution

```python
from botanu import enable, botanu_use_case

enable(service_name="my-service")

@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id: str):
    # requests.get() automatically creates a span with run_id
    context = requests.get(f"https://api.example.com/tickets/{ticket_id}")

    # OpenAI call automatically creates a span with tokens, model, etc.
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": context.text}]
    )

    return response
```

## Context Propagation

Auto-instrumented HTTP clients automatically propagate context:

```python
@botanu_use_case("Distributed Workflow")
async def orchestrate():
    # Baggage (run_id, use_case) is injected into request headers
    response = requests.get("https://service-b.example.com/process")
    # Service B extracts baggage and continues the trace
```

Headers injected:
```
traceparent: 00-{trace_id}-{span_id}-01
baggage: botanu.run_id=019abc12...,botanu.use_case=Distributed%20Workflow
```

## Customizing Instrumentation

### Exclude Specific Endpoints

```python
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Exclude health checks from tracing
RequestsInstrumentor().instrument(
    excluded_urls=["health", "metrics"]
)
```

### Add Request/Response Hooks

```python
def request_hook(span, request):
    span.set_attribute("http.request.custom_header", request.headers.get("X-Custom"))

def response_hook(span, request, response):
    span.set_attribute("http.response.custom_header", response.headers.get("X-Custom"))

RequestsInstrumentor().instrument(
    request_hook=request_hook,
    response_hook=response_hook,
)
```

## GenAI Instrumentation Details

### OpenAI

Automatically captures:
- Model name and parameters
- Token usage (input, output, cached)
- Request/response IDs
- Streaming status
- Tool/function calls

```python
# Automatically traced
response = await openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

Span attributes:
```
gen_ai.operation.name: chat
gen_ai.provider.name: openai
gen_ai.request.model: gpt-4
gen_ai.usage.input_tokens: 10
gen_ai.usage.output_tokens: 25
```

### Anthropic

Automatically captures:
- Model and version
- Token usage with cache breakdown
- Stop reason

```python
# Automatically traced
response = await anthropic.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### LangChain

Traces the full chain execution:

```python
# Each step is traced
chain = prompt | llm | parser
result = await chain.ainvoke({"input": "Hello"})
```

## Combining with Manual Tracking

Auto-instrumentation works alongside manual tracking:

```python
from botanu import botanu_use_case, emit_outcome
from botanu.tracking.llm import track_llm_call

@botanu_use_case("Hybrid Workflow")
async def hybrid_example():
    # Auto-instrumented HTTP call
    data = requests.get("https://api.example.com/data")

    # Manual tracking for custom provider
    with track_llm_call(provider="custom-llm", model="my-model") as tracker:
        response = await custom_llm_call(data.json())
        tracker.set_tokens(input_tokens=100, output_tokens=200)

    # Auto-instrumented database call
    await database.execute("INSERT INTO results VALUES (?)", response)

    emit_outcome("success")
```

## Disabling Auto-Instrumentation

### Completely Disable

```python
enable(
    service_name="my-service",
    auto_instrument_packages=[],  # Empty list
)
```

### Disable Specific Libraries

```python
enable(
    service_name="my-service",
    auto_instrument_packages=["fastapi", "openai_v2"],  # Only these
)
```

## Troubleshooting

### Spans Not Appearing

1. Check the library is installed:
   ```bash
   pip list | grep opentelemetry-instrumentation
   ```

2. Verify instrumentation is enabled:
   ```python
   from opentelemetry.instrumentation.requests import RequestsInstrumentor
   print(RequestsInstrumentor().is_instrumented())
   ```

3. Ensure `enable()` is called before library imports:
   ```python
   from botanu import enable
   enable(service_name="my-service")

   # Import after enable()
   import requests
   ```

### Context Not Propagating

Check that baggage propagator is configured:

```python
from opentelemetry import propagate
print(propagate.get_global_textmap())
# Should include W3CBaggagePropagator
```

## See Also

- [Existing OTel Setup](existing-otel.md) - Integration with existing OTel
- [Collector Configuration](collector.md) - Collector setup
- [Context Propagation](../concepts/context-propagation.md) - How context flows
