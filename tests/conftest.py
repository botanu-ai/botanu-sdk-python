# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures for Botanu SDK tests."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

# Module-level provider and exporter to avoid "cannot override" warnings
_provider: TracerProvider = None
_exporter: InMemorySpanExporter = None


def _get_or_create_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Get or create the global test provider."""
    global _provider, _exporter

    if _provider is None:
        _provider = TracerProvider(sampler=ALWAYS_ON)
        _exporter = InMemorySpanExporter()
        _provider.add_span_processor(SimpleSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)

    return _provider, _exporter


@pytest.fixture(autouse=True)
def reset_tracing():
    """Reset tracing state before each test."""
    _, exporter = _get_or_create_provider()
    exporter.clear()
    yield
    exporter.clear()


@pytest.fixture
def tracer_provider():
    """Get the test TracerProvider."""
    provider, _ = _get_or_create_provider()
    return provider


@pytest.fixture
def memory_exporter():
    """Get the in-memory span exporter for testing."""
    _, exporter = _get_or_create_provider()
    return exporter


@pytest.fixture
def tracer(tracer_provider):
    """Get a tracer instance."""
    return trace.get_tracer("test-tracer")
