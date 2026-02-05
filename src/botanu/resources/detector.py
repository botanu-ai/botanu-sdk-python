# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Resource Detector — auto-detect execution environment for cost attribution.

Detects attributes from:
- Kubernetes (``k8s.*``)
- Cloud providers (``cloud.*``, ``aws.*``, ``gcp.*``, ``azure.*``)
- Host / VM (``host.*``, ``os.*``)
- Container (``container.*``)
- Serverless / FaaS (``faas.*``)
- Process (``process.*``)
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from functools import lru_cache
from typing import Any, Dict, Optional


# =========================================================================
# Environment Variable Mappings
# =========================================================================

K8S_ENV_MAPPINGS: Dict[str, Optional[str]] = {
    "KUBERNETES_SERVICE_HOST": None,
    "HOSTNAME": "k8s.pod.name",
    "K8S_POD_NAME": "k8s.pod.name",
    "K8S_POD_UID": "k8s.pod.uid",
    "K8S_NAMESPACE": "k8s.namespace.name",
    "K8S_NODE_NAME": "k8s.node.name",
    "K8S_CLUSTER_NAME": "k8s.cluster.name",
    "K8S_DEPLOYMENT_NAME": "k8s.deployment.name",
    "K8S_STATEFULSET_NAME": "k8s.statefulset.name",
    "K8S_CONTAINER_NAME": "k8s.container.name",
}

AWS_ENV_MAPPINGS: Dict[str, Optional[str]] = {
    "AWS_REGION": "cloud.region",
    "AWS_DEFAULT_REGION": "cloud.region",
    "AWS_ACCOUNT_ID": "cloud.account.id",
    "ECS_CONTAINER_METADATA_URI": None,
    "ECS_CLUSTER": "aws.ecs.cluster.name",
    "ECS_TASK_ARN": "aws.ecs.task.arn",
    "ECS_TASK_DEFINITION_FAMILY": "aws.ecs.task.family",
    "AWS_LAMBDA_FUNCTION_NAME": "faas.name",
    "AWS_LAMBDA_FUNCTION_VERSION": "faas.version",
    "AWS_LAMBDA_LOG_GROUP_NAME": "aws.lambda.log_group",
    "AWS_LAMBDA_FUNCTION_MEMORY_SIZE": "faas.max_memory",
}

GCP_ENV_MAPPINGS: Dict[str, Optional[str]] = {
    "GOOGLE_CLOUD_PROJECT": "cloud.account.id",
    "GCLOUD_PROJECT": "cloud.account.id",
    "GCP_PROJECT": "cloud.account.id",
    "GOOGLE_CLOUD_REGION": "cloud.region",
    "K_SERVICE": "faas.name",
    "K_REVISION": "faas.version",
    "K_CONFIGURATION": "gcp.cloud_run.configuration",
    "FUNCTION_NAME": "faas.name",
    "FUNCTION_TARGET": "faas.trigger",
    "FUNCTION_SIGNATURE_TYPE": "gcp.function.signature_type",
}

AZURE_ENV_MAPPINGS: Dict[str, Optional[str]] = {
    "AZURE_SUBSCRIPTION_ID": "cloud.account.id",
    "AZURE_RESOURCE_GROUP": "azure.resource_group",
    "WEBSITE_SITE_NAME": "faas.name",
    "FUNCTIONS_EXTENSION_VERSION": "azure.functions.version",
    "WEBSITE_INSTANCE_ID": "faas.instance",
    "REGION_NAME": "cloud.region",
}


# =========================================================================
# Detection Functions
# =========================================================================


def detect_kubernetes() -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    if not os.environ.get("KUBERNETES_SERVICE_HOST"):
        return attrs

    for env_var, attr_name in K8S_ENV_MAPPINGS.items():
        value = os.environ.get(env_var)
        if attr_name and value:
            attrs[attr_name] = value

    if "k8s.pod.name" not in attrs:
        hostname = os.environ.get("HOSTNAME", socket.gethostname())
        if hostname:
            attrs["k8s.pod.name"] = hostname

    namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    if "k8s.namespace.name" not in attrs and os.path.exists(namespace_file):
        try:
            with open(namespace_file) as fh:
                attrs["k8s.namespace.name"] = fh.read().strip()
        except OSError:
            pass

    return attrs


def detect_cloud_provider() -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}

    if _is_aws():
        attrs["cloud.provider"] = "aws"
        for env_var, attr_name in AWS_ENV_MAPPINGS.items():
            value = os.environ.get(env_var)
            if attr_name and value:
                attrs[attr_name] = value

        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            attrs["faas.id"] = (
                f"arn:aws:lambda:{attrs.get('cloud.region', 'unknown')}:"
                f"{attrs.get('cloud.account.id', 'unknown')}:"
                f"function:{os.environ['AWS_LAMBDA_FUNCTION_NAME']}"
            )

        az = _get_aws_availability_zone()
        if az:
            attrs["cloud.availability_zone"] = az
            if "cloud.region" not in attrs:
                attrs["cloud.region"] = az[:-1]

    elif _is_gcp():
        attrs["cloud.provider"] = "gcp"
        for env_var, attr_name in GCP_ENV_MAPPINGS.items():
            value = os.environ.get(env_var)
            if attr_name and value:
                attrs[attr_name] = value
        if os.environ.get("K_SERVICE"):
            attrs["faas.trigger"] = "http"
        elif os.environ.get("FUNCTION_NAME"):
            attrs["faas.trigger"] = os.environ.get("FUNCTION_TRIGGER_TYPE", "unknown")

    elif _is_azure():
        attrs["cloud.provider"] = "azure"
        for env_var, attr_name in AZURE_ENV_MAPPINGS.items():
            value = os.environ.get(env_var)
            if attr_name and value:
                attrs[attr_name] = value

    return attrs


def _is_aws() -> bool:
    indicators = [
        "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_LAMBDA_FUNCTION_NAME",
        "ECS_CONTAINER_METADATA_URI", "AWS_EXECUTION_ENV",
    ]
    return any(os.environ.get(var) for var in indicators)


def _is_gcp() -> bool:
    indicators = [
        "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT",
        "K_SERVICE", "FUNCTION_NAME",
    ]
    return any(os.environ.get(var) for var in indicators)


def _is_azure() -> bool:
    indicators = [
        "WEBSITE_SITE_NAME", "AZURE_FUNCTIONS_ENVIRONMENT", "AZURE_SUBSCRIPTION_ID",
    ]
    return any(os.environ.get(var) for var in indicators)


def _get_aws_availability_zone() -> Optional[str]:
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return None
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/placement/availability-zone",
            headers={"Accept": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=0.5) as resp:  # noqa: S310
            return resp.read().decode("utf-8").strip()
    except Exception:
        return None


def detect_host() -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    try:
        hostname = socket.gethostname()
        if hostname:
            attrs["host.name"] = hostname
    except Exception:
        pass

    host_id = os.environ.get("HOST_ID") or os.environ.get("INSTANCE_ID")
    if host_id:
        attrs["host.id"] = host_id
    elif "host.name" in attrs:
        attrs["host.id"] = attrs["host.name"]

    attrs["os.type"] = sys.platform
    attrs["host.arch"] = platform.machine()
    return attrs


def detect_container() -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    container_id = _get_container_id()
    if container_id:
        attrs["container.id"] = container_id

    if os.path.exists("/.dockerenv"):
        attrs["container.runtime"] = "docker"
    elif os.environ.get("KUBERNETES_SERVICE_HOST"):
        attrs["container.runtime"] = "containerd"
    return attrs


def _get_container_id() -> Optional[str]:
    container_id = os.environ.get("CONTAINER_ID") or os.environ.get("HOSTNAME")

    cgroup_path = "/proc/self/cgroup"
    if os.path.exists(cgroup_path):
        try:
            with open(cgroup_path) as fh:
                for line in fh:
                    if "docker" in line or "kubepods" in line:
                        parts = line.strip().split("/")
                        if parts:
                            last = parts[-1]
                            if last.startswith("cri-containerd-"):
                                last = last[15:]
                            if len(last) >= 12:
                                return last[:64]
        except OSError:
            pass

    return container_id if container_id and len(container_id) >= 12 else None


def detect_process() -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    attrs["process.pid"] = os.getpid()
    attrs["process.runtime.name"] = "python"
    attrs["process.runtime.version"] = sys.version.split()[0]
    if sys.argv:
        attrs["process.command"] = sys.argv[0][:200]
    return attrs


def detect_serverless() -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}

    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        attrs["faas.name"] = os.environ["AWS_LAMBDA_FUNCTION_NAME"]
        version = os.environ.get("AWS_LAMBDA_FUNCTION_VERSION")
        if version:
            attrs["faas.version"] = version
        memory = os.environ.get("AWS_LAMBDA_FUNCTION_MEMORY_SIZE")
        if memory:
            attrs["faas.max_memory"] = int(memory) * 1024 * 1024

    elif os.environ.get("K_SERVICE"):
        attrs["faas.name"] = os.environ["K_SERVICE"]
        revision = os.environ.get("K_REVISION")
        if revision:
            attrs["faas.version"] = revision

    elif os.environ.get("FUNCTION_NAME"):
        attrs["faas.name"] = os.environ["FUNCTION_NAME"]
        target = os.environ.get("FUNCTION_TARGET")
        if target:
            attrs["faas.trigger"] = target

    elif os.environ.get("WEBSITE_SITE_NAME"):
        attrs["faas.name"] = os.environ["WEBSITE_SITE_NAME"]
        instance = os.environ.get("WEBSITE_INSTANCE_ID")
        if instance:
            attrs["faas.instance"] = instance

    return attrs


# =========================================================================
# Main Detection
# =========================================================================


@lru_cache(maxsize=1)
def detect_all_resources() -> Dict[str, Any]:
    """Detect all environment resource attributes.

    Results are cached (environment doesn't change during runtime).
    """
    attrs: Dict[str, Any] = {}
    attrs.update(detect_host())
    attrs.update(detect_process())
    attrs.update(detect_container())
    attrs.update(detect_cloud_provider())
    attrs.update(detect_kubernetes())
    attrs.update(detect_serverless())

    if "service.instance.id" not in attrs:
        container_id = attrs.get("container.id")
        if container_id:
            attrs["service.instance.id"] = container_id[:12]
        elif pod_name := attrs.get("k8s.pod.name"):
            attrs["service.instance.id"] = pod_name
        elif host_id := attrs.get("host.id"):
            attrs["service.instance.id"] = host_id

    return attrs


def get_resource_attributes(
    include_host: bool = True,
    include_process: bool = True,
    include_container: bool = True,
    include_cloud: bool = True,
    include_k8s: bool = True,
    include_faas: bool = True,
) -> Dict[str, Any]:
    """Get resource attributes with selective detection."""
    attrs: Dict[str, Any] = {}
    if include_host:
        attrs.update(detect_host())
    if include_process:
        attrs.update(detect_process())
    if include_container:
        attrs.update(detect_container())
    if include_cloud:
        attrs.update(detect_cloud_provider())
    if include_k8s:
        attrs.update(detect_kubernetes())
    if include_faas:
        attrs.update(detect_serverless())
    return attrs
