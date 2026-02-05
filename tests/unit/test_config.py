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
            assert config.trace_sample_rate == 1.0
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
        """OTEL_EXPORTER_OTLP_ENDPOINT gets /v1/traces appended."""
        with mock.patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"}):
            config = BotanuConfig()
            # Base endpoint gets /v1/traces appended
            assert config.otlp_endpoint == "http://collector:4318/v1/traces"

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

    def test_env_var_sample_rate(self):
        with mock.patch.dict(os.environ, {"BOTANU_TRACE_SAMPLE_RATE": "0.5"}):
            config = BotanuConfig()
            assert config.trace_sample_rate == 0.5

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
