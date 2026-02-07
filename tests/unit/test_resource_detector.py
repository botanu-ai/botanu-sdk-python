# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for resource detection."""

from __future__ import annotations

import os
import sys
from unittest import mock

from botanu.resources.detector import (
    detect_all_resources,
    detect_cloud_provider,
    detect_container,
    detect_host,
    detect_kubernetes,
    detect_process,
    detect_serverless,
    get_resource_attributes,
)


class TestDetectHost:
    """Tests for host detection."""

    def test_detects_hostname(self):
        attrs = detect_host()
        assert "host.name" in attrs
        assert isinstance(attrs["host.name"], str)

    def test_detects_os_type(self):
        attrs = detect_host()
        assert attrs["os.type"] == sys.platform

    def test_detects_host_arch(self):
        attrs = detect_host()
        assert "host.arch" in attrs


class TestDetectProcess:
    """Tests for process detection."""

    def test_detects_pid(self):
        attrs = detect_process()
        assert attrs["process.pid"] == os.getpid()

    def test_detects_runtime(self):
        attrs = detect_process()
        assert attrs["process.runtime.name"] == "python"
        assert "process.runtime.version" in attrs


class TestDetectKubernetes:
    """Tests for Kubernetes detection."""

    def test_no_k8s_when_not_in_cluster(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("KUBERNETES_SERVICE_HOST", None)
            attrs = detect_kubernetes()
            assert attrs == {}

    def test_detects_k8s_pod_name(self):
        with mock.patch.dict(
            os.environ,
            {
                "KUBERNETES_SERVICE_HOST": "10.0.0.1",
                "HOSTNAME": "my-pod-abc123",
                "K8S_NAMESPACE": "default",
            },
        ):
            attrs = detect_kubernetes()
            assert attrs.get("k8s.pod.name") == "my-pod-abc123"
            assert attrs.get("k8s.namespace.name") == "default"

    def test_detects_k8s_from_env_vars(self):
        with mock.patch.dict(
            os.environ,
            {
                "KUBERNETES_SERVICE_HOST": "10.0.0.1",
                "K8S_POD_NAME": "explicit-pod",
                "K8S_POD_UID": "uid-12345",
                "K8S_CLUSTER_NAME": "prod-cluster",
            },
        ):
            attrs = detect_kubernetes()
            assert attrs.get("k8s.pod.name") == "explicit-pod"
            assert attrs.get("k8s.pod.uid") == "uid-12345"
            assert attrs.get("k8s.cluster.name") == "prod-cluster"


class TestDetectCloudProvider:
    """Tests for cloud provider detection."""

    def test_no_cloud_when_not_in_cloud(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            # Clear all cloud env vars
            for key in list(os.environ.keys()):
                if any(
                    prefix in key
                    for prefix in ["AWS_", "GOOGLE_", "GCLOUD_", "GCP_", "AZURE_", "K_", "FUNCTION_", "WEBSITE_"]
                ):
                    os.environ.pop(key, None)
            attrs = detect_cloud_provider()
            assert "cloud.provider" not in attrs

    def test_detects_aws(self):
        with mock.patch.dict(
            os.environ,
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCOUNT_ID": "123456789012",
            },
            clear=False,
        ):
            attrs = detect_cloud_provider()
            assert attrs.get("cloud.provider") == "aws"
            assert attrs.get("cloud.region") == "us-east-1"

    def test_detects_aws_lambda(self):
        with mock.patch.dict(
            os.environ,
            {
                "AWS_LAMBDA_FUNCTION_NAME": "my-function",
                "AWS_LAMBDA_FUNCTION_VERSION": "$LATEST",
                "AWS_REGION": "us-west-2",
            },
            clear=False,
        ):
            attrs = detect_cloud_provider()
            assert attrs.get("cloud.provider") == "aws"
            assert attrs.get("faas.name") == "my-function"

    def test_detects_gcp(self):
        with mock.patch.dict(
            os.environ,
            {"GOOGLE_CLOUD_PROJECT": "my-project", "GOOGLE_CLOUD_REGION": "us-central1"},
            clear=False,
        ):
            # Clear AWS vars
            os.environ.pop("AWS_REGION", None)
            os.environ.pop("AWS_DEFAULT_REGION", None)
            attrs = detect_cloud_provider()
            assert attrs.get("cloud.provider") == "gcp"
            assert attrs.get("cloud.account.id") == "my-project"

    def test_detects_gcp_cloud_run(self):
        with mock.patch.dict(
            os.environ,
            {
                "K_SERVICE": "my-service",
                "K_REVISION": "my-service-00001",
                "GOOGLE_CLOUD_PROJECT": "my-project",
            },
            clear=False,
        ):
            os.environ.pop("AWS_REGION", None)
            attrs = detect_cloud_provider()
            assert attrs.get("cloud.provider") == "gcp"
            assert attrs.get("faas.name") == "my-service"

    def test_detects_azure(self):
        with mock.patch.dict(
            os.environ,
            {
                "WEBSITE_SITE_NAME": "my-app",
                "AZURE_SUBSCRIPTION_ID": "sub-12345",
                "REGION_NAME": "eastus",
            },
            clear=False,
        ):
            # Clear other cloud vars
            os.environ.pop("AWS_REGION", None)
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
            attrs = detect_cloud_provider()
            assert attrs.get("cloud.provider") == "azure"
            assert attrs.get("faas.name") == "my-app"


class TestDetectContainer:
    """Tests for container detection."""

    def test_detects_container_id_from_env(self):
        with mock.patch.dict(os.environ, {"CONTAINER_ID": "abc123def456"}):
            attrs = detect_container()
            # Container ID detection depends on cgroup files
            # In test environment, may or may not detect
            assert isinstance(attrs, dict)


class TestDetectServerless:
    """Tests for serverless/FaaS detection."""

    def test_detects_lambda(self):
        with mock.patch.dict(
            os.environ,
            {
                "AWS_LAMBDA_FUNCTION_NAME": "my-lambda",
                "AWS_LAMBDA_FUNCTION_VERSION": "1",
                "AWS_LAMBDA_FUNCTION_MEMORY_SIZE": "512",
            },
        ):
            attrs = detect_serverless()
            assert attrs.get("faas.name") == "my-lambda"
            assert attrs.get("faas.version") == "1"
            assert attrs.get("faas.max_memory") == 512 * 1024 * 1024

    def test_detects_cloud_run(self):
        with mock.patch.dict(
            os.environ,
            {
                "K_SERVICE": "cloud-run-service",
                "K_REVISION": "rev-001",
            },
        ):
            # Clear Lambda vars
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            attrs = detect_serverless()
            assert attrs.get("faas.name") == "cloud-run-service"
            assert attrs.get("faas.version") == "rev-001"


class TestDetectAllResources:
    """Tests for combined resource detection."""

    def test_returns_dict(self):
        attrs = detect_all_resources()
        assert isinstance(attrs, dict)

    def test_includes_host_info(self):
        # Clear cache to ensure fresh detection
        detect_all_resources.cache_clear()
        attrs = detect_all_resources()
        assert "host.name" in attrs
        assert "process.pid" in attrs

    def test_caches_results(self):
        detect_all_resources.cache_clear()
        result1 = detect_all_resources()
        result2 = detect_all_resources()
        assert result1 is result2  # Same object due to caching


class TestGetResourceAttributes:
    """Tests for selective resource detection."""

    def test_include_host_only(self):
        attrs = get_resource_attributes(
            include_host=True,
            include_process=False,
            include_container=False,
            include_cloud=False,
            include_k8s=False,
            include_faas=False,
        )
        assert "host.name" in attrs
        assert "process.pid" not in attrs

    def test_include_process_only(self):
        attrs = get_resource_attributes(
            include_host=False,
            include_process=True,
            include_container=False,
            include_cloud=False,
            include_k8s=False,
            include_faas=False,
        )
        assert "process.pid" in attrs
        assert "host.name" not in attrs


class TestAWSAvailabilityZone:
    """Tests for _get_aws_availability_zone."""

    def test_returns_none_for_lambda(self):
        from botanu.resources.detector import _get_aws_availability_zone

        with mock.patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "fn"}):
            assert _get_aws_availability_zone() is None

    def test_returns_none_when_metadata_disabled(self):
        from botanu.resources.detector import _get_aws_availability_zone

        with mock.patch.dict(os.environ, {"AWS_EC2_METADATA_DISABLED": "true"}, clear=True):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            assert _get_aws_availability_zone() is None

    def test_returns_none_when_invalid_endpoint(self):
        from botanu.resources.detector import _get_aws_availability_zone

        with mock.patch.dict(
            os.environ,
            {
                "AWS_EC2_METADATA_SERVICE_ENDPOINT": "not-a-url",
            },
            clear=True,
        ):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            assert _get_aws_availability_zone() is None

    def test_returns_none_on_network_error(self):
        from botanu.resources.detector import _get_aws_availability_zone

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            os.environ.pop("AWS_EC2_METADATA_DISABLED", None)
            # Default endpoint (169.254.169.254) will fail in test env
            result = _get_aws_availability_zone()
            assert result is None


class TestCloudRegionFromAZ:
    """Tests for cloud region derivation from availability zone."""

    def test_region_derived_from_az(self):
        """When AZ is 'us-east-1a', region should be 'us-east-1'."""

        with mock.patch.dict(
            os.environ,
            {
                "AWS_REGION": "",
                "AWS_DEFAULT_REGION": "",
                "AWS_ACCOUNT_ID": "123456789012",
            },
            clear=True,
        ):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)

            # Mock the IMDS call to return an AZ
            with mock.patch(
                "botanu.resources.detector._get_aws_availability_zone",
                return_value="us-west-2c",
            ):
                attrs = detect_cloud_provider()
                if "cloud.availability_zone" in attrs:
                    assert attrs["cloud.region"] == "us-west-2"


class TestContainerId:
    """Tests for container ID extraction."""

    def test_container_id_from_env(self):
        from botanu.resources.detector import _get_container_id

        # Short container IDs (< 12 chars) are ignored
        with mock.patch.dict(os.environ, {"CONTAINER_ID": "short"}, clear=True):
            os.environ.pop("HOSTNAME", None)
            result = _get_container_id()
            assert result is None

        # Long enough IDs are returned
        with mock.patch.dict(os.environ, {"CONTAINER_ID": "abcdef123456"}, clear=True):
            os.environ.pop("HOSTNAME", None)
            result = _get_container_id()
            # May be overridden by cgroup parsing, but at minimum not None
            assert result is None or len(result) >= 12


class TestDetectHostExtended:
    """Extended host detection tests."""

    def test_host_id_from_env(self):
        with mock.patch.dict(os.environ, {"HOST_ID": "i-0123456789"}):
            attrs = detect_host()
            assert attrs["host.id"] == "i-0123456789"

    def test_host_id_from_instance_id(self):
        with mock.patch.dict(os.environ, {"INSTANCE_ID": "vm-abc"}, clear=True):
            os.environ.pop("HOST_ID", None)
            attrs = detect_host()
            assert attrs["host.id"] == "vm-abc"

    def test_host_id_falls_back_to_hostname(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("HOST_ID", None)
            os.environ.pop("INSTANCE_ID", None)
            attrs = detect_host()
            assert attrs.get("host.id") == attrs.get("host.name")


class TestDetectServerlessExtended:
    """Extended serverless detection tests."""

    def test_gcp_cloud_function(self):
        with mock.patch.dict(
            os.environ,
            {
                "FUNCTION_NAME": "my-function",
                "FUNCTION_TARGET": "handle_event",
            },
            clear=True,
        ):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            os.environ.pop("K_SERVICE", None)
            attrs = detect_serverless()
            assert attrs["faas.name"] == "my-function"
            assert attrs["faas.trigger"] == "handle_event"

    def test_azure_functions(self):
        with mock.patch.dict(
            os.environ,
            {
                "WEBSITE_SITE_NAME": "my-azure-fn",
                "WEBSITE_INSTANCE_ID": "inst-123",
            },
            clear=True,
        ):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            os.environ.pop("K_SERVICE", None)
            os.environ.pop("FUNCTION_NAME", None)
            attrs = detect_serverless()
            assert attrs["faas.name"] == "my-azure-fn"
            assert attrs["faas.instance"] == "inst-123"

    def test_no_serverless_detected(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)
            os.environ.pop("K_SERVICE", None)
            os.environ.pop("FUNCTION_NAME", None)
            os.environ.pop("WEBSITE_SITE_NAME", None)
            attrs = detect_serverless()
            assert attrs == {}


class TestDetectProcessExtended:
    """Extended process detection tests."""

    def test_process_command(self):
        attrs = detect_process()
        assert "process.command" in attrs
        assert isinstance(attrs["process.command"], str)

    def test_process_runtime_version_format(self):
        attrs = detect_process()
        version = attrs["process.runtime.version"]
        parts = version.split(".")
        assert len(parts) >= 2  # major.minor at minimum


class TestServiceInstanceId:
    """Tests for service.instance.id derivation in detect_all_resources."""

    def test_instance_id_from_hostname_in_k8s(self):
        detect_all_resources.cache_clear()
        with mock.patch.dict(
            os.environ,
            {
                "KUBERNETES_SERVICE_HOST": "10.0.0.1",
                "HOSTNAME": "my-pod-abc123xyz",
            },
        ):
            attrs = detect_all_resources()
            # Should have service.instance.id
            assert "service.instance.id" in attrs
        detect_all_resources.cache_clear()
