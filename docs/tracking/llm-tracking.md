# LLM Tracking

Track AI model usage for accurate cost attribution across providers.

## Overview

Botanu provides LLM tracking that aligns with [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/). This ensures compatibility with standard observability tooling while enabling detailed cost analysis.

## Basic Usage

### Context Manager (Recommended)

```python
from botanu.tracking.llm import track_llm_call

with track_llm_call(provider="openai", model="gpt-4") as tracker:
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
    tracker.set_tokens(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
    tracker.set_request_id(response.id)
```

### What Gets Recorded

| Attribute | Example | Description |
|-----------|---------|-------------|
| `gen_ai.operation.name` | `chat` | Type of operation |
| `gen_ai.provider.name` | `openai` | Normalized provider name |
| `gen_ai.request.model` | `gpt-4` | Requested model |
| `gen_ai.response.model` | `gpt-4-0613` | Actual model used |
| `gen_ai.usage.input_tokens` | `150` | Input/prompt tokens |
| `gen_ai.usage.output_tokens` | `200` | Output/completion tokens |
| `gen_ai.response.id` | `chatcmpl-...` | Provider request ID |

## LLMTracker Methods

### set_tokens()

Record token usage from the response:

```python
tracker.set_tokens(
    input_tokens=150,
    output_tokens=200,
    cached_tokens=50,        # For providers with caching
    cache_read_tokens=50,    # Anthropic-style cache read
    cache_write_tokens=100,  # Anthropic-style cache write
)
```

### set_request_id()

Record provider and client request IDs for billing reconciliation:

```python
tracker.set_request_id(
    provider_request_id=response.id,      # From provider response
    client_request_id="my-client-123",    # Your tracking ID
)
```

### set_response_model()

When the response uses a different model than requested:

```python
tracker.set_response_model("gpt-4-0613")
```

### set_request_params()

Record request parameters for analysis:

```python
tracker.set_request_params(
    temperature=0.7,
    top_p=0.9,
    max_tokens=1000,
    stop_sequences=["END"],
    frequency_penalty=0.5,
    presence_penalty=0.3,
)
```

### set_streaming()

Mark as a streaming request:

```python
tracker.set_streaming(True)
```

### set_cache_hit()

Mark as a cache hit (for semantic caching):

```python
tracker.set_cache_hit(True)
```

### set_attempt()

Track retry attempts:

```python
tracker.set_attempt(2)  # Second attempt
```

### set_finish_reason()

Record the stop reason:

```python
tracker.set_finish_reason("stop")  # or "length", "content_filter", etc.
```

### set_error()

Record errors (automatically called on exceptions):

```python
try:
    response = await client.chat(...)
except openai.RateLimitError as e:
    tracker.set_error(e)
    raise
```

### add_metadata()

Add custom attributes:

```python
tracker.add_metadata(
    prompt_version="v2.1",
    experiment_id="exp-123",
)
```

## Operation Types

Use `ModelOperation` constants for the `operation` parameter:

```python
from botanu.tracking.llm import track_llm_call, ModelOperation

# Chat completion
with track_llm_call(provider="openai", model="gpt-4", operation=ModelOperation.CHAT):
    ...

# Embeddings
with track_llm_call(provider="openai", model="text-embedding-3-small", operation=ModelOperation.EMBEDDINGS):
    ...

# Text completion (legacy)
with track_llm_call(provider="openai", model="davinci", operation=ModelOperation.TEXT_COMPLETION):
    ...
```

Available operations:

| Constant | Value | Use Case |
|----------|-------|----------|
| `CHAT` | `chat` | Chat completions (default) |
| `TEXT_COMPLETION` | `text_completion` | Legacy completions |
| `EMBEDDINGS` | `embeddings` | Embedding generation |
| `GENERATE_CONTENT` | `generate_content` | Generic content generation |
| `EXECUTE_TOOL` | `execute_tool` | Tool/function execution |
| `CREATE_AGENT` | `create_agent` | Agent creation |
| `INVOKE_AGENT` | `invoke_agent` | Agent invocation |
| `RERANK` | `rerank` | Reranking |
| `IMAGE_GENERATION` | `image_generation` | Image generation |
| `SPEECH_TO_TEXT` | `speech_to_text` | Transcription |
| `TEXT_TO_SPEECH` | `text_to_speech` | Speech synthesis |

## Provider Normalization

Provider names are automatically normalized:

| Input | Normalized |
|-------|------------|
| `openai`, `OpenAI` | `openai` |
| `azure_openai`, `azure-openai` | `azure.openai` |
| `anthropic`, `claude` | `anthropic` |
| `bedrock`, `aws_bedrock` | `aws.bedrock` |
| `vertex`, `vertexai`, `gemini` | `gcp.vertex_ai` |
| `cohere` | `cohere` |
| `mistral`, `mistralai` | `mistral` |
| `together`, `togetherai` | `together` |
| `groq` | `groq` |

## Tool/Function Tracking

Track tool calls triggered by LLMs:

```python
from botanu.tracking.llm import track_tool_call

with track_tool_call(tool_name="search_database", tool_call_id="call_abc123") as tool:
    results = await do_work(query)
    tool.set_result(
        success=True,
        items_returned=len(results),
        bytes_processed=1024,
    )
```

### ToolTracker Methods

```python
# Set execution result
tool.set_result(
    success=True,
    items_returned=10,
    bytes_processed=2048,
)

# Set tool call ID from LLM response
tool.set_tool_call_id("call_abc123")

# Record error
tool.set_error(exception)

# Add custom metadata
tool.add_metadata(query_type="semantic")
```

## Standalone Helpers

For cases where you can't use context managers:

### set_llm_attributes()

```python
from botanu.tracking.llm import set_llm_attributes

set_llm_attributes(
    provider="openai",
    model="gpt-4",
    operation="chat",
    input_tokens=150,
    output_tokens=200,
    streaming=True,
    provider_request_id="chatcmpl-...",
)
```

### set_token_usage()

```python
from botanu.tracking.llm import set_token_usage

set_token_usage(
    input_tokens=150,
    output_tokens=200,
    cached_tokens=50,
)
```

## Decorator for Auto-Instrumentation

For wrapping existing client methods:

```python
from botanu.tracking.llm import llm_instrumented

class MyOpenAIClient:
    @llm_instrumented(provider="openai", tokens_from_response=True)
    def chat(self, model: str, messages: list):
        return openai.chat.completions.create(model=model, messages=messages)
```

## Metrics

The SDK automatically records these metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `gen_ai.client.token.usage` | Histogram | Token counts by type |
| `gen_ai.client.operation.duration` | Histogram | Operation duration in seconds |
| `botanu.gen_ai.attempts` | Counter | Request attempts (including retries) |

## Example: Multi-Provider Workflow

```python
from botanu import botanu_workflow, emit_outcome
from botanu.tracking.llm import track_llm_call

@botanu_workflow("process-with-fallback", event_id=event_id, customer_id=customer_id)
async def process_with_fallback(data: str):
    """Try one provider first, fall back to another."""

    try:
        with track_llm_call(provider="anthropic", model="claude-3-opus") as tracker:
            tracker.set_attempt(1)
            response = await do_work(data, provider="anthropic")
            tracker.set_tokens(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            emit_outcome("success", value_type="items_processed", value_amount=1)
            return response.content

    except RateLimitError:
        # Fallback to second provider
        with track_llm_call(provider="openai", model="gpt-4") as tracker:
            tracker.set_attempt(2)
            response = await do_work(data, provider="openai")
            tracker.set_tokens(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
            emit_outcome("success", value_type="items_processed", value_amount=1)
            return response.content
```

## See Also

- [Auto-Instrumentation](../integration/auto-instrumentation.md) - Automatic LLM tracking
- [Data Tracking](data-tracking.md) - Database and storage tracking
- [Outcomes](outcomes.md) - Recording business outcomes
