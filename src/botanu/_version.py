# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Dynamic version from package metadata (set by hatch-vcs at build time)."""

from __future__ import annotations

try:
    from importlib.metadata import version

    __version__: str = version("botanu")
except Exception:
    __version__ = "0.0.0.dev0"
