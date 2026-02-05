# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Configuration for Botanu SDK.

The SDK is intentionally minimal on the hot path. Heavy processing happens in
the OpenTelemetry Collector, not in the application:

- **SDK responsibility**: Generate run_id, propagate minimal context (run_id, use_case)
- **Collector responsibility**: PII redaction, vendor detection, attribute enrichment

Configuration precedence (highest to lowest):
1. Code arguments (explicit values passed to BotanuConfig)
2. Environment variables (BOTANU_*, OTEL_*)
3. YAML config file (botanu.yaml or specified path)
4. Built-in defaults
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BotanuConfig:
    """Configuration for Botanu SDK and OpenTelemetry.

    The SDK is a thin wrapper on OpenTelemetry.  PII redaction, cardinality
    limits, and vendor enrichment are handled by the OTel Collector — not here.

    Example::

        >>> config = BotanuConfig(
        ...     service_name="my-service",
        ...     otlp_endpoint="http://collector:4318/v1/traces",
        ... )

        >>> # Or load from YAML
        >>> config = BotanuConfig.from_yaml("config/botanu.yaml")
    """

    # Service identification
    service_name: Optional[str] = None
    service_version: Optional[str] = None
    service_namespace: Optional[str] = None
    deployment_environment: Optional[str] = None

    # Resource detection
    auto_detect_resources: bool = True

    # OTLP exporter configuration
    otlp_endpoint: Optional[str] = None
    otlp_headers: Optional[Dict[str, str]] = None

    # Span export configuration
    max_export_batch_size: int = 512
    max_queue_size: int = 2048
    schedule_delay_millis: int = 5000

    # Sampling (1.0 = 100% — never sample for cost attribution)
    trace_sample_rate: float = 1.0

    # Propagation mode: "lean" (run_id + use_case only) or "full" (all context)
    propagation_mode: str = "lean"

    # Auto-instrumentation packages to enable
    auto_instrument_packages: List[str] = field(
        default_factory=lambda: [
            # HTTP clients
            "requests",
            "httpx",
            "urllib3",
            "aiohttp_client",
            # Web frameworks
            "fastapi",
            "flask",
            "django",
            "starlette",
            # Databases
            "sqlalchemy",
            "psycopg2",
            "asyncpg",
            "pymongo",
            "redis",
            # Messaging
            "celery",
            "kafka_python",
            # gRPC
            "grpc",
            # GenAI / AI
            "openai_v2",
            "anthropic",
            "vertexai",
            "google_genai",
            "langchain",
            # Runtime
            "logging",
        ]
    )

    # Config file path (for tracking where config was loaded from)
    _config_file: Optional[str] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Apply environment variable defaults."""
        if self.service_name is None:
            self.service_name = os.getenv("OTEL_SERVICE_NAME", "unknown_service")

        if self.service_version is None:
            self.service_version = os.getenv("OTEL_SERVICE_VERSION")

        if self.service_namespace is None:
            self.service_namespace = os.getenv("OTEL_SERVICE_NAMESPACE")

        env_auto_detect = os.getenv("BOTANU_AUTO_DETECT_RESOURCES")
        if env_auto_detect is not None:
            self.auto_detect_resources = env_auto_detect.lower() in ("true", "1", "yes")

        if self.deployment_environment is None:
            self.deployment_environment = os.getenv(
                "OTEL_DEPLOYMENT_ENVIRONMENT",
                os.getenv("BOTANU_ENVIRONMENT", "production"),
            )

        if self.otlp_endpoint is None:
            env_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            if env_endpoint:
                self.otlp_endpoint = env_endpoint
            else:
                base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
                self.otlp_endpoint = f"{base}/v1/traces"

        env_propagation_mode = os.getenv("BOTANU_PROPAGATION_MODE")
        if env_propagation_mode and env_propagation_mode in ("lean", "full"):
            self.propagation_mode = env_propagation_mode

        env_sample_rate = os.getenv("BOTANU_TRACE_SAMPLE_RATE")
        if env_sample_rate:
            self.trace_sample_rate = float(env_sample_rate)

    # ------------------------------------------------------------------
    # YAML loading
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Optional[str] = None) -> BotanuConfig:
        """Load configuration from a YAML file.

        Supports environment variable interpolation using ``${VAR_NAME}`` syntax.

        Args:
            path: Path to YAML config file.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If YAML is malformed.
        """
        if path is None:
            raise FileNotFoundError("No config file path provided")

        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Config file not found: {resolved}")

        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as err:
            raise ImportError("PyYAML required for YAML config. Install with: pip install pyyaml") from err

        with open(resolved) as fh:
            raw_content = fh.read()

        content = _interpolate_env_vars(raw_content)

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in {resolved}: {exc}") from exc

        if data is None:
            data = {}

        return cls._from_dict(data, config_file=str(resolved))

    @classmethod
    def from_file_or_env(cls, path: Optional[str] = None) -> BotanuConfig:
        """Load config from file if exists, otherwise use environment variables.

        Search order:
        1. Explicit *path* argument
        2. ``BOTANU_CONFIG_FILE`` env var
        3. ``./botanu.yaml``
        4. ``./config/botanu.yaml``
        5. Falls back to env-only config
        """
        search_paths: List[Path] = []

        if path:
            search_paths.append(Path(path))

        env_path = os.getenv("BOTANU_CONFIG_FILE")
        if env_path:
            search_paths.append(Path(env_path))

        search_paths.extend(
            [
                Path("botanu.yaml"),
                Path("botanu.yml"),
                Path("config/botanu.yaml"),
                Path("config/botanu.yml"),
            ]
        )

        for candidate in search_paths:
            if candidate.exists():
                logger.info("Loading config from: %s", candidate)
                return cls.from_yaml(str(candidate))

        logger.debug("No config file found, using environment variables only")
        return cls()

    @classmethod
    def _from_dict(
        cls,
        data: Dict[str, Any],
        config_file: Optional[str] = None,
    ) -> BotanuConfig:
        """Create config from dictionary (parsed YAML)."""
        service = data.get("service", {})
        otlp = data.get("otlp", {})
        export = data.get("export", {})
        sampling = data.get("sampling", {})
        propagation = data.get("propagation", {})
        resource = data.get("resource", {})
        auto_packages = data.get("auto_instrument_packages")

        return cls(
            service_name=service.get("name"),
            service_version=service.get("version"),
            service_namespace=service.get("namespace"),
            deployment_environment=service.get("environment"),
            auto_detect_resources=resource.get("auto_detect", True),
            otlp_endpoint=otlp.get("endpoint"),
            otlp_headers=otlp.get("headers"),
            max_export_batch_size=export.get("batch_size", 512),
            max_queue_size=export.get("queue_size", 2048),
            schedule_delay_millis=export.get("delay_ms", 5000),
            trace_sample_rate=sampling.get("rate", 1.0),
            propagation_mode=propagation.get("mode", "lean"),
            auto_instrument_packages=(auto_packages if auto_packages else BotanuConfig().auto_instrument_packages),
            _config_file=config_file,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "service": {
                "name": self.service_name,
                "version": self.service_version,
                "namespace": self.service_namespace,
                "environment": self.deployment_environment,
            },
            "resource": {
                "auto_detect": self.auto_detect_resources,
            },
            "otlp": {
                "endpoint": self.otlp_endpoint,
                "headers": self.otlp_headers,
            },
            "export": {
                "batch_size": self.max_export_batch_size,
                "queue_size": self.max_queue_size,
                "delay_ms": self.schedule_delay_millis,
            },
            "sampling": {
                "rate": self.trace_sample_rate,
            },
            "propagation": {
                "mode": self.propagation_mode,
            },
            "auto_instrument_packages": self.auto_instrument_packages,
        }


def _interpolate_env_vars(content: str) -> str:
    """Interpolate ``${VAR_NAME}`` and ``${VAR_NAME:-default}`` in *content*."""
    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

    def _replace(match: re.Match) -> str:  # type: ignore[type-arg]
        var_name = match.group(1)
        default = match.group(2)
        value = os.getenv(var_name)
        if value is not None:
            return value
        if default is not None:
            return default
        return match.group(0)

    return pattern.sub(_replace, content)
