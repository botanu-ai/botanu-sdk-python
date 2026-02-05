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
        with track_llm_call(model="gpt-4", provider="openai") as tracker:
            tracker.set_tokens(input_tokens=100, output_tokens=50)

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        # Span name format: "{operation} {model}"
        assert spans[0].name == "chat gpt-4"

    def test_records_token_usage(self, memory_exporter):
        with track_llm_call(model="claude-3-opus", provider="anthropic") as tracker:
            tracker.set_tokens(input_tokens=500, output_tokens=200)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)

        assert attrs[GenAIAttributes.USAGE_INPUT_TOKENS] == 500
        assert attrs[GenAIAttributes.USAGE_OUTPUT_TOKENS] == 200

    def test_records_error_on_exception(self, memory_exporter):
        with pytest.raises(ValueError):
            with track_llm_call(model="gpt-4", provider="openai") as tracker:
                raise ValueError("API error")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get(GenAIAttributes.ERROR_TYPE) == "ValueError"

    def test_operation_type_attribute(self, memory_exporter):
        with track_llm_call(
            model="gpt-4",
            provider="openai",
            operation=ModelOperation.EMBEDDINGS,
        ):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.OPERATION_NAME] == "embeddings"

    def test_request_params(self, memory_exporter):
        with track_llm_call(
            model="gpt-4",
            provider="openai",
        ) as tracker:
            tracker.set_request_params(temperature=0.7, max_tokens=1000)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.REQUEST_TEMPERATURE] == 0.7
        assert attrs[GenAIAttributes.REQUEST_MAX_TOKENS] == 1000


class TestLLMTracker:
    """Tests for LLMTracker helper methods."""

    def test_set_request_id(self, memory_exporter):
        with track_llm_call(model="gpt-4", provider="openai") as tracker:
            tracker.set_request_id(provider_request_id="resp_123")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.RESPONSE_ID] == "resp_123"

    def test_set_finish_reason(self, memory_exporter):
        with track_llm_call(model="gpt-4", provider="openai") as tracker:
            tracker.set_finish_reason("stop")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # OTel converts lists to tuples for span attributes
        assert attrs[GenAIAttributes.RESPONSE_FINISH_REASONS] == ("stop",)


class TestProviderNormalization:
    """Tests for provider name normalization."""

    def test_openai_normalized(self, memory_exporter):
        with track_llm_call(model="gpt-4", provider="OpenAI"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "openai"

    def test_anthropic_normalized(self, memory_exporter):
        with track_llm_call(model="claude-3", provider="Anthropic"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "anthropic"

    def test_bedrock_normalized(self, memory_exporter):
        with track_llm_call(model="claude-v2", provider="bedrock"):
            pass

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs[GenAIAttributes.PROVIDER_NAME] == "aws.bedrock"
