# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""LLM/Model Tracking — Track AI model usage for cost attribution.

Aligned with OpenTelemetry GenAI Semantic Conventions:
https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/

Usage::

    from botanu.tracking.llm import track_llm_call, track_tool_call

    with track_llm_call(provider="openai", model="gpt-4") as tracker:
        response = openai.chat.completions.create(...)
        tracker.set_tokens(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
        tracker.set_request_id(response.id)
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from opentelemetry import metrics, trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

# =========================================================================
# OTel GenAI Semantic Convention Attribute Names
# =========================================================================


class GenAIAttributes:
    """OpenTelemetry GenAI Semantic Convention attribute names."""

    OPERATION_NAME = "gen_ai.operation.name"
    PROVIDER_NAME = "gen_ai.provider.name"
    REQUEST_MODEL = "gen_ai.request.model"
    RESPONSE_MODEL = "gen_ai.response.model"
    USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    REQUEST_TOP_P = "gen_ai.request.top_p"
    REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
    REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
    REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
    RESPONSE_ID = "gen_ai.response.id"
    RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
    TOOL_NAME = "gen_ai.tool.name"
    TOOL_CALL_ID = "gen_ai.tool.call.id"
    ERROR_TYPE = "error.type"


class BotanuAttributes:
    """Botanu-specific attributes for cost attribution."""

    PROVIDER_REQUEST_ID = "botanu.provider.request_id"
    CLIENT_REQUEST_ID = "botanu.provider.client_request_id"
    TOKENS_CACHED = "botanu.usage.cached_tokens"
    TOKENS_CACHED_READ = "botanu.usage.cache_read_tokens"
    TOKENS_CACHED_WRITE = "botanu.usage.cache_write_tokens"
    STREAMING = "botanu.request.streaming"
    CACHE_HIT = "botanu.request.cache_hit"
    ATTEMPT_NUMBER = "botanu.request.attempt"
    TOOL_SUCCESS = "botanu.tool.success"
    TOOL_ITEMS_RETURNED = "botanu.tool.items_returned"
    TOOL_BYTES_PROCESSED = "botanu.tool.bytes_processed"
    TOOL_DURATION_MS = "botanu.tool.duration_ms"
    VENDOR = "botanu.vendor"


# =========================================================================
# Provider name mapping
# =========================================================================

LLM_PROVIDERS: Dict[str, str] = {
    "openai": "openai",
    "azure_openai": "azure.openai",
    "azure-openai": "azure.openai",
    "azureopenai": "azure.openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "bedrock": "aws.bedrock",
    "aws_bedrock": "aws.bedrock",
    "amazon_bedrock": "aws.bedrock",
    "vertex": "gcp.vertex_ai",
    "vertexai": "gcp.vertex_ai",
    "vertex_ai": "gcp.vertex_ai",
    "gcp_vertex": "gcp.vertex_ai",
    "gemini": "gcp.vertex_ai",
    "google": "gcp.vertex_ai",
    "cohere": "cohere",
    "mistral": "mistral",
    "mistralai": "mistral",
    "together": "together",
    "togetherai": "together",
    "groq": "groq",
    "replicate": "replicate",
    "ollama": "ollama",
    "huggingface": "huggingface",
    "hf": "huggingface",
    "fireworks": "fireworks",
    "perplexity": "perplexity",
}


class ModelOperation:
    """GenAI operation types per OTel semconv."""

    CHAT = "chat"
    TEXT_COMPLETION = "text_completion"
    EMBEDDINGS = "embeddings"
    GENERATE_CONTENT = "generate_content"
    EXECUTE_TOOL = "execute_tool"
    CREATE_AGENT = "create_agent"
    INVOKE_AGENT = "invoke_agent"
    RERANK = "rerank"
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDIT = "image_edit"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    MODERATION = "moderation"

    # Aliases
    COMPLETION = "text_completion"
    EMBEDDING = "embeddings"
    FUNCTION_CALL = "execute_tool"
    TOOL_USE = "execute_tool"


# =========================================================================
# GenAI Metrics
# =========================================================================

_meter = metrics.get_meter("botanu.gen_ai")

_token_usage_histogram = _meter.create_histogram(
    name="gen_ai.client.token.usage",
    description="Number of input and output tokens used",
    unit="{token}",
)

_operation_duration_histogram = _meter.create_histogram(
    name="gen_ai.client.operation.duration",
    description="GenAI operation duration",
    unit="s",
)

_attempt_counter = _meter.create_counter(
    name="botanu.gen_ai.attempts",
    description="Number of request attempts (including retries)",
    unit="{attempt}",
)


def _record_token_metrics(
    provider: str,
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    error_type: Optional[str] = None,
) -> None:
    base_attrs: Dict[str, str] = {
        GenAIAttributes.OPERATION_NAME: operation,
        GenAIAttributes.PROVIDER_NAME: provider,
        GenAIAttributes.REQUEST_MODEL: model,
    }
    if error_type:
        base_attrs[GenAIAttributes.ERROR_TYPE] = error_type

    if input_tokens > 0:
        _token_usage_histogram.record(
            input_tokens,
            {**base_attrs, "gen_ai.token.type": "input"},
        )
    if output_tokens > 0:
        _token_usage_histogram.record(
            output_tokens,
            {**base_attrs, "gen_ai.token.type": "output"},
        )


def _record_duration_metric(
    provider: str,
    model: str,
    operation: str,
    duration_seconds: float,
    error_type: Optional[str] = None,
) -> None:
    attrs: Dict[str, str] = {
        GenAIAttributes.OPERATION_NAME: operation,
        GenAIAttributes.PROVIDER_NAME: provider,
        GenAIAttributes.REQUEST_MODEL: model,
    }
    if error_type:
        attrs[GenAIAttributes.ERROR_TYPE] = error_type

    _operation_duration_histogram.record(duration_seconds, attrs)


# =========================================================================
# LLM Tracker
# =========================================================================


@dataclass
class LLMTracker:
    """Context manager for tracking LLM calls with OTel GenAI semconv."""

    provider: str
    model: str
    operation: str = ModelOperation.CHAT
    span: Optional[Span] = field(default=None, repr=False)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    provider_request_id: Optional[str] = None
    client_request_id: Optional[str] = None
    response_model: Optional[str] = None
    finish_reason: Optional[str] = None
    is_streaming: bool = False
    cache_hit: bool = False
    attempt_number: int = 1
    error_type: Optional[str] = None

    def set_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> LLMTracker:
        """Set token counts from model response."""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cached_tokens = cached_tokens or cache_read_tokens
        self.cache_read_tokens = cache_read_tokens
        self.cache_write_tokens = cache_write_tokens

        if self.span:
            self.span.set_attribute(GenAIAttributes.USAGE_INPUT_TOKENS, input_tokens)
            self.span.set_attribute(GenAIAttributes.USAGE_OUTPUT_TOKENS, output_tokens)
            if self.cached_tokens > 0:
                self.span.set_attribute(BotanuAttributes.TOKENS_CACHED, self.cached_tokens)
            if cache_read_tokens > 0:
                self.span.set_attribute(BotanuAttributes.TOKENS_CACHED_READ, cache_read_tokens)
            if cache_write_tokens > 0:
                self.span.set_attribute(BotanuAttributes.TOKENS_CACHED_WRITE, cache_write_tokens)
        return self

    def set_request_id(
        self,
        provider_request_id: Optional[str] = None,
        client_request_id: Optional[str] = None,
    ) -> LLMTracker:
        """Set provider request IDs for billing reconciliation."""
        if provider_request_id:
            self.provider_request_id = provider_request_id
            if self.span:
                self.span.set_attribute(GenAIAttributes.RESPONSE_ID, provider_request_id)
                self.span.set_attribute(BotanuAttributes.PROVIDER_REQUEST_ID, provider_request_id)
        if client_request_id:
            self.client_request_id = client_request_id
            if self.span:
                self.span.set_attribute(BotanuAttributes.CLIENT_REQUEST_ID, client_request_id)
        return self

    def set_response_model(self, model: str) -> LLMTracker:
        """Set the actual model used in the response."""
        self.response_model = model
        if self.span:
            self.span.set_attribute(GenAIAttributes.RESPONSE_MODEL, model)
        return self

    def set_finish_reason(self, reason: str) -> LLMTracker:
        """Set the finish/stop reason from the response."""
        self.finish_reason = reason
        if self.span:
            self.span.set_attribute(GenAIAttributes.RESPONSE_FINISH_REASONS, [reason])
        return self

    def set_streaming(self, is_streaming: bool = True) -> LLMTracker:
        """Mark request as streaming."""
        self.is_streaming = is_streaming
        if self.span:
            self.span.set_attribute(BotanuAttributes.STREAMING, is_streaming)
        return self

    def set_cache_hit(self, cache_hit: bool = True) -> LLMTracker:
        """Mark as cache hit."""
        self.cache_hit = cache_hit
        if self.span:
            self.span.set_attribute(BotanuAttributes.CACHE_HIT, cache_hit)
        return self

    def set_attempt(self, attempt_number: int) -> LLMTracker:
        """Set the attempt number (for retry tracking)."""
        self.attempt_number = attempt_number
        if self.span:
            self.span.set_attribute(BotanuAttributes.ATTEMPT_NUMBER, attempt_number)
        return self

    def set_request_params(
        self,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
    ) -> LLMTracker:
        """Set request parameters per OTel GenAI semconv."""
        if self.span:
            if temperature is not None:
                self.span.set_attribute(GenAIAttributes.REQUEST_TEMPERATURE, temperature)
            if top_p is not None:
                self.span.set_attribute(GenAIAttributes.REQUEST_TOP_P, top_p)
            if max_tokens is not None:
                self.span.set_attribute(GenAIAttributes.REQUEST_MAX_TOKENS, max_tokens)
            if stop_sequences is not None:
                self.span.set_attribute(GenAIAttributes.REQUEST_STOP_SEQUENCES, stop_sequences)
            if frequency_penalty is not None:
                self.span.set_attribute(GenAIAttributes.REQUEST_FREQUENCY_PENALTY, frequency_penalty)
            if presence_penalty is not None:
                self.span.set_attribute(GenAIAttributes.REQUEST_PRESENCE_PENALTY, presence_penalty)
        return self

    def set_error(self, error: Exception) -> LLMTracker:
        """Record an error from the LLM call."""
        self.error_type = type(error).__name__
        if self.span:
            self.span.set_status(Status(StatusCode.ERROR, str(error)))
            self.span.set_attribute(GenAIAttributes.ERROR_TYPE, self.error_type)
            self.span.record_exception(error)
        return self

    def add_metadata(self, **kwargs: Any) -> LLMTracker:
        """Add custom metadata to the span."""
        if self.span:
            for key, value in kwargs.items():
                attr_key = key if key.startswith(("botanu.", "gen_ai.")) else f"botanu.{key}"
                self.span.set_attribute(attr_key, value)
        return self

    def _finalize(self) -> None:
        if not self.span:
            return

        duration_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        _record_token_metrics(
            provider=self.provider,
            model=self.model,
            operation=self.operation,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            error_type=self.error_type,
        )
        _record_duration_metric(
            provider=self.provider,
            model=self.model,
            operation=self.operation,
            duration_seconds=duration_seconds,
            error_type=self.error_type,
        )
        _attempt_counter.add(
            1,
            {
                GenAIAttributes.PROVIDER_NAME: self.provider,
                GenAIAttributes.REQUEST_MODEL: self.model,
                GenAIAttributes.OPERATION_NAME: self.operation,
                "status": "error" if self.error_type else "success",
            },
        )


@contextmanager
def track_llm_call(
    provider: str,
    model: str,
    operation: str = ModelOperation.CHAT,
    client_request_id: Optional[str] = None,
    **kwargs: Any,
) -> Generator[LLMTracker, None, None]:
    """Context manager for tracking LLM/model calls with OTel GenAI semconv.

    Args:
        provider: LLM provider (openai, anthropic, bedrock, vertex, …).
        model: Model name/ID (gpt-4, claude-3-opus, …).
        operation: Type of operation (chat, embeddings, text_completion, …).
        client_request_id: Optional client-generated request ID.
        **kwargs: Additional span attributes.

    Yields:
        :class:`LLMTracker` instance.
    """
    tracer = trace.get_tracer("botanu.gen_ai")
    normalized_provider = LLM_PROVIDERS.get(provider.lower(), provider.lower())
    span_name = f"{operation} {model}"

    with tracer.start_as_current_span(name=span_name, kind=SpanKind.CLIENT) as span:
        span.set_attribute(GenAIAttributes.OPERATION_NAME, operation)
        span.set_attribute(GenAIAttributes.PROVIDER_NAME, normalized_provider)
        span.set_attribute(GenAIAttributes.REQUEST_MODEL, model)
        span.set_attribute(BotanuAttributes.VENDOR, normalized_provider)

        for key, value in kwargs.items():
            attr_key = key if key.startswith(("botanu.", "gen_ai.")) else f"botanu.{key}"
            span.set_attribute(attr_key, value)

        tracker = LLMTracker(
            provider=normalized_provider,
            model=model,
            operation=operation,
            span=span,
        )
        if client_request_id:
            tracker.set_request_id(client_request_id=client_request_id)

        try:
            yield tracker
        except Exception as exc:
            tracker.set_error(exc)
            raise
        finally:
            tracker._finalize()


# =========================================================================
# Tool/Function Call Tracker
# =========================================================================

_tool_duration_histogram = _meter.create_histogram(
    name="botanu.tool.duration",
    description="Tool execution duration",
    unit="s",
)

_tool_counter = _meter.create_counter(
    name="botanu.tool.executions",
    description="Number of tool executions",
    unit="{execution}",
)


@dataclass
class ToolTracker:
    """Context manager for tracking tool/function calls."""

    tool_name: str
    tool_call_id: Optional[str] = None
    provider: Optional[str] = None
    span: Optional[Span] = field(default=None, repr=False)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    success: bool = True
    items_returned: int = 0
    bytes_processed: int = 0
    error_type: Optional[str] = None

    def set_result(
        self,
        success: bool = True,
        items_returned: int = 0,
        bytes_processed: int = 0,
    ) -> ToolTracker:
        """Set tool execution result."""
        self.success = success
        self.items_returned = items_returned
        self.bytes_processed = bytes_processed
        if self.span:
            self.span.set_attribute(BotanuAttributes.TOOL_SUCCESS, success)
            if items_returned > 0:
                self.span.set_attribute(BotanuAttributes.TOOL_ITEMS_RETURNED, items_returned)
            if bytes_processed > 0:
                self.span.set_attribute(BotanuAttributes.TOOL_BYTES_PROCESSED, bytes_processed)
        return self

    def set_tool_call_id(self, tool_call_id: str) -> ToolTracker:
        """Set the tool call ID from the LLM response."""
        self.tool_call_id = tool_call_id
        if self.span:
            self.span.set_attribute(GenAIAttributes.TOOL_CALL_ID, tool_call_id)
        return self

    def set_error(self, error: Exception) -> ToolTracker:
        """Record tool execution error."""
        self.success = False
        self.error_type = type(error).__name__
        if self.span:
            self.span.set_status(Status(StatusCode.ERROR, str(error)))
            self.span.set_attribute(GenAIAttributes.ERROR_TYPE, self.error_type)
            self.span.record_exception(error)
        return self

    def add_metadata(self, **kwargs: Any) -> ToolTracker:
        """Add custom metadata to the span."""
        if self.span:
            for key, value in kwargs.items():
                attr_key = key if key.startswith(("botanu.", "gen_ai.")) else f"botanu.tool.{key}"
                self.span.set_attribute(attr_key, value)
        return self

    def _finalize(self) -> None:
        if not self.span:
            return
        duration_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.span.set_attribute(BotanuAttributes.TOOL_DURATION_MS, duration_seconds * 1000)

        attrs: Dict[str, str] = {
            GenAIAttributes.TOOL_NAME: self.tool_name,
            "status": "error" if self.error_type else "success",
        }
        if self.provider:
            attrs[GenAIAttributes.PROVIDER_NAME] = self.provider

        _tool_duration_histogram.record(duration_seconds, attrs)
        _tool_counter.add(1, attrs)


@contextmanager
def track_tool_call(
    tool_name: str,
    tool_call_id: Optional[str] = None,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Generator[ToolTracker, None, None]:
    """Context manager for tracking tool/function calls.

    Args:
        tool_name: Name of the tool/function.
        tool_call_id: Tool call ID from the LLM response.
        provider: Tool provider if external (e.g., ``"tavily"``).
        **kwargs: Additional span attributes.

    Yields:
        :class:`ToolTracker` instance.
    """
    tracer = trace.get_tracer("botanu.gen_ai")
    span_name = f"execute_tool {tool_name}"

    with tracer.start_as_current_span(name=span_name, kind=SpanKind.INTERNAL) as span:
        span.set_attribute(GenAIAttributes.OPERATION_NAME, ModelOperation.EXECUTE_TOOL)
        span.set_attribute(GenAIAttributes.TOOL_NAME, tool_name)

        if tool_call_id:
            span.set_attribute(GenAIAttributes.TOOL_CALL_ID, tool_call_id)
        if provider:
            normalized = LLM_PROVIDERS.get(provider.lower(), provider.lower())
            span.set_attribute(GenAIAttributes.PROVIDER_NAME, normalized)
            span.set_attribute(BotanuAttributes.VENDOR, normalized)

        for key, value in kwargs.items():
            attr_key = key if key.startswith(("botanu.", "gen_ai.")) else f"botanu.tool.{key}"
            span.set_attribute(attr_key, value)

        tracker = ToolTracker(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            provider=provider,
            span=span,
        )

        try:
            yield tracker
        except Exception as exc:
            tracker.set_error(exc)
            raise
        finally:
            tracker._finalize()


# =========================================================================
# Standalone Helpers
# =========================================================================


def set_llm_attributes(
    provider: str,
    model: str,
    operation: str = ModelOperation.CHAT,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    streaming: bool = False,
    provider_request_id: Optional[str] = None,
    span: Optional[Span] = None,
) -> None:
    """Set LLM attributes on the current span using OTel GenAI semconv."""
    target_span = span or trace.get_current_span()
    if not target_span or not target_span.is_recording():
        return

    normalized_provider = LLM_PROVIDERS.get(provider.lower(), provider.lower())

    target_span.set_attribute(GenAIAttributes.OPERATION_NAME, operation)
    target_span.set_attribute(GenAIAttributes.PROVIDER_NAME, normalized_provider)
    target_span.set_attribute(GenAIAttributes.REQUEST_MODEL, model)
    target_span.set_attribute(BotanuAttributes.VENDOR, normalized_provider)

    if input_tokens > 0:
        target_span.set_attribute(GenAIAttributes.USAGE_INPUT_TOKENS, input_tokens)
    if output_tokens > 0:
        target_span.set_attribute(GenAIAttributes.USAGE_OUTPUT_TOKENS, output_tokens)
    if cached_tokens > 0:
        target_span.set_attribute(BotanuAttributes.TOKENS_CACHED, cached_tokens)
    if streaming:
        target_span.set_attribute(BotanuAttributes.STREAMING, True)
    if provider_request_id:
        target_span.set_attribute(GenAIAttributes.RESPONSE_ID, provider_request_id)
        target_span.set_attribute(BotanuAttributes.PROVIDER_REQUEST_ID, provider_request_id)

    _record_token_metrics(
        provider=normalized_provider,
        model=model,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def set_token_usage(
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    span: Optional[Span] = None,
) -> None:
    """Set token usage on the current span using OTel GenAI semconv."""
    target_span = span or trace.get_current_span()
    if not target_span or not target_span.is_recording():
        return

    target_span.set_attribute(GenAIAttributes.USAGE_INPUT_TOKENS, input_tokens)
    target_span.set_attribute(GenAIAttributes.USAGE_OUTPUT_TOKENS, output_tokens)

    if cached_tokens > 0:
        target_span.set_attribute(BotanuAttributes.TOKENS_CACHED, cached_tokens)


def llm_instrumented(
    provider: str,
    model_param: str = "model",
    tokens_from_response: bool = True,
) -> Any:
    """Decorator to auto-instrument LLM client methods.

    Args:
        provider: LLM provider name.
        model_param: Name of the parameter containing the model name.
        tokens_from_response: Whether to extract tokens from ``response.usage``.
    """

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            model = kwargs.get(model_param) or (args[1] if len(args) > 1 else "unknown")

            with track_llm_call(provider, model) as tracker:
                if kwargs.get("stream"):
                    tracker.set_streaming(True)

                response = func(*args, **kwargs)

                if tokens_from_response and hasattr(response, "usage"):
                    usage = response.usage
                    tracker.set_tokens(
                        input_tokens=getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0),
                        output_tokens=getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0),
                    )

                return response

        return wrapper

    return decorator
