# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for botanu.sampling.content_sampler."""

from __future__ import annotations

import random

from botanu.sampling.content_sampler import should_capture_content


class TestShouldCaptureContent:
    def test_rate_zero_returns_false(self):
        """rate=0.0 must never capture."""
        for _ in range(100):
            assert should_capture_content(0.0) is False

    def test_rate_negative_returns_false(self):
        """Negative rates (defensive) must never capture."""
        assert should_capture_content(-0.1) is False
        assert should_capture_content(-1.0) is False

    def test_rate_one_returns_true(self):
        """rate=1.0 must always capture."""
        for _ in range(100):
            assert should_capture_content(1.0) is True

    def test_rate_above_one_returns_true(self):
        """Rates above 1.0 (defensive) must always capture."""
        assert should_capture_content(1.5) is True
        assert should_capture_content(2.0) is True

    def test_rate_half_approx_half(self):
        """rate=0.5 must capture roughly half the time (seeded RNG)."""
        random.seed(42)
        results = [should_capture_content(0.5) for _ in range(10_000)]
        captured = sum(results)
        # Generous tolerance: 10000 trials with p=0.5, stddev=50, expect ~5000±150
        assert 4700 < captured < 5300, f"expected ~5000 captures, got {captured}"

    def test_event_id_argument_accepted(self):
        """event_id is accepted but currently unused (MVP behaviour)."""
        # Should not raise
        should_capture_content(0.0, event_id="evt_abc")
        should_capture_content(1.0, event_id="evt_xyz")

    def test_event_id_none_default(self):
        """event_id defaults to None."""
        # Should not raise, should behave identically to omitting
        assert should_capture_content(0.0, None) is False
        assert should_capture_content(1.0, None) is True
