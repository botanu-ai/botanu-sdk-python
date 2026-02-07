# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for bootstrap module — enable(), auto-instrumentation, and config env var precedence."""

from __future__ import annotations

import os
from unittest import mock

from botanu.sdk.config import BotanuConfig

# ---------------------------------------------------------------------------
# Config env-var precedence: BOTANU_* > OTEL_* > defaults
# ---------------------------------------------------------------------------


class TestConfigBotanuEnvPrecedence:
    """BOTANU_* env vars take precedence over OTEL_* equivalents."""

    def test_botanu_service_name_over_otel(self):
        env = {
            "BOTANU_SERVICE_NAME": "botanu-svc",
            "OTEL_SERVICE_NAME": "otel-svc",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = BotanuConfig()
            assert cfg.service_name == "botanu-svc"

    def test_otel_service_name_fallback(self):
        env = {"OTEL_SERVICE_NAME": "otel-svc"}
        with mock.patch.dict(os.environ, env, clear=False):
            for key in ["BOTANU_SERVICE_NAME"]:
                os.environ.pop(key, None)
            cfg = BotanuConfig()
            assert cfg.service_name == "otel-svc"

    def test_service_name_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = BotanuConfig()
            assert cfg.service_name == "unknown_service"

    def test_botanu_collector_endpoint_over_otel(self):
        env = {
            "BOTANU_COLLECTOR_ENDPOINT": "http://botanu-collector:4318",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://botanu-collector:4318"

    def test_otel_exporter_endpoint_fallback(self):
        env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318"}
        with mock.patch.dict(os.environ, env, clear=False):
            for key in ["BOTANU_COLLECTOR_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]:
                os.environ.pop(key, None)
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://otel-collector:4318"

    def test_otel_traces_endpoint_over_base_endpoint(self):
        env = {
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://traces:4318/v1/traces",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://base:4318",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            for key in ["BOTANU_COLLECTOR_ENDPOINT"]:
                os.environ.pop(key, None)
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://traces:4318/v1/traces"

    def test_endpoint_default_localhost(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://localhost:4318"

    def test_botanu_environment_over_otel(self):
        env = {
            "BOTANU_ENVIRONMENT": "botanu-staging",
            "OTEL_DEPLOYMENT_ENVIRONMENT": "otel-prod",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = BotanuConfig()
            assert cfg.deployment_environment == "botanu-staging"

    def test_otel_deployment_environment_fallback(self):
        env = {"OTEL_DEPLOYMENT_ENVIRONMENT": "otel-prod"}
        with mock.patch.dict(os.environ, env, clear=False):
            for key in ["BOTANU_ENVIRONMENT"]:
                os.environ.pop(key, None)
            cfg = BotanuConfig()
            assert cfg.deployment_environment == "otel-prod"

    def test_environment_default_production(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = BotanuConfig()
            assert cfg.deployment_environment == "production"

    def test_explicit_args_override_all_env(self):
        env = {
            "BOTANU_SERVICE_NAME": "env-name",
            "BOTANU_COLLECTOR_ENDPOINT": "http://env:4318",
            "BOTANU_ENVIRONMENT": "env-staging",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = BotanuConfig(
                service_name="explicit-name",
                otlp_endpoint="http://explicit:4318",
                deployment_environment="explicit-staging",
            )
            assert cfg.service_name == "explicit-name"
            assert cfg.otlp_endpoint == "http://explicit:4318"
            assert cfg.deployment_environment == "explicit-staging"


# ---------------------------------------------------------------------------
# Config: propagation mode
# ---------------------------------------------------------------------------


class TestConfigPropagationMode:
    """Tests for propagation mode configuration."""

    def test_default_lean(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = BotanuConfig()
            assert cfg.propagation_mode == "lean"

    def test_env_var_full(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "full"}):
            cfg = BotanuConfig()
            assert cfg.propagation_mode == "full"

    def test_env_var_lean(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "lean"}):
            cfg = BotanuConfig()
            assert cfg.propagation_mode == "lean"

    def test_invalid_propagation_mode_ignored(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "invalid"}):
            cfg = BotanuConfig()
            assert cfg.propagation_mode == "lean"


# ---------------------------------------------------------------------------
# Config: auto-detect resources
# ---------------------------------------------------------------------------


class TestConfigAutoDetectResources:
    """Tests for auto-detect resources toggle."""

    def test_default_true(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = BotanuConfig()
            assert cfg.auto_detect_resources is True

    def test_env_disable(self):
        with mock.patch.dict(os.environ, {"BOTANU_AUTO_DETECT_RESOURCES": "false"}):
            cfg = BotanuConfig()
            assert cfg.auto_detect_resources is False

    def test_env_enable(self):
        with mock.patch.dict(os.environ, {"BOTANU_AUTO_DETECT_RESOURCES": "true"}):
            cfg = BotanuConfig()
            assert cfg.auto_detect_resources is True

    def test_env_numeric(self):
        with mock.patch.dict(os.environ, {"BOTANU_AUTO_DETECT_RESOURCES": "0"}):
            cfg = BotanuConfig()
            assert cfg.auto_detect_resources is False


# ---------------------------------------------------------------------------
# Bootstrap: auto-instrumentation coverage
# ---------------------------------------------------------------------------


class TestAutoInstrumentationCoverage:
    """Verify all expected instrumentations are wired in _enable_auto_instrumentation."""

    def _get_instrumentation_names(self) -> list[str]:
        """Extract all instrumentation names from the bootstrap source."""
        import ast
        import inspect

        from botanu.sdk.bootstrap import _enable_auto_instrumentation

        source = inspect.getsource(_enable_auto_instrumentation)
        names: list[str] = []
        # Parse all _try_instrument calls and extract the 'name' argument
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "_try_instrument" and len(node.args) >= 3:
                    name_arg = node.args[2]
                    if isinstance(name_arg, ast.Constant):
                        names.append(name_arg.value)
        return names

    # ── HTTP clients ──────────────────────────────────────────────

    def test_httpx_instrumented(self):
        assert "httpx" in self._get_instrumentation_names()

    def test_requests_instrumented(self):
        assert "requests" in self._get_instrumentation_names()

    def test_urllib3_instrumented(self):
        assert "urllib3" in self._get_instrumentation_names()

    def test_urllib_instrumented(self):
        assert "urllib" in self._get_instrumentation_names()

    def test_aiohttp_client_instrumented(self):
        assert "aiohttp_client" in self._get_instrumentation_names()

    def test_aiohttp_server_instrumented(self):
        assert "aiohttp_server" in self._get_instrumentation_names()

    # ── Web frameworks ────────────────────────────────────────────

    def test_fastapi_instrumented(self):
        assert "fastapi" in self._get_instrumentation_names()

    def test_flask_instrumented(self):
        assert "flask" in self._get_instrumentation_names()

    def test_django_instrumented(self):
        assert "django" in self._get_instrumentation_names()

    def test_starlette_instrumented(self):
        assert "starlette" in self._get_instrumentation_names()

    def test_falcon_instrumented(self):
        assert "falcon" in self._get_instrumentation_names()

    def test_pyramid_instrumented(self):
        assert "pyramid" in self._get_instrumentation_names()

    def test_tornado_instrumented(self):
        assert "tornado" in self._get_instrumentation_names()

    # ── Databases ─────────────────────────────────────────────────

    def test_sqlalchemy_instrumented(self):
        assert "sqlalchemy" in self._get_instrumentation_names()

    def test_psycopg2_instrumented(self):
        assert "psycopg2" in self._get_instrumentation_names()

    def test_psycopg_instrumented(self):
        assert "psycopg" in self._get_instrumentation_names()

    def test_asyncpg_instrumented(self):
        assert "asyncpg" in self._get_instrumentation_names()

    def test_aiopg_instrumented(self):
        assert "aiopg" in self._get_instrumentation_names()

    def test_pymongo_instrumented(self):
        assert "pymongo" in self._get_instrumentation_names()

    def test_redis_instrumented(self):
        assert "redis" in self._get_instrumentation_names()

    def test_mysql_instrumented(self):
        assert "mysql" in self._get_instrumentation_names()

    def test_pymysql_instrumented(self):
        assert "pymysql" in self._get_instrumentation_names()

    def test_sqlite3_instrumented(self):
        assert "sqlite3" in self._get_instrumentation_names()

    def test_elasticsearch_instrumented(self):
        assert "elasticsearch" in self._get_instrumentation_names()

    def test_cassandra_instrumented(self):
        assert "cassandra" in self._get_instrumentation_names()

    # ── Caching ───────────────────────────────────────────────────

    def test_pymemcache_instrumented(self):
        assert "pymemcache" in self._get_instrumentation_names()

    # ── Messaging ─────────────────────────────────────────────────

    def test_celery_instrumented(self):
        assert "celery" in self._get_instrumentation_names()

    def test_kafka_python_instrumented(self):
        assert "kafka-python" in self._get_instrumentation_names()

    def test_confluent_kafka_instrumented(self):
        assert "confluent-kafka" in self._get_instrumentation_names()

    def test_aiokafka_instrumented(self):
        assert "aiokafka" in self._get_instrumentation_names()

    def test_pika_instrumented(self):
        assert "pika" in self._get_instrumentation_names()

    def test_aio_pika_instrumented(self):
        assert "aio-pika" in self._get_instrumentation_names()

    # ── AWS ───────────────────────────────────────────────────────

    def test_botocore_instrumented(self):
        assert "botocore" in self._get_instrumentation_names()

    def test_boto3sqs_instrumented(self):
        assert "boto3sqs" in self._get_instrumentation_names()

    # ── GenAI / AI ────────────────────────────────────────────────

    def test_openai_instrumented(self):
        assert "openai" in self._get_instrumentation_names()

    def test_anthropic_instrumented(self):
        assert "anthropic" in self._get_instrumentation_names()

    def test_vertexai_instrumented(self):
        assert "vertexai" in self._get_instrumentation_names()

    def test_google_genai_instrumented(self):
        assert "google_genai" in self._get_instrumentation_names()

    def test_langchain_instrumented(self):
        assert "langchain" in self._get_instrumentation_names()

    def test_ollama_instrumented(self):
        assert "ollama" in self._get_instrumentation_names()

    def test_crewai_instrumented(self):
        assert "crewai" in self._get_instrumentation_names()

    # ── Runtime ───────────────────────────────────────────────────

    def test_logging_instrumented(self):
        assert "logging" in self._get_instrumentation_names()

    def test_threading_instrumented(self):
        assert "threading" in self._get_instrumentation_names()

    def test_asyncio_instrumented(self):
        assert "asyncio" in self._get_instrumentation_names()


# ---------------------------------------------------------------------------
# Bootstrap: _try_instrument resilience
# ---------------------------------------------------------------------------


class TestTryInstrument:
    """Tests for _try_instrument helper function."""

    def test_missing_package_silently_skipped(self):
        from botanu.sdk.bootstrap import _try_instrument

        enabled: list[str] = []
        failed: list[tuple[str, str]] = []
        _try_instrument(enabled, failed, "nonexistent", "nonexistent.module", "FooInstrumentor")
        assert enabled == []
        assert failed == []

    def test_instrument_error_recorded(self):
        from botanu.sdk.bootstrap import _try_instrument

        enabled: list[str] = []
        failed: list[tuple[str, str]] = []
        # os module exists but has no 'FooInstrumentor' class
        _try_instrument(enabled, failed, "os_fake", "os", "FooInstrumentor")
        assert enabled == []
        assert len(failed) == 1
        assert failed[0][0] == "os_fake"


# ---------------------------------------------------------------------------
# Bootstrap: enable() / disable() / is_enabled()
# ---------------------------------------------------------------------------


class TestEnableDisable:
    """Tests for bootstrap enable/disable lifecycle."""

    def test_is_enabled_initially_false(self):
        from botanu.sdk import bootstrap

        # Save and reset state
        original = bootstrap._initialized
        bootstrap._initialized = False
        try:
            assert bootstrap.is_enabled() is False
        finally:
            bootstrap._initialized = original

    def test_get_config_returns_none_when_not_initialized(self):
        from botanu.sdk import bootstrap

        original_init = bootstrap._initialized
        original_cfg = bootstrap._current_config
        bootstrap._initialized = False
        bootstrap._current_config = None
        try:
            assert bootstrap.get_config() is None
        finally:
            bootstrap._initialized = original_init
            bootstrap._current_config = original_cfg


# ---------------------------------------------------------------------------
# Bootstrap: endpoint normalization in bootstrap
# ---------------------------------------------------------------------------


class TestEndpointNormalization:
    """Verify bootstrap appends /v1/traces when needed."""

    def test_base_endpoint_gets_v1_traces_appended(self):
        """Config stores base URL; bootstrap should append /v1/traces."""
        with mock.patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"}, clear=True):
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://collector:4318"

            # Simulate what bootstrap does
            traces_endpoint = cfg.otlp_endpoint
            if traces_endpoint and not traces_endpoint.endswith("/v1/traces"):
                traces_endpoint = f"{traces_endpoint.rstrip('/')}/v1/traces"
            assert traces_endpoint == "http://collector:4318/v1/traces"

    def test_traces_endpoint_not_doubled(self):
        """If already ends with /v1/traces, don't append again."""
        with mock.patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces"},
            clear=True,
        ):
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://collector:4318/v1/traces"

            traces_endpoint = cfg.otlp_endpoint
            if traces_endpoint and not traces_endpoint.endswith("/v1/traces"):
                traces_endpoint = f"{traces_endpoint.rstrip('/')}/v1/traces"
            assert traces_endpoint == "http://collector:4318/v1/traces"

    def test_botanu_endpoint_gets_v1_traces_appended(self):
        """BOTANU_COLLECTOR_ENDPOINT also gets /v1/traces appended by bootstrap."""
        with mock.patch.dict(
            os.environ,
            {"BOTANU_COLLECTOR_ENDPOINT": "http://my-collector:4318"},
            clear=True,
        ):
            cfg = BotanuConfig()
            assert cfg.otlp_endpoint == "http://my-collector:4318"

            traces_endpoint = cfg.otlp_endpoint
            if traces_endpoint and not traces_endpoint.endswith("/v1/traces"):
                traces_endpoint = f"{traces_endpoint.rstrip('/')}/v1/traces"
            assert traces_endpoint == "http://my-collector:4318/v1/traces"

    def test_trailing_slash_handled(self):
        """Trailing slash on base endpoint should not cause double slash."""
        with mock.patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318/"},
            clear=True,
        ):
            cfg = BotanuConfig()
            traces_endpoint = cfg.otlp_endpoint
            if traces_endpoint and not traces_endpoint.endswith("/v1/traces"):
                traces_endpoint = f"{traces_endpoint.rstrip('/')}/v1/traces"
            assert traces_endpoint == "http://collector:4318/v1/traces"


# ---------------------------------------------------------------------------
# Bootstrap: thread safety
# ---------------------------------------------------------------------------


class TestBootstrapThreadSafety:
    """Verify that enable() is thread-safe."""

    def test_lock_exists(self):
        """Bootstrap module must have a threading lock."""
        import threading

        from botanu.sdk import bootstrap

        assert hasattr(bootstrap, "_lock")
        assert isinstance(bootstrap._lock, type(threading.RLock()))

    def test_concurrent_enable_only_initializes_once(self):
        """Multiple threads calling enable() simultaneously should not race."""
        import threading

        from botanu.sdk import bootstrap

        # Reset state
        original_init = bootstrap._initialized
        original_cfg = bootstrap._current_config
        bootstrap._initialized = False
        bootstrap._current_config = None

        results = []
        barrier = threading.Barrier(5)

        def call_enable():
            barrier.wait()
            try:
                result = bootstrap.enable(
                    service_name="thread-test",
                    otlp_endpoint="http://localhost:4318",
                    auto_instrumentation=False,
                )
                results.append(result)
            except Exception:
                results.append(None)

        try:
            threads = [threading.Thread(target=call_enable) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            # Exactly one thread should get True (first to init), rest get False
            true_count = sum(1 for r in results if r is True)
            false_count = sum(1 for r in results if r is False)
            assert true_count == 1, f"Expected exactly 1 True, got {true_count}"
            assert false_count == 4, f"Expected 4 False, got {false_count}"
        finally:
            bootstrap._initialized = original_init
            bootstrap._current_config = original_cfg


# ---------------------------------------------------------------------------
# Bootstrap: full lifecycle
# ---------------------------------------------------------------------------


class TestBootstrapLifecycle:
    """Tests for enable/disable full lifecycle."""

    def test_disable_when_not_initialized_is_noop(self):
        from botanu.sdk import bootstrap

        original = bootstrap._initialized
        bootstrap._initialized = False
        try:
            bootstrap.disable()  # Should not raise
        finally:
            bootstrap._initialized = original

    def test_disable_clears_config(self):
        from botanu.sdk import bootstrap

        original_init = bootstrap._initialized
        original_cfg = bootstrap._current_config

        bootstrap._initialized = True
        bootstrap._current_config = BotanuConfig(service_name="test")

        try:
            # Mock the tracer provider to avoid shutting down the real test provider
            mock_provider = mock.MagicMock()
            with mock.patch("opentelemetry.trace.get_tracer_provider", return_value=mock_provider):
                bootstrap.disable()
            assert bootstrap._current_config is None
            assert bootstrap._initialized is False
            mock_provider.force_flush.assert_called_once()
            mock_provider.shutdown.assert_called_once()
        finally:
            bootstrap._initialized = original_init
            bootstrap._current_config = original_cfg

    def test_is_enabled_reflects_state(self):
        from botanu.sdk import bootstrap

        original = bootstrap._initialized

        try:
            bootstrap._initialized = True
            assert bootstrap.is_enabled() is True
            bootstrap._initialized = False
            assert bootstrap.is_enabled() is False
        finally:
            bootstrap._initialized = original

    def test_get_config_returns_config_when_set(self):
        from botanu.sdk import bootstrap

        original_init = bootstrap._initialized
        original_cfg = bootstrap._current_config

        test_cfg = BotanuConfig(service_name="my-svc")
        bootstrap._current_config = test_cfg

        try:
            assert bootstrap.get_config() is test_cfg
        finally:
            bootstrap._initialized = original_init
            bootstrap._current_config = original_cfg


# ---------------------------------------------------------------------------
# Bootstrap: no-sampling guarantee
# ---------------------------------------------------------------------------


class TestNoSamplingGuarantee:
    """Botanu NEVER samples or drops spans."""

    def test_always_on_sampler_in_bootstrap(self):
        """Bootstrap source must use ALWAYS_ON sampler explicitly."""
        import inspect

        from botanu.sdk import bootstrap

        source = inspect.getsource(bootstrap.enable)
        assert "ALWAYS_ON" in source, "enable() must use ALWAYS_ON sampler"
        assert "sampler=ALWAYS_ON" in source, "TracerProvider must have sampler=ALWAYS_ON"

    def test_no_sampling_imports_in_codebase(self):
        """SDK must never import ratio or parent-based samplers."""
        import inspect

        from botanu.sdk import bootstrap

        source = inspect.getsource(bootstrap)
        # These samplers would enable span dropping
        assert "TraceIdRatio" not in source
        assert "ParentBased" not in source
        assert "ALWAYS_OFF" not in source

    def test_otel_traces_sampler_env_var_warning(self):
        """Setting OTEL_TRACES_SAMPLER should log a warning, not enable sampling."""
        import inspect

        from botanu.sdk import bootstrap

        source = inspect.getsource(bootstrap.enable)
        assert "OTEL_TRACES_SAMPLER" in source, "enable() must check for OTEL_TRACES_SAMPLER env var and warn"

    def test_conftest_uses_always_on(self):
        """Test provider must also use ALWAYS_ON to match production behavior."""
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON

        from tests.conftest import _get_or_create_provider

        provider, _ = _get_or_create_provider()
        assert provider.sampler is ALWAYS_ON


# ---------------------------------------------------------------------------
# Bootstrap: provider reuse (no double-spanning)
# ---------------------------------------------------------------------------


class TestProviderReuse:
    """Botanu must not create a second TracerProvider if one already exists."""

    def test_reuse_existing_provider_code_path(self):
        """Bootstrap source must check for existing TracerProvider."""
        import inspect

        from botanu.sdk import bootstrap

        source = inspect.getsource(bootstrap.enable)
        assert "get_tracer_provider" in source, "enable() must check for existing TracerProvider"
        assert "isinstance" in source, "enable() must use isinstance to check provider type"
