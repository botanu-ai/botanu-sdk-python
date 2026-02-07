# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Botanu span processors.

Only :class:`RunContextEnricher` is needed in the SDK.
All other processing should happen in the OTel Collector.
"""

from botanu.processors.enricher import RunContextEnricher

__all__ = ["RunContextEnricher"]
