# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for botanu.sdk.pii — regex scrubber + Presidio opt-in path."""

from __future__ import annotations

import importlib.util

import pytest

from botanu.sdk.config import BotanuConfig
from botanu.sdk.pii import PIIScrubber, _luhn_valid, _reset_cache_for_tests, apply_scrub


@pytest.fixture(autouse=True)
def _reset_cache():
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


class TestBuiltinPatterns:
    def test_scrubs_email(self):
        out = PIIScrubber().scrub("contact me at alice@example.com please")
        assert "alice@example.com" not in out
        assert "[REDACTED]" in out

    def test_scrubs_phone_e164(self):
        out = PIIScrubber().scrub("call +14155551234 now")
        assert "+14155551234" not in out
        assert "[REDACTED]" in out

    def test_scrubs_phone_us(self):
        out = PIIScrubber().scrub("call (415) 555-1234 or 415-555-1234")
        assert "(415) 555-1234" not in out
        assert "415-555-1234" not in out

    def test_scrubs_ssn(self):
        out = PIIScrubber().scrub("SSN 123-45-6789 on file")
        assert "123-45-6789" not in out

    def test_scrubs_credit_card_luhn_valid(self):
        # 4111 1111 1111 1111 is the standard Visa test card — Luhn-valid.
        out = PIIScrubber().scrub("card 4111 1111 1111 1111 expires soon")
        assert "4111" not in out
        assert "[REDACTED]" in out

    def test_luhn_rejects_non_card(self):
        # 16-digit order ID that fails Luhn — must pass through untouched.
        assert _luhn_valid("4111111111111112") is False
        out = PIIScrubber().scrub("order id 4111111111111112 placed")
        assert "4111111111111112" in out

    def test_scrubs_ipv4(self):
        out = PIIScrubber().scrub("request from 192.168.1.100 failed")
        assert "192.168.1.100" not in out

    def test_scrubs_ipv6(self):
        out = PIIScrubber().scrub("peer 2001:0db8:85a3:0000:0000:8a2e:0370:7334 down")
        assert "2001:0db8" not in out

    def test_scrubs_bearer_token(self):
        out = PIIScrubber().scrub("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.foo.bar")
        assert "Bearer " not in out or "[REDACTED]" in out

    def test_scrubs_jwt(self):
        out = PIIScrubber().scrub("token=eyJabc.eyJdef.XYZ123 next")
        assert "eyJabc.eyJdef.XYZ123" not in out

    # Test secrets are assembled at runtime to avoid tripping source-side
    # secret scanners (GitHub push-protection, gitleaks, etc.) that match
    # on literal prefixes like ``sk_live_`` / ``ghp_`` / ``xoxb-``.

    def test_scrubs_aws_access_key(self):
        fake = "AKIA" + "IOSFODNN7EXAMPLE"
        out = PIIScrubber().scrub(f"AWS key {fake} detected")
        assert fake not in out

    def test_scrubs_github_token(self):
        fake = "ghp" + "_" + ("a" * 36)
        out = PIIScrubber().scrub(f"export GH={fake} done")
        assert "ghp" + "_" not in out

    def test_scrubs_stripe_key(self):
        fake = "sk" + "_live_" + "abcdefghijklmnopqrstuvwxyz"
        out = PIIScrubber().scrub(f"STRIPE={fake} used")
        assert "sk" + "_live_" not in out

    def test_scrubs_slack_token(self):
        fake = "xoxb" + "-12345-67890-abcdef"
        out = PIIScrubber().scrub(f"token {fake} caught")
        assert "xoxb" + "-" not in out

    def test_scrubs_openai_key(self):
        fake = "sk" + "-abcdefghijklmnopqrstuv"
        out = PIIScrubber().scrub(f"OPENAI={fake} leaked")
        assert fake not in out

    def test_scrubs_anthropic_key(self):
        fake = "sk" + "-ant-abcdefghijklmnopqrst123"
        out = PIIScrubber().scrub(f"ANTHROPIC={fake} leaked")
        assert "sk" + "-ant-" not in out


class TestConstructorOptions:
    def test_empty_text_noop(self):
        assert PIIScrubber().scrub("") == ""

    def test_none_like_noop(self):
        assert PIIScrubber().scrub("") == ""

    def test_clean_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog"
        assert PIIScrubber().scrub(text) == text

    def test_disable_specific_pattern(self):
        scrubber = PIIScrubber(disabled_patterns=["ipv4"])
        out = scrubber.scrub("server 10.0.0.1 and email me@x.com")
        assert "10.0.0.1" in out          # ipv4 disabled
        assert "me@x.com" not in out      # email still scrubbed

    def test_enabled_patterns_allowlist(self):
        scrubber = PIIScrubber(enabled_patterns=["email"])
        out = scrubber.scrub("email a@b.com and ip 10.0.0.1")
        assert "a@b.com" not in out
        assert "10.0.0.1" in out

    def test_custom_pattern(self):
        scrubber = PIIScrubber(custom_patterns={"employee_id": r"EMP-\d{6}"})
        out = scrubber.scrub("assigned to EMP-123456 today")
        assert "EMP-123456" not in out

    def test_custom_replacement_token(self):
        scrubber = PIIScrubber(replacement="<hidden>")
        out = scrubber.scrub("mail me at a@b.com")
        assert "<hidden>" in out
        assert "a@b.com" not in out

    def test_invalid_custom_regex_logged_not_raised(self, caplog):
        # Malformed regex should not crash construction.
        scrubber = PIIScrubber(custom_patterns={"bad": "(unclosed"})
        out = scrubber.scrub("a@b.com here")
        assert "a@b.com" not in out  # built-ins still work


class TestApplyScrubWithConfig:
    def test_default_config_scrubs(self):
        cfg = BotanuConfig()  # default pii_scrub_enabled=True
        out = apply_scrub("send to alice@acme.com", cfg)
        assert "alice@acme.com" not in out

    def test_disabled_scrubber_noop(self):
        cfg = BotanuConfig(pii_scrub_enabled=False)
        text = "send to alice@acme.com"
        assert apply_scrub(text, cfg) == text

    def test_empty_text_short_circuits(self):
        cfg = BotanuConfig()
        assert apply_scrub("", cfg) == ""

    def test_custom_replacement_roundtrips(self):
        cfg = BotanuConfig(pii_scrub_replacement="<PII>")
        out = apply_scrub("alice@acme.com here", cfg)
        assert "<PII>" in out

    def test_custom_patterns_from_config(self):
        cfg = BotanuConfig(pii_scrub_custom_patterns={"order": r"ORD-\d{4}"})
        out = apply_scrub("order ORD-1234 shipped to bob@x.com", cfg)
        assert "ORD-1234" not in out
        assert "bob@x.com" not in out

    def test_disable_patterns_from_config(self):
        cfg = BotanuConfig(pii_scrub_disable_patterns=["email"])
        out = apply_scrub("ping alice@acme.com from 1.2.3.4", cfg)
        assert "alice@acme.com" in out
        assert "1.2.3.4" not in out

    def test_cache_rebuilds_on_config_change(self):
        cfg1 = BotanuConfig(pii_scrub_enabled=True)
        apply_scrub("alice@acme.com", cfg1)
        cfg2 = BotanuConfig(pii_scrub_enabled=False)
        assert apply_scrub("alice@acme.com", cfg2) == "alice@acme.com"


_presidio_available = importlib.util.find_spec("presidio_analyzer") is not None


class TestPresidioOptIn:
    def test_opt_in_without_install_falls_back(self, caplog):
        """pii_scrub_use_presidio=True without Presidio installed should not raise
        and should still apply the regex pass."""
        if _presidio_available:
            pytest.skip("presidio installed — this test exercises the missing-package path")
        cfg = BotanuConfig(pii_scrub_use_presidio=True)
        out = apply_scrub("ping alice@acme.com", cfg)
        # regex pass still scrubs the email even though presidio is absent
        assert "alice@acme.com" not in out

    @pytest.mark.skipif(not _presidio_available, reason="presidio not installed")
    def test_scrubs_person_name_with_presidio(self):
        from botanu.sdk.pii_presidio import _reset_for_tests, presidio_scrub

        _reset_for_tests()
        out = presidio_scrub("meeting with John Smith tomorrow")
        # "John Smith" is a PERSON entity — Presidio should redact at least one token.
        assert "[REDACTED]" in out


class TestLuhnHelper:
    @pytest.mark.parametrize(
        "number, expected",
        [
            ("4111111111111111", True),
            ("4111 1111 1111 1111", True),
            ("5500 0000 0000 0004", True),
            ("4111111111111112", False),
            ("1234", False),
            ("12345678901234567890", False),
        ],
    )
    def test_luhn_valid(self, number, expected):
        assert _luhn_valid(number) is expected
