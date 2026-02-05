# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Botanu Bootstrap — one-switch enablement for OTEL auto-instrumentation.

This is the "Botanu OTel Distribution" — a curated bundle that:

1. Configures OTEL SDK with OTLP exporter
2. Enables OTEL auto-instrumentation for popular libraries
3. Adds :class:`~botanu.processors.enricher.RunContextEnricher`
   (propagates ``run_id`` to all spans)
4. Sets up W3C TraceContext + Baggage propagators

Usage::

    from botanu import enable
    enable(service_name="my-app", otlp_endpoint="http://collector:4318")
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from botanu.sdk.config import BotanuConfig

logger = logging.getLogger(__name__)

_initialized = False
_current_config: Optional[BotanuConfig] = None


def enable(
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    environment: Optional[str] = None,
    auto_instrumentation: bool = True,
    propagators: Optional[List[str]] = None,
    log_level: str = "INFO",
    config: Optional[BotanuConfig] = None,
    config_file: Optional[str] = None,
) -> bool:
    """Enable Botanu SDK with OTEL auto-instrumentation.

    This is the ONE function customers need to call to get full observability.

    Args:
        service_name: Service name.
        otlp_endpoint: OTLP collector endpoint.
        environment: Deployment environment.
        auto_instrumentation: Enable OTEL auto-instrumentation (default: ``True``).
        propagators: List of propagators (default: ``["tracecontext", "baggage"]``).
        log_level: Logging level (default: ``"INFO"``).
        config: Full :class:`BotanuConfig` (overrides individual params).
        config_file: Path to YAML config file.

    Returns:
        ``True`` if successfully initialized, ``False`` if already initialized.
    """
    global _initialized, _current_config

    if _initialized:
        logger.warning("Botanu SDK already initialized")
        return False

    logging.basicConfig(level=getattr(logging, log_level.upper()))

    from botanu.sdk.config import BotanuConfig as ConfigClass

    if config is not None:
        cfg = config
    elif config_file is not None:
        cfg = ConfigClass.from_yaml(config_file)
    else:
        cfg = ConfigClass.from_file_or_env()

    if service_name is not None:
        cfg.service_name = service_name
    if otlp_endpoint is not None:
        cfg.otlp_endpoint = otlp_endpoint
    if environment is not None:
        cfg.deployment_environment = environment

    _current_config = cfg

    traces_endpoint = cfg.otlp_endpoint
    if traces_endpoint and not traces_endpoint.endswith("/v1/traces"):
        traces_endpoint = f"{traces_endpoint.rstrip('/')}/v1/traces"

    logger.info(
        "Initializing Botanu SDK: service=%s, env=%s, endpoint=%s",
        cfg.service_name,
        cfg.deployment_environment,
        traces_endpoint,
    )

    try:
        from opentelemetry import trace
        from opentelemetry.baggage.propagation import W3CBaggagePropagator
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        from botanu._version import __version__
        from botanu.processors import RunContextEnricher
        from botanu.resources.detector import detect_all_resources

        # Build resource attributes
        resource_attrs = {
            "service.name": cfg.service_name,
            "deployment.environment": cfg.deployment_environment,
            "telemetry.sdk.name": "botanu",
            "telemetry.sdk.version": __version__,
        }
        if cfg.service_version:
            resource_attrs["service.version"] = cfg.service_version
        if cfg.service_namespace:
            resource_attrs["service.namespace"] = cfg.service_namespace

        # Auto-detect resources (K8s, cloud, host, container, FaaS)
        if cfg.auto_detect_resources:
            detected = detect_all_resources()
            for key, value in detected.items():
                if key not in resource_attrs:
                    resource_attrs[key] = value
            if detected:
                logger.debug("Auto-detected resources: %s", list(detected.keys()))

        resource = Resource.create(resource_attrs)
        provider = TracerProvider(resource=resource)

        # RunContextEnricher — the ONLY processor in SDK.
        # Reads run_id from baggage, stamps on all spans.
        lean_mode = cfg.propagation_mode == "lean"
        provider.add_span_processor(RunContextEnricher(lean_mode=lean_mode))

        # OTLP exporter
        exporter = OTLPSpanExporter(
            endpoint=traces_endpoint,
            headers=cfg.otlp_headers or {},
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                max_export_batch_size=cfg.max_export_batch_size,
                max_queue_size=cfg.max_queue_size,
                schedule_delay_millis=cfg.schedule_delay_millis,
            )
        )

        trace.set_tracer_provider(provider)

        # Propagators (W3C TraceContext + Baggage)
        set_global_textmap(
            CompositePropagator([
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ])
        )

        logger.info("Botanu SDK tracing initialized")

        if auto_instrumentation:
            _enable_auto_instrumentation()

        _initialized = True
        return True

    except Exception as exc:
        logger.error("Failed to initialize Botanu SDK: %s", exc, exc_info=True)
        return False


def _enable_auto_instrumentation() -> None:
    """Enable OTEL auto-instrumentation for common libraries.

    Each instrumentation is optional — if the underlying library or
    instrumentation package isn't installed, it is silently skipped.
    """
    enabled: List[str] = []
    failed: List[tuple[str, str]] = []

    # HTTP clients
    _try_instrument(enabled, failed, "httpx", "opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentation")
    _try_instrument(enabled, failed, "requests", "opentelemetry.instrumentation.requests", "RequestsInstrumentor")
    _try_instrument(enabled, failed, "urllib3", "opentelemetry.instrumentation.urllib3", "URLLib3Instrumentor")
    _try_instrument(enabled, failed, "aiohttp", "opentelemetry.instrumentation.aiohttp_client", "AioHttpClientInstrumentor")

    # Web frameworks
    _try_instrument(enabled, failed, "fastapi", "opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor")
    _try_instrument(enabled, failed, "flask", "opentelemetry.instrumentation.flask", "FlaskInstrumentor")
    _try_instrument(enabled, failed, "django", "opentelemetry.instrumentation.django", "DjangoInstrumentor")
    _try_instrument(enabled, failed, "starlette", "opentelemetry.instrumentation.starlette", "StarletteInstrumentor")

    # Databases
    _try_instrument(enabled, failed, "sqlalchemy", "opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor")
    _try_instrument(enabled, failed, "psycopg2", "opentelemetry.instrumentation.psycopg2", "Psycopg2Instrumentor")
    _try_instrument(enabled, failed, "asyncpg", "opentelemetry.instrumentation.asyncpg", "AsyncPGInstrumentor")
    _try_instrument(enabled, failed, "pymongo", "opentelemetry.instrumentation.pymongo", "PymongoInstrumentor")
    _try_instrument(enabled, failed, "redis", "opentelemetry.instrumentation.redis", "RedisInstrumentor")

    # Messaging
    _try_instrument(enabled, failed, "celery", "opentelemetry.instrumentation.celery", "CeleryInstrumentor")
    _try_instrument(enabled, failed, "kafka", "opentelemetry.instrumentation.kafka", "KafkaInstrumentor")

    # gRPC
    _try_instrument_grpc(enabled, failed)

    # GenAI / AI
    _try_instrument(enabled, failed, "openai", "opentelemetry.instrumentation.openai_v2", "OpenAIInstrumentor")
    _try_instrument(enabled, failed, "anthropic", "opentelemetry.instrumentation.anthropic", "AnthropicInstrumentor")
    _try_instrument(enabled, failed, "vertexai", "opentelemetry.instrumentation.vertexai", "VertexAIInstrumentor")
    _try_instrument(enabled, failed, "google_genai", "opentelemetry.instrumentation.google_genai", "GoogleGenAiInstrumentor")
    _try_instrument(enabled, failed, "langchain", "opentelemetry.instrumentation.langchain", "LangchainInstrumentor")

    # Runtime
    _try_instrument(enabled, failed, "logging", "opentelemetry.instrumentation.logging", "LoggingInstrumentor")

    if enabled:
        logger.info("Auto-instrumentation enabled: %s", ", ".join(enabled))
    if failed:
        for name, error in failed:
            logger.warning("Auto-instrumentation failed for %s: %s", name, error)


def _try_instrument(
    enabled: List[str],
    failed: List[tuple[str, str]],
    name: str,
    module_path: str,
    class_name: str,
) -> None:
    """Try to import and instrument a single library."""
    try:
        import importlib

        mod = importlib.import_module(module_path)
        instrumentor_cls = getattr(mod, class_name)
        instrumentor_cls().instrument()
        enabled.append(name)
    except ImportError:
        pass
    except Exception as exc:
        failed.append((name, str(exc)))


def _try_instrument_grpc(
    enabled: List[str],
    failed: List[tuple[str, str]],
) -> None:
    """Try to instrument gRPC (client + server)."""
    try:
        from opentelemetry.instrumentation.grpc import (
            GrpcInstrumentorClient,
            GrpcInstrumentorServer,
        )

        GrpcInstrumentorClient().instrument()
        GrpcInstrumentorServer().instrument()
        enabled.append("grpc")
    except ImportError:
        pass
    except Exception as exc:
        failed.append(("grpc", str(exc)))


def is_enabled() -> bool:
    """Check if Botanu SDK is initialized."""
    return _initialized


def get_config() -> Optional[BotanuConfig]:
    """Get the current Botanu configuration."""
    return _current_config


def disable() -> None:
    """Disable Botanu SDK and shutdown OTEL.

    Call on application shutdown for clean exit.
    """
    global _initialized

    if not _initialized:
        return

    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()

        _initialized = False
        logger.info("Botanu SDK shutdown complete")

    except Exception as exc:
        logger.error("Error during Botanu SDK shutdown: %s", exc)
