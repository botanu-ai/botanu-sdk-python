# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for BotanuConfig."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from botanu.sdk.config import BotanuConfig, _interpolate_env_vars


class TestInterpolateEnvVars:
    """Tests for environment variable interpolation."""

    def test_interpolates_env_vars(self):
        with mock.patch.dict(os.environ, {"MY_VAR": "my_value"}):
            result = _interpolate_env_vars("endpoint: ${MY_VAR}")
            assert result == "endpoint: my_value"

    def test_preserves_unset_vars(self):
        result = _interpolate_env_vars("endpoint: ${UNSET_VAR}")
        assert result == "endpoint: ${UNSET_VAR}"

    def test_no_interpolation_needed(self):
        result = _interpolate_env_vars("endpoint: http://localhost")
        assert result == "endpoint: http://localhost"

    def test_default_value_when_unset(self):
        result = _interpolate_env_vars("endpoint: ${UNSET_VAR:-default_value}")
        assert result == "endpoint: default_value"

    def test_default_value_ignored_when_set(self):
        with mock.patch.dict(os.environ, {"MY_VAR": "actual_value"}):
            result = _interpolate_env_vars("endpoint: ${MY_VAR:-default_value}")
            assert result == "endpoint: actual_value"


class TestBotanuConfigDefaults:
    """Tests for BotanuConfig defaults."""

    def test_default_values(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            # Clear relevant env vars
            for key in ["OTEL_SERVICE_NAME", "BOTANU_ENVIRONMENT", "OTEL_EXPORTER_OTLP_ENDPOINT"]:
                os.environ.pop(key, None)

            config = BotanuConfig()

            assert config.service_name == "unknown_service"
            assert config.deployment_environment == "production"
            assert config.propagation_mode == "lean"
            assert config.auto_detect_resources is True

    def test_env_var_service_name(self):
        with mock.patch.dict(os.environ, {"OTEL_SERVICE_NAME": "my-service"}):
            config = BotanuConfig()
            assert config.service_name == "my-service"

    def test_env_var_environment(self):
        with mock.patch.dict(os.environ, {"BOTANU_ENVIRONMENT": "staging"}):
            config = BotanuConfig()
            assert config.deployment_environment == "staging"

    def test_env_var_otlp_endpoint_base(self):
        """OTEL_EXPORTER_OTLP_ENDPOINT is stored as base; bootstrap appends /v1/traces."""
        with mock.patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"}):
            config = BotanuConfig()
            # Base endpoint stored as-is; bootstrap.py appends /v1/traces
            assert config.otlp_endpoint == "http://collector:4318"

    def test_env_var_otlp_traces_endpoint_direct(self):
        """OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is used directly without appending."""
        with mock.patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces"}):
            config = BotanuConfig()
            # Direct traces endpoint is used as-is
            assert config.otlp_endpoint == "http://collector:4318/v1/traces"

    def test_explicit_values_override_env(self):
        with mock.patch.dict(os.environ, {"OTEL_SERVICE_NAME": "env-service"}):
            config = BotanuConfig(service_name="explicit-service")
            assert config.service_name == "explicit-service"

    def test_env_var_propagation_mode(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "full"}):
            config = BotanuConfig()
            assert config.propagation_mode == "full"


class TestBotanuConfigFromYaml:
    """Tests for loading config from YAML."""

    def test_from_yaml_basic(self, tmp_path):
        yaml_content = """
service:
  name: yaml-service
  environment: production
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        config = BotanuConfig.from_yaml(str(yaml_file))
        assert config.service_name == "yaml-service"
        assert config.deployment_environment == "production"

    def test_from_yaml_with_otlp(self, tmp_path):
        yaml_content = """
service:
  name: test-service
otlp:
  endpoint: http://localhost:4318
  headers:
    Authorization: Bearer token123
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        config = BotanuConfig.from_yaml(str(yaml_file))
        assert config.otlp_endpoint == "http://localhost:4318"
        assert config.otlp_headers == {"Authorization": "Bearer token123"}

    def test_from_yaml_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            BotanuConfig.from_yaml("/nonexistent/path/config.yaml")

    def test_from_yaml_empty_file(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        config = BotanuConfig.from_yaml(str(yaml_file))
        # Should use defaults
        assert config.service_name is not None

    def test_from_yaml_env_interpolation(self, tmp_path):
        yaml_content = """
service:
  name: ${TEST_SERVICE_NAME}
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        with mock.patch.dict(os.environ, {"TEST_SERVICE_NAME": "interpolated-service"}):
            config = BotanuConfig.from_yaml(str(yaml_file))
            assert config.service_name == "interpolated-service"


class TestBotanuConfigFromFileOrEnv:
    """Tests for from_file_or_env method."""

    def test_uses_env_when_no_file(self):
        with mock.patch.dict(
            os.environ,
            {"OTEL_SERVICE_NAME": "env-only-service"},
            clear=False,
        ):
            # Ensure no config files exist in current directory
            config = BotanuConfig.from_file_or_env()
            # Should use env vars
            assert config.service_name == "env-only-service"

    def test_uses_specified_path(self, tmp_path):
        yaml_content = """
service:
  name: file-service
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        config = BotanuConfig.from_file_or_env(path=str(yaml_file))
        assert config.service_name == "file-service"


class TestBotanuConfigToDict:
    """Tests for config serialization."""

    def test_to_dict(self):
        config = BotanuConfig(
            service_name="test-service",
            deployment_environment="staging",
            otlp_endpoint="http://localhost:4318",
        )
        d = config.to_dict()

        assert d["service"]["name"] == "test-service"
        assert d["service"]["environment"] == "staging"
        assert d["otlp"]["endpoint"] == "http://localhost:4318"


class TestBotanuConfigExportTuning:
    """Tests for export tuning env vars (queue, batch, timeout)."""

    def test_default_export_values(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for key in ["BOTANU_MAX_QUEUE_SIZE", "BOTANU_MAX_EXPORT_BATCH_SIZE", "BOTANU_EXPORT_TIMEOUT_MILLIS"]:
                os.environ.pop(key, None)
            config = BotanuConfig()
            assert config.max_queue_size == 65536
            assert config.max_export_batch_size == 512
            assert config.export_timeout_millis == 30000

    def test_env_var_max_queue_size(self):
        with mock.patch.dict(os.environ, {"BOTANU_MAX_QUEUE_SIZE": "131072"}):
            config = BotanuConfig()
            assert config.max_queue_size == 131072

    def test_env_var_max_export_batch_size(self):
        with mock.patch.dict(os.environ, {"BOTANU_MAX_EXPORT_BATCH_SIZE": "1024"}):
            config = BotanuConfig()
            assert config.max_export_batch_size == 1024

    def test_env_var_export_timeout_millis(self):
        with mock.patch.dict(os.environ, {"BOTANU_EXPORT_TIMEOUT_MILLIS": "60000"}):
            config = BotanuConfig()
            assert config.export_timeout_millis == 60000

    def test_invalid_queue_size_ignored(self):
        with mock.patch.dict(os.environ, {"BOTANU_MAX_QUEUE_SIZE": "not_a_number"}):
            config = BotanuConfig()
            assert config.max_queue_size == 65536

    def test_invalid_batch_size_ignored(self):
        with mock.patch.dict(os.environ, {"BOTANU_MAX_EXPORT_BATCH_SIZE": "bad"}):
            config = BotanuConfig()
            assert config.max_export_batch_size == 512

    def test_invalid_timeout_ignored(self):
        with mock.patch.dict(os.environ, {"BOTANU_EXPORT_TIMEOUT_MILLIS": "abc"}):
            config = BotanuConfig()
            assert config.export_timeout_millis == 30000


class TestBotanuConfigFromYamlExport:
    """Tests for YAML export configuration parsing."""

    def test_from_yaml_with_export_config(self, tmp_path):
        yaml_content = """
service:
  name: yaml-export-test
export:
  batch_size: 256
  queue_size: 32768
  delay_ms: 2000
  export_timeout_ms: 15000
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        config = BotanuConfig.from_yaml(str(yaml_file))
        assert config.max_export_batch_size == 256
        assert config.max_queue_size == 32768
        assert config.schedule_delay_millis == 2000
        assert config.export_timeout_millis == 15000

    def test_from_yaml_export_defaults(self, tmp_path):
        """YAML without export section uses defaults."""
        yaml_content = """
service:
  name: minimal
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        config = BotanuConfig.from_yaml(str(yaml_file))
        assert config.max_export_batch_size == 512
        assert config.max_queue_size == 65536
        assert config.export_timeout_millis == 30000


class TestBotanuConfigToDictExport:
    """Tests for to_dict roundtrip with export params."""

    def test_to_dict_includes_export_timeout(self):
        config = BotanuConfig(export_timeout_millis=45000)
        d = config.to_dict()
        assert d["export"]["export_timeout_ms"] == 45000

    def test_to_dict_roundtrip(self, tmp_path):
        """to_dict output should be loadable by _from_dict."""
        original = BotanuConfig(
            service_name="roundtrip",
            max_queue_size=4096,
            max_export_batch_size=128,
            export_timeout_millis=10000,
        )
        d = original.to_dict()
        d["auto_instrument_packages"] = original.auto_instrument_packages
        restored = BotanuConfig._from_dict(d)
        assert restored.max_queue_size == 4096
        assert restored.max_export_batch_size == 128
        assert restored.export_timeout_millis == 10000


class TestBotanuConfigPrecedence:
    """Tests for BOTANU_* > OTEL_* > default precedence."""

    def test_botanu_service_name_over_otel(self):
        with mock.patch.dict(
            os.environ,
            {
                "BOTANU_SERVICE_NAME": "botanu-svc",
                "OTEL_SERVICE_NAME": "otel-svc",
            },
        ):
            config = BotanuConfig()
            assert config.service_name == "botanu-svc"

    def test_botanu_endpoint_over_otel(self):
        with mock.patch.dict(
            os.environ,
            {
                "BOTANU_COLLECTOR_ENDPOINT": "http://botanu:4318",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4318",
            },
        ):
            config = BotanuConfig()
            assert config.otlp_endpoint == "http://botanu:4318"

    def test_botanu_environment_over_otel(self):
        with mock.patch.dict(
            os.environ,
            {
                "BOTANU_ENVIRONMENT": "staging",
                "OTEL_DEPLOYMENT_ENVIRONMENT": "production",
            },
        ):
            config = BotanuConfig()
            assert config.deployment_environment == "staging"

    def test_propagation_mode_rejects_invalid(self):
        with mock.patch.dict(os.environ, {"BOTANU_PROPAGATION_MODE": "invalid"}):
            config = BotanuConfig()
            assert config.propagation_mode == "lean"

    def test_auto_detect_resources_env_false(self):
        with mock.patch.dict(os.environ, {"BOTANU_AUTO_DETECT_RESOURCES": "false"}):
            config = BotanuConfig()
            assert config.auto_detect_resources is False

    def test_auto_detect_resources_truthy_values(self):
        for truthy in ("true", "1", "yes"):
            with mock.patch.dict(os.environ, {"BOTANU_AUTO_DETECT_RESOURCES": truthy}):
                config = BotanuConfig()
                assert config.auto_detect_resources is True


class TestBotanuConfigAutoInstrument:
    """Tests for auto-instrumentation configuration."""

    def test_default_packages(self):
        config = BotanuConfig()
        packages = config.auto_instrument_packages

        assert "requests" in packages
        assert "httpx" in packages
        assert "fastapi" in packages
        assert "openai_v2" in packages
        assert "anthropic" in packages
