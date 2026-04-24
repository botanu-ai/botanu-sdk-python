# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Optional Presidio NER layer on top of the regex scrubber.

Opt-in via ``BotanuConfig(pii_scrub_use_presidio=True)`` or
``BOTANU_PII_SCRUB_USE_PRESIDIO=true``. Requires the ``pii-nlp`` extra::

    pip install botanu[pii-nlp]

If Presidio is not installed, :func:`presidio_scrub` logs a warning once
and returns the input unchanged — callers should rely on the regex pass
for their floor guarantee.

Mirrors the evaluator's :mod:`app.pii.presidio_scrubber` entity list so
SDK and evaluator redact the same categories (double coverage by design).
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ENTITIES: List[str] = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "PERSON",
    "LOCATION",
    "IP_ADDRESS",
    "US_BANK_NUMBER",
    "MEDICAL_LICENSE",
]

_analyzer = None
_anonymizer = None
_operators = None
_initialized = False
_available = False
_warned = False


def _ensure_initialized(replacement: str) -> bool:
    """Lazy-load Presidio engines. Returns True if available.

    Cold start is ~1s (spaCy model load); cached for process lifetime.
    """
    global _analyzer, _anonymizer, _operators, _initialized, _available, _warned
    if _initialized:
        return _available
    _initialized = True
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig

        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
        _operators = {"DEFAULT": OperatorConfig("replace", {"new_value": replacement})}
        _available = True
        return True
    except ImportError:
        if not _warned:
            logger.warning(
                "Botanu PII scrubber: pii_scrub_use_presidio=True but presidio is not installed. "
                "Install with: pip install botanu[pii-nlp]. Falling back to regex-only scrubbing."
            )
            _warned = True
        return False


def presidio_scrub(text: str, replacement: str = "[REDACTED]", entities: Optional[List[str]] = None) -> str:
    """Return *text* with Presidio-detected PII replaced by *replacement*.

    No-op when the package is not installed — regex-only scrubbing still
    runs upstream in :func:`botanu.sdk.pii.apply_scrub`.
    """
    if not text:
        return text
    if not _ensure_initialized(replacement):
        return text
    results = _analyzer.analyze(text=text, entities=entities or _DEFAULT_ENTITIES, language="en")  # type: ignore[union-attr]
    anonymized = _anonymizer.anonymize(text=text, analyzer_results=results, operators=_operators)  # type: ignore[union-attr]
    return anonymized.text


def _reset_for_tests() -> None:
    """Test-only hook to re-trigger the lazy init after monkey-patching imports."""
    global _analyzer, _anonymizer, _operators, _initialized, _available, _warned
    _analyzer = None
    _anonymizer = None
    _operators = None
    _initialized = False
    _available = False
    _warned = False
