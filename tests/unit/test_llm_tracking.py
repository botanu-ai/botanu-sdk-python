# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for LLM tracking."""

from __future__ import annotations

import pytest

from botanu.tracking.llm import (
    GenAIAttributes,
    ModelOperation,
    track_llm_call,
)


class TestTrackLLMCall:
    """Tests for track_llm_call context manager."""

    def test_creates_span_with_model_name(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_tokens(input_tokens=100, output_tokens=50)

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        # Span name format: "{operation} {model}"
        assert spans[0].name == "chat gpt-4"

    def test_records_token_usage(self, memory_exporter):
        with track_llm_call(model="claude-3-opus", vendor="anthropic") as tracker:
            tracker.set_tokens(input_tokens=500, output_tokens=200)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)

        assert attrs[GenAIAttributes.USAGE_INPUT_TOKENS] == 500
        assert attrs[GenAIAttributes.USAGE_OUTPUT_TOKENS] == 200

    def test_records_error_on_exception(self, memory_exporter):
        with pytest.raises(ValueError):
            with track_llm_call(model="gpt-4", vendor="openai") as _tracker:
                raise ValueError("API error")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get(GenAIAttributes.ERROR_TYPE) == "ValueError"

    def test_operation_type_attribute(self, memory_exporter):
        with track_llm_call(
            model="gpt-4",
            vendor="openai",
            operation=ModelOperation.EMBEDDINGS,
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.OPERATION_NAME] == "embeddings"

    def test_request_params(self, memory_exporter):
        with track_llm_call(
            model="gpt-4",
            vendor="openai",
        ) as tracker:
            tracker.set_request_params(temperature=0.7, max_tokens=1000)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.REQUEST_TEMPERATURE] == 0.7
        assert attrs[GenAIAttributes.REQUEST_MAX_TOKENS] == 1000


class TestLLMTracker:
    """Tests for LLMTracker helper methods."""

    def test_set_request_id(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_request_id(vendor_request_id="resp_123")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.RESPONSE_ID] == "resp_123"

    def test_set_finish_reason(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_finish_reason("stop")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # OTel converts lists to tuples for span attributes
        assert attrs[GenAIAttributes.RESPONSE_FINISH_REASONS] == ("stop",)


class TestVendorNormalization:
    """Tests for provider name normalization."""

    def test_openai_normalized(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="OpenAI"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "openai"

    def test_anthropic_normalized(self, memory_exporter):
        with track_llm_call(model="claude-3", vendor="Anthropic"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "anthropic"

    def test_bedrock_normalized(self, memory_exporter):
        with track_llm_call(model="claude-v2", vendor="bedrock"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "aws.bedrock"

    def test_vertex_normalized(self, memory_exporter):
        with track_llm_call(model="gemini-pro", vendor="vertex_ai"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "gcp.vertex_ai"

    def test_azure_openai_normalized(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="azure_openai"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "azure.openai"

    def test_unknown_provider_passthrough(self, memory_exporter):
        """Unknown provider names should be normalized to lowercase."""
        with track_llm_call(model="custom-model", vendor="CustomProvider"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "customprovider"


class TestLLMTrackerExtended:
    """Extended tests for LLMTracker methods."""

    def test_set_streaming(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes

        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_streaming(True)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[BotanuAttributes.STREAMING] is True

    def test_set_cache_hit(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes

        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_cache_hit(True)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[BotanuAttributes.CACHE_HIT] is True

    def test_set_attempt(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes

        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_attempt(3)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[BotanuAttributes.ATTEMPT_NUMBER] == 3

    def test_set_response_model(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_response_model("gpt-4-0125-preview")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.RESPONSE_MODEL] == "gpt-4-0125-preview"

    def test_set_tokens_with_cache(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes

        with track_llm_call(model="claude-3", vendor="anthropic") as tracker:
            tracker.set_tokens(
                input_tokens=100,
                output_tokens=50,
                cache_read_tokens=80,
                cache_write_tokens=20,
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.USAGE_INPUT_TOKENS] == 100
        assert attrs[GenAIAttributes.USAGE_OUTPUT_TOKENS] == 50
        assert attrs[BotanuAttributes.TOKENS_CACHED_READ] == 80
        assert attrs[BotanuAttributes.TOKENS_CACHED_WRITE] == 20

    def test_set_request_id_with_client_id(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes

        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_request_id(
                vendor_request_id="resp_123",
                client_request_id="client_456",
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.RESPONSE_ID] == "resp_123"
        assert attrs[BotanuAttributes.VENDOR_CLIENT_REQUEST_ID] == "client_456"

    def test_set_request_params_extended(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.set_request_params(
                temperature=0.8,
                top_p=0.95,
                max_tokens=2000,
                stop_sequences=["END", "STOP"],
                frequency_penalty=0.5,
                presence_penalty=0.3,
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.REQUEST_TEMPERATURE] == 0.8
        assert attrs[GenAIAttributes.REQUEST_TOP_P] == 0.95
        assert attrs[GenAIAttributes.REQUEST_MAX_TOKENS] == 2000
        # OTel converts lists to tuples
        assert attrs[GenAIAttributes.REQUEST_STOP_SEQUENCES] == ("END", "STOP")
        assert attrs[GenAIAttributes.REQUEST_FREQUENCY_PENALTY] == 0.5
        assert attrs[GenAIAttributes.REQUEST_PRESENCE_PENALTY] == 0.3

    def test_add_metadata(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.add_metadata(custom_field="value", another_field=123)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.custom_field"] == "value"
        assert attrs["botanu.another_field"] == 123

    def test_add_metadata_preserves_prefix(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            tracker.add_metadata(**{"botanu.explicit": "prefixed"})

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.explicit"] == "prefixed"

    def test_set_error_manually(self, memory_exporter):
        with track_llm_call(model="gpt-4", vendor="openai") as tracker:
            error = RuntimeError("Rate limit exceeded")
            tracker.set_error(error)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.ERROR_TYPE] == "RuntimeError"


class TestModelOperationConstants:
    """Tests for ModelOperation constants."""

    def test_operation_types(self):
        assert ModelOperation.CHAT == "chat"
        assert ModelOperation.TEXT_COMPLETION == "text_completion"
        assert ModelOperation.EMBEDDINGS == "embeddings"
        assert ModelOperation.GENERATE_CONTENT == "generate_content"
        assert ModelOperation.EXECUTE_TOOL == "execute_tool"
        assert ModelOperation.IMAGE_GENERATION == "image_generation"
        assert ModelOperation.SPEECH_TO_TEXT == "speech_to_text"
        assert ModelOperation.TEXT_TO_SPEECH == "text_to_speech"

    def test_operation_aliases(self):
        """Aliases should match their canonical forms."""
        assert ModelOperation.COMPLETION == ModelOperation.TEXT_COMPLETION
        assert ModelOperation.EMBEDDING == ModelOperation.EMBEDDINGS
        assert ModelOperation.FUNCTION_CALL == ModelOperation.EXECUTE_TOOL
        assert ModelOperation.TOOL_USE == ModelOperation.EXECUTE_TOOL


class TestGenAIAttributeConstants:
    """Tests for GenAIAttributes and BotanuAttributes constants."""

    def test_genai_attributes(self):
        assert GenAIAttributes.OPERATION_NAME == "gen_ai.operation.name"
        assert GenAIAttributes.PROVIDER_NAME == "gen_ai.provider.name"
        assert GenAIAttributes.REQUEST_MODEL == "gen_ai.request.model"
        assert GenAIAttributes.RESPONSE_MODEL == "gen_ai.response.model"
        assert GenAIAttributes.USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
        assert GenAIAttributes.USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"

    def test_botanu_attributes(self):
        from botanu.tracking.llm import BotanuAttributes

        assert BotanuAttributes.TOKENS_CACHED == "botanu.usage.cached_tokens"
        assert BotanuAttributes.STREAMING == "botanu.request.streaming"
        assert BotanuAttributes.CACHE_HIT == "botanu.request.cache_hit"
        assert BotanuAttributes.ATTEMPT_NUMBER == "botanu.request.attempt"
        assert BotanuAttributes.VENDOR == "botanu.vendor"


class TestTrackToolCall:
    """Tests for track_tool_call context manager."""

    def test_creates_span(self, memory_exporter):
        from botanu.tracking.llm import track_tool_call

        with track_tool_call(tool_name="search"):
            pass

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "execute_tool search"

    def test_tool_call_attributes(self, memory_exporter):
        from botanu.tracking.llm import track_tool_call

        with track_tool_call(
            tool_name="web_search",
            tool_call_id="call_abc123",
            vendor="tavily",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.TOOL_NAME] == "web_search"
        assert attrs[GenAIAttributes.TOOL_CALL_ID] == "call_abc123"
        assert attrs[GenAIAttributes.OPERATION_NAME] == "execute_tool"

    def test_tool_tracker_set_result(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes, track_tool_call

        with track_tool_call(tool_name="db_query") as tracker:
            tracker.set_result(success=True, items_returned=42, bytes_processed=8192)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[BotanuAttributes.TOOL_SUCCESS] is True
        assert attrs[BotanuAttributes.TOOL_ITEMS_RETURNED] == 42
        assert attrs[BotanuAttributes.TOOL_BYTES_PROCESSED] == 8192

    def test_tool_tracker_set_error(self, memory_exporter):
        from botanu.tracking.llm import track_tool_call

        with pytest.raises(ConnectionError):
            with track_tool_call(tool_name="api_call"):
                raise ConnectionError("Service down")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.ERROR_TYPE] == "ConnectionError"

    def test_tool_tracker_set_tool_call_id(self, memory_exporter):
        from botanu.tracking.llm import track_tool_call

        with track_tool_call(tool_name="calc") as tracker:
            tracker.set_tool_call_id("call_xyz789")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.TOOL_CALL_ID] == "call_xyz789"

    def test_tool_tracker_add_metadata(self, memory_exporter):
        from botanu.tracking.llm import track_tool_call

        with track_tool_call(tool_name="search") as tracker:
            tracker.add_metadata(query="python otel", source="web")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.tool.query"] == "python otel"
        assert attrs["botanu.tool.source"] == "web"

    def test_tool_duration_recorded(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes, track_tool_call

        with track_tool_call(tool_name="slow_tool"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert BotanuAttributes.TOOL_DURATION_MS in attrs
        assert attrs[BotanuAttributes.TOOL_DURATION_MS] >= 0


class TestStandaloneHelpers:
    """Tests for set_llm_attributes and set_token_usage."""

    def test_set_llm_attributes(self, memory_exporter):
        from opentelemetry import trace as otl_trace

        from botanu.tracking.llm import BotanuAttributes, set_llm_attributes

        tracer = otl_trace.get_tracer("test")
        with tracer.start_as_current_span("test-llm-attrs"):
            set_llm_attributes(
                vendor="openai",
                model="gpt-4",
                input_tokens=150,
                output_tokens=75,
                streaming=True,
                vendor_request_id="resp_abc",
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "openai"
        assert attrs[GenAIAttributes.REQUEST_MODEL] == "gpt-4"
        assert attrs[GenAIAttributes.USAGE_INPUT_TOKENS] == 150
        assert attrs[GenAIAttributes.USAGE_OUTPUT_TOKENS] == 75
        assert attrs[BotanuAttributes.STREAMING] is True
        assert attrs[GenAIAttributes.RESPONSE_ID] == "resp_abc"

    def test_set_llm_attributes_no_active_span(self):
        from botanu.tracking.llm import set_llm_attributes

        # Should not raise when no recording span
        set_llm_attributes(vendor="openai", model="gpt-4")

    def test_set_token_usage(self, memory_exporter):
        from opentelemetry import trace as otl_trace

        from botanu.tracking.llm import BotanuAttributes, set_token_usage

        tracer = otl_trace.get_tracer("test")
        with tracer.start_as_current_span("test-token-usage"):
            set_token_usage(input_tokens=200, output_tokens=100, cached_tokens=50)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.USAGE_INPUT_TOKENS] == 200
        assert attrs[GenAIAttributes.USAGE_OUTPUT_TOKENS] == 100
        assert attrs[BotanuAttributes.TOKENS_CACHED] == 50

    def test_set_token_usage_no_active_span(self):
        from botanu.tracking.llm import set_token_usage

        # Should not raise when no recording span
        set_token_usage(input_tokens=10, output_tokens=5)


class TestLLMInstrumentedDecorator:
    """Tests for the llm_instrumented decorator."""

    def test_decorator_creates_span(self, memory_exporter):
        from botanu.tracking.llm import llm_instrumented

        @llm_instrumented(vendor="openai")
        def fake_completion(prompt, model="gpt-4"):
            class _Usage:
                prompt_tokens = 10
                completion_tokens = 20

            class _Response:
                usage = _Usage()

            return _Response()

        result = fake_completion("Hello", model="gpt-4")
        assert result is not None

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "openai"
        assert attrs[GenAIAttributes.REQUEST_MODEL] == "gpt-4"
        assert attrs[GenAIAttributes.USAGE_INPUT_TOKENS] == 10
        assert attrs[GenAIAttributes.USAGE_OUTPUT_TOKENS] == 20

    def test_decorator_with_streaming(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes, llm_instrumented

        @llm_instrumented(vendor="anthropic")
        def fake_stream(prompt, model="claude-3", stream=False):
            return "streamed"

        fake_stream("Hi", model="claude-3", stream=True)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[BotanuAttributes.STREAMING] is True

    def test_decorator_without_usage(self, memory_exporter):
        from botanu.tracking.llm import llm_instrumented

        @llm_instrumented(vendor="custom", tokens_from_response=False)
        def no_usage_fn(prompt, model="custom-model"):
            return "done"

        no_usage_fn("test", model="custom-model")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert GenAIAttributes.USAGE_INPUT_TOKENS not in attrs


class TestClientRequestId:
    """Tests for client_request_id passthrough."""

    def test_client_request_id_on_track_llm_call(self, memory_exporter):
        from botanu.tracking.llm import BotanuAttributes

        with track_llm_call(
            model="gpt-4",
            vendor="openai",
            client_request_id="cli-req-001",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[BotanuAttributes.VENDOR_CLIENT_REQUEST_ID] == "cli-req-001"


class TestKwargsPassthrough:
    """Tests for additional kwargs passed to track_llm_call."""

    def test_custom_kwargs(self, memory_exporter):
        with track_llm_call(
            model="gpt-4",
            vendor="openai",
            deployment_id="dep-001",
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.deployment_id"] == "dep-001"
