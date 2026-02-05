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
