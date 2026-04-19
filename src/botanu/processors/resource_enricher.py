# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""ResourceEnricher — infer `botanu.cloud_provider` + `botanu.bytes_transferred`
from OTel semantic-convention attributes set by auto-instrumentation.

Why this exists: the cost worker (botanu-cost-engine-workflow) prices non-LLM
spans via `rate × bytes_transferred` and looks up rate cards keyed by
`cloud_provider + system_name`. OTel auto-instrumentation emits the raw
attributes (`db.system`, `http.request.body.size`, `aws.service`, etc.) but
does NOT emit botanu-namespaced attributes in the shape the cost worker
reads. Without this enricher, S3 PUTs, DynamoDB ops, and egress all price to
$0 — see the `pricing.md` problem statement.

Attributes written:

- `botanu.cloud_provider`       ("aws" | "gcp" | "azure" | …)
- `botanu.bytes_transferred`    (int, sent + received combined)

The enricher is purely additive. It leaves all original OTel attributes
intact — no customer observability breaks.

Explicit values set by `set_bytes_transferred()` / `cloud_provider=` kwarg on
trackers take precedence: this enricher only writes if the target attribute
is not already present (checked at `on_end` time via the span's attribute
dict).
"""

from __future__ import annotations

import logging
from typing import Mapping, Optional

from opentelemetry import context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

logger = logging.getLogger(__name__)


# System/service → cloud provider. Used when the semconv `cloud.provider`
# attribute is absent (most auto-instrumentations don't set it, so we infer
# from the db/messaging system name or the AWS/Azure/GCP service name).
_SYSTEM_TO_CLOUD_PROVIDER: dict[str, str] = {
    # AWS
    "dynamodb": "aws",
    "s3": "aws",
    "sqs": "aws",
    "sns": "aws",
    "kinesis": "aws",
    "eventbridge": "aws",
    "lambda": "aws",
    "elasticache": "aws",
    "redshift": "aws",
    "athena": "aws",
    "neptune": "aws",
    "efs": "aws",
    # GCP
    "firestore": "gcp",
    "bigquery": "gcp",
    "gcs": "gcp",
    "pubsub": "gcp",
    # Azure
    "cosmosdb": "azure",
    "azure_blob": "azure",
    "servicebus": "azure",
    "eventhub": "azure",
    "synapse": "azure",
}

_BOTANU_CLOUD_PROVIDER = "botanu.cloud_provider"
_BOTANU_BYTES_TRANSFERRED = "botanu.bytes_transferred"


class ResourceEnricher(SpanProcessor):
    """Write botanu-namespaced resource attributes from OTel semconv data.

    Runs at `on_end` (not `on_start`) — auto-instrumentation populates the
    source attributes on span start, but some (notably http.*.body.size) are
    only known when the response completes.
    """

    def on_start(self, span: Span, parent_context: Optional[context.Context] = None) -> None:
        # Cheap path: no work at start. Waiting until on_end lets us read
        # response-time attributes that auto-instrumentation sets after the
        # wrapped call returns (bytes, status codes, etc.).
        return

    def on_end(self, span: ReadableSpan) -> None:
        attrs = span.attributes or {}

        # Skip LLM spans entirely — LLM pricing goes through pricing_model_tokens
        # (prompt/completion tokens), not bytes_transferred. Writing bytes here
        # would double-count into cost_infra_usd.
        if _is_llm_span(attrs):
            return

        cloud_provider = _infer_cloud_provider(attrs)
        bytes_transferred = _infer_bytes_transferred(attrs)

        if cloud_provider is None and bytes_transferred is None:
            return

        # Writing to a ReadableSpan: OTel SDK's ReadableSpan is read-only by
        # contract, but the concrete _Span class exposes set_attribute. If
        # the attribute is already set (explicit API or customer), skip —
        # explicit beats inferred.
        setter = getattr(span, "set_attribute", None)
        if setter is None:
            return

        if cloud_provider is not None and _BOTANU_CLOUD_PROVIDER not in attrs:
            setter(_BOTANU_CLOUD_PROVIDER, cloud_provider)
        if bytes_transferred is not None and _BOTANU_BYTES_TRANSFERRED not in attrs:
            setter(_BOTANU_BYTES_TRANSFERRED, bytes_transferred)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _is_llm_span(attrs: Mapping[str, object]) -> bool:
    return (
        "gen_ai.request.model" in attrs
        or "gen_ai.system" in attrs
        or "llm.request.model" in attrs
    )


def _infer_cloud_provider(attrs: Mapping[str, object]) -> Optional[str]:
    # 1. Explicit semconv `cloud.provider` (if set, trust it)
    explicit = attrs.get("cloud.provider")
    if isinstance(explicit, str) and explicit:
        return explicit.lower()

    # 2. AWS auto-instrumentation sets `aws.service` or `rpc.system="aws-api"`
    if attrs.get("rpc.system") == "aws-api" or "aws.service" in attrs or "aws.region" in attrs:
        return "aws"
    if "gcp.service" in attrs or "gcp.project_id" in attrs:
        return "gcp"
    if "azure.resource" in attrs or "azure.namespace" in attrs:
        return "azure"

    # 3. Infer from system name (db.system, messaging.system, botanu.storage.system)
    for key in ("db.system", "messaging.system", "botanu.storage.system"):
        val = attrs.get(key)
        if isinstance(val, str):
            provider = _SYSTEM_TO_CLOUD_PROVIDER.get(val.lower())
            if provider:
                return provider
    return None


def _infer_bytes_transferred(attrs: Mapping[str, object]) -> Optional[int]:
    total = 0
    saw_any = False

    # OTel HTTP semconv (stable)
    for key in ("http.request.body.size", "http.response.body.size"):
        val = attrs.get(key)
        if isinstance(val, int) and val >= 0:
            total += val
            saw_any = True

    # botanu tracker attrs (fallback — populated by DBTracker.set_result etc.)
    if not saw_any:
        for key in (
            "botanu.data.bytes_read",
            "botanu.data.bytes_written",
            "botanu.messaging.bytes_transferred",
            "botanu.warehouse.bytes_scanned",
        ):
            val = attrs.get(key)
            if isinstance(val, int) and val >= 0:
                total += val
                saw_any = True

    return total if saw_any else None
