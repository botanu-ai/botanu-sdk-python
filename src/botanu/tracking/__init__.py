# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Botanu tracking components.

Provides tracking for different operation types:
- LLM/GenAI model calls
- Database, storage, and messaging operations
- Attempt ledger for durable cost tracking
"""

from __future__ import annotations

from botanu.tracking.data import (
    DBOperation,
    MessagingOperation,
    StorageOperation,
    set_data_metrics,
    set_warehouse_metrics,
    track_db_operation,
    track_messaging_operation,
    track_storage_operation,
)
from botanu.tracking.ledger import (
    AttemptLedger,
    AttemptStatus,
    LedgerEventType,
    get_ledger,
    record_attempt_ended,
    record_attempt_started,
    record_llm_attempted,
    record_tool_attempted,
    set_ledger,
)
from botanu.tracking.llm import (
    BotanuAttributes,
    GenAIAttributes,
    LLMTracker,
    ModelOperation,
    ToolTracker,
    set_llm_attributes,
    set_token_usage,
    track_llm_call,
    track_tool_call,
)

__all__ = [
    # LLM tracking
    "track_llm_call",
    "track_tool_call",
    "set_llm_attributes",
    "set_token_usage",
    "ModelOperation",
    "GenAIAttributes",
    "BotanuAttributes",
    "LLMTracker",
    "ToolTracker",
    # Data tracking
    "track_db_operation",
    "track_storage_operation",
    "track_messaging_operation",
    "set_data_metrics",
    "set_warehouse_metrics",
    "DBOperation",
    "StorageOperation",
    "MessagingOperation",
    # Attempt ledger
    "AttemptLedger",
    "get_ledger",
    "set_ledger",
    "record_attempt_started",
    "record_attempt_ended",
    "record_llm_attempted",
    "record_tool_attempted",
    "LedgerEventType",
    "AttemptStatus",
]
