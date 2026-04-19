# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Botanu span processors.

Only :class:`RunContextEnricher` is needed in the SDK.
All other processing should happen in the OTel Collector.
"""

from botanu.processors.enricher import RunContextEnricher
from botanu.processors.resource_enricher import ResourceEnricher
from botanu.processors.sampled import SampledSpanProcessor

__all__ = ["RunContextEnricher", "ResourceEnricher", "SampledSpanProcessor"]
