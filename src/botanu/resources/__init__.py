# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Resource detection using official OTel community detectors.

Instead of a custom reimplementation, we try to import the official
OpenTelemetry resource detector packages.  Each one is a lightweight
pip package that auto-detects environment attributes (K8s, AWS, GCP,
Azure, container).  If a package isn't installed, we gracefully skip it.

Install detectors for your environment::

    pip install botanu[aws]       # AWS EC2/ECS/EKS/Lambda
    pip install botanu[gcp]       # GCE/GKE/Cloud Run/Cloud Functions
    pip install botanu[azure]     # Azure VMs/App Service/Functions
    pip install botanu[cloud]     # All cloud detectors
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# (module_path, class_name) — tried in order.
# Each entry corresponds to a pip package from opentelemetry-python-contrib.
_DETECTOR_REGISTRY: List[Tuple[str, str]] = [
    # Built-in (opentelemetry-sdk — always available)
    ("opentelemetry.sdk.resources", "ProcessResourceDetector"),
    # opentelemetry-resource-detector-aws
    ("opentelemetry.resource.detector.aws.ec2", "AwsEc2ResourceDetector"),
    ("opentelemetry.resource.detector.aws.ecs", "AwsEcsResourceDetector"),
    ("opentelemetry.resource.detector.aws.eks", "AwsEksResourceDetector"),
    ("opentelemetry.resource.detector.aws.lambda_", "AwsLambdaResourceDetector"),
    # opentelemetry-resource-detector-gcp
    ("opentelemetry.resource.detector.gcp", "GoogleCloudResourceDetector"),
    # opentelemetry-resource-detector-azure
    ("opentelemetry.resource.detector.azure.vm", "AzureVMResourceDetector"),
    ("opentelemetry.resource.detector.azure.app_service", "AzureAppServiceResourceDetector"),
    # opentelemetry-resource-detector-container
    ("opentelemetry.resource.detector.container", "ContainerResourceDetector"),
]


def collect_detectors() -> list:
    """Return instances of all importable OTel resource detectors.

    Each detector implements ``opentelemetry.sdk.resources.ResourceDetector``.
    Missing packages are silently skipped.
    """
    detectors: list = []
    for module_path, class_name in _DETECTOR_REGISTRY:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            detectors.append(cls())
        except (ImportError, AttributeError):
            pass

    if detectors:
        names = [type(d).__name__ for d in detectors]
        logger.debug("Available resource detectors: %s", names)

    return detectors


def detect_resource_attrs() -> Dict[str, Any]:
    """Detect environment attributes using available OTel detectors.

    Returns a flat dict of resource attributes.  This is a convenience
    wrapper for callers that just need a dict (like bootstrap.py).
    """
    attrs: Dict[str, Any] = {}
    for detector in collect_detectors():
        try:
            resource = detector.detect()
            attrs.update(dict(resource.attributes))
        except Exception:
            # Community detectors may raise on network timeouts, missing
            # metadata endpoints, etc.  Never let detection break SDK init.
            logger.debug("Resource detector %s failed", type(detector).__name__, exc_info=True)
    return attrs


__all__ = ["collect_detectors", "detect_resource_attrs"]
