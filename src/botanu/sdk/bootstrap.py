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
    enable()  # reads OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT from env
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from botanu.sdk.config import BotanuConfig

logger = logging.getLogger(__name__)

_lock = threading.RLock()
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

    with _lock:
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

        otel_sampler_env = os.getenv("OTEL_TRACES_SAMPLER")
        if otel_sampler_env and otel_sampler_env != "always_on":
            logger.warning(
                "OTEL_TRACES_SAMPLER=%s is set but Botanu enforces ALWAYS_ON. No spans will be sampled or dropped.",
                otel_sampler_env,
            )

        logger.info(
            "Initializing Botanu SDK: service=%s, env=%s, endpoint=%s",
            cfg.service_name,
            cfg.deployment_environment,
            traces_endpoint,
        )

        try:
            from opentelemetry import trace
            from opentelemetry.baggage.propagation import W3CBaggagePropagator
            from opentelemetry.propagate import set_global_textmap
            from opentelemetry.propagators.composite import CompositePropagator
            from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        except ImportError as exc:
            logger.error("Missing opentelemetry-api. Install with: pip install botanu")
            raise ImportError("opentelemetry-api is required. Install with: pip install botanu") from exc

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import ALWAYS_ON
        except ImportError as exc:
            logger.error("Missing OTel SDK dependencies. Install with: pip install botanu")
            raise ImportError("OTel SDK and exporter required for enable(). Install with: pip install botanu") from exc

        try:
            from botanu._version import __version__
            from botanu.processors import RunContextEnricher
            from botanu.resources.detector import detect_all_resources

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

            if cfg.auto_detect_resources:
                detected = detect_all_resources()
                for key, value in detected.items():
                    if key not in resource_attrs:
                        resource_attrs[key] = value
                if detected:
                    logger.debug("Auto-detected resources: %s", list(detected.keys()))

            resource = Resource.create(resource_attrs)

            existing = trace.get_tracer_provider()
            if isinstance(existing, TracerProvider):
                provider = existing
                logger.info("Reusing existing TracerProvider — adding Botanu processors")
            else:
                provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
                trace.set_tracer_provider(provider)

            lean_mode = cfg.propagation_mode == "lean"
            provider.add_span_processor(RunContextEnricher(lean_mode=lean_mode))

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
                    export_timeout_millis=cfg.export_timeout_millis,
                )
            )

            set_global_textmap(
                CompositePropagator(
                    [
                        TraceContextTextMapPropagator(),
                        W3CBaggagePropagator(),
                    ]
                )
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

    # ── HTTP clients ──────────────────────────────────────────────
    _try_instrument(enabled, failed, "httpx", "opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor")
    _try_instrument(enabled, failed, "requests", "opentelemetry.instrumentation.requests", "RequestsInstrumentor")
    _try_instrument(enabled, failed, "urllib3", "opentelemetry.instrumentation.urllib3", "URLLib3Instrumentor")
    _try_instrument(enabled, failed, "urllib", "opentelemetry.instrumentation.urllib", "URLLibInstrumentor")
    _try_instrument(
        enabled, failed, "aiohttp_client", "opentelemetry.instrumentation.aiohttp_client", "AioHttpClientInstrumentor"
    )
    _try_instrument(
        enabled, failed, "aiohttp_server", "opentelemetry.instrumentation.aiohttp_server", "AioHttpServerInstrumentor"
    )

    # ── Web frameworks ────────────────────────────────────────────
    _try_instrument(enabled, failed, "fastapi", "opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor")
    _try_instrument(enabled, failed, "flask", "opentelemetry.instrumentation.flask", "FlaskInstrumentor")
    _try_instrument(enabled, failed, "django", "opentelemetry.instrumentation.django", "DjangoInstrumentor")
    _try_instrument(enabled, failed, "starlette", "opentelemetry.instrumentation.starlette", "StarletteInstrumentor")
    _try_instrument(enabled, failed, "falcon", "opentelemetry.instrumentation.falcon", "FalconInstrumentor")
    _try_instrument(enabled, failed, "pyramid", "opentelemetry.instrumentation.pyramid", "PyramidInstrumentor")
    _try_instrument(enabled, failed, "tornado", "opentelemetry.instrumentation.tornado", "TornadoInstrumentor")

    # ── Databases ─────────────────────────────────────────────────
    _try_instrument(enabled, failed, "sqlalchemy", "opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor")
    _try_instrument(enabled, failed, "psycopg2", "opentelemetry.instrumentation.psycopg2", "Psycopg2Instrumentor")
    _try_instrument(enabled, failed, "psycopg", "opentelemetry.instrumentation.psycopg", "PsycopgInstrumentor")
    _try_instrument(enabled, failed, "asyncpg", "opentelemetry.instrumentation.asyncpg", "AsyncPGInstrumentor")
    _try_instrument(enabled, failed, "aiopg", "opentelemetry.instrumentation.aiopg", "AiopgInstrumentor")
    _try_instrument(enabled, failed, "pymongo", "opentelemetry.instrumentation.pymongo", "PymongoInstrumentor")
    _try_instrument(enabled, failed, "redis", "opentelemetry.instrumentation.redis", "RedisInstrumentor")
    _try_instrument(enabled, failed, "mysql", "opentelemetry.instrumentation.mysql", "MySQLInstrumentor")
    _try_instrument(
        enabled, failed, "mysqlclient", "opentelemetry.instrumentation.mysqlclient", "MySQLClientInstrumentor"
    )
    _try_instrument(enabled, failed, "pymysql", "opentelemetry.instrumentation.pymysql", "PyMySQLInstrumentor")
    _try_instrument(enabled, failed, "sqlite3", "opentelemetry.instrumentation.sqlite3", "SQLite3Instrumentor")
    _try_instrument(
        enabled, failed, "elasticsearch", "opentelemetry.instrumentation.elasticsearch", "ElasticsearchInstrumentor"
    )
    _try_instrument(enabled, failed, "cassandra", "opentelemetry.instrumentation.cassandra", "CassandraInstrumentor")
    _try_instrument(
        enabled, failed, "tortoise_orm", "opentelemetry.instrumentation.tortoiseorm", "TortoiseORMInstrumentor"
    )

    # ── Caching ───────────────────────────────────────────────────
    _try_instrument(enabled, failed, "pymemcache", "opentelemetry.instrumentation.pymemcache", "PymemcacheInstrumentor")

    # ── Messaging / Task queues ───────────────────────────────────
    _try_instrument(enabled, failed, "celery", "opentelemetry.instrumentation.celery", "CeleryInstrumentor")
    _try_instrument(enabled, failed, "kafka-python", "opentelemetry.instrumentation.kafka_python", "KafkaInstrumentor")
    _try_instrument(
        enabled,
        failed,
        "confluent-kafka",
        "opentelemetry.instrumentation.confluent_kafka",
        "ConfluentKafkaInstrumentor",
    )
    _try_instrument(enabled, failed, "aiokafka", "opentelemetry.instrumentation.aiokafka", "AioKafkaInstrumentor")
    _try_instrument(enabled, failed, "pika", "opentelemetry.instrumentation.pika", "PikaInstrumentor")
    _try_instrument(enabled, failed, "aio-pika", "opentelemetry.instrumentation.aio_pika", "AioPikaInstrumentor")

    # ── AWS ───────────────────────────────────────────────────────
    _try_instrument(enabled, failed, "botocore", "opentelemetry.instrumentation.botocore", "BotocoreInstrumentor")
    _try_instrument(enabled, failed, "boto3sqs", "opentelemetry.instrumentation.boto3sqs", "Boto3SQSInstrumentor")

    # ── gRPC ──────────────────────────────────────────────────────
    _try_instrument_grpc(enabled, failed)

    # ── GenAI / AI ────────────────────────────────────────────────
    _try_instrument(enabled, failed, "openai", "opentelemetry.instrumentation.openai_v2", "OpenAIInstrumentor")
    _try_instrument(enabled, failed, "anthropic", "opentelemetry.instrumentation.anthropic", "AnthropicInstrumentor")
    _try_instrument(enabled, failed, "vertexai", "opentelemetry.instrumentation.vertexai", "VertexAIInstrumentor")
    _try_instrument(
        enabled,
        failed,
        "google_genai",
        "opentelemetry.instrumentation.google_generativeai",
        "GoogleGenerativeAIInstrumentor",
    )
    _try_instrument(enabled, failed, "langchain", "opentelemetry.instrumentation.langchain", "LangchainInstrumentor")
    _try_instrument(enabled, failed, "ollama", "opentelemetry.instrumentation.ollama", "OllamaInstrumentor")
    _try_instrument(enabled, failed, "crewai", "opentelemetry.instrumentation.crewai", "CrewAIInstrumentor")

    # ── Runtime / Concurrency ─────────────────────────────────────
    _try_instrument(enabled, failed, "logging", "opentelemetry.instrumentation.logging", "LoggingInstrumentor")
    _try_instrument(enabled, failed, "threading", "opentelemetry.instrumentation.threading", "ThreadingInstrumentor")
    _try_instrument(enabled, failed, "asyncio", "opentelemetry.instrumentation.asyncio", "AsyncioInstrumentor")

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
    global _initialized, _current_config

    with _lock:
        if not _initialized:
            return

        try:
            from opentelemetry import trace

            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush(timeout_millis=5000)
            if hasattr(provider, "shutdown"):
                provider.shutdown()

            _initialized = False
            _current_config = None
            logger.info("Botanu SDK shutdown complete")

        except Exception as exc:
            logger.error("Error during Botanu SDK shutdown: %s", exc)
