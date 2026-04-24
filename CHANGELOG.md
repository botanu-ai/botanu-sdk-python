# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking

- Primary API is now `botanu.event(...)` — works as context manager, async context manager, and decorator. The legacy `@botanu_workflow`, `workflow` alias, `run_botanu`, and `@botanu_outcome` decorators are removed.
- `emit_outcome` is keyword-only and no longer accepts a `status` argument. Authoritative event outcome is resolved server-side from SoR connectors, HITL reviews, or eval verdict rollup.
- Lean baggage propagation is removed. All seven baggage keys (plus any retry/deadline keys when set) always propagate. The `BOTANU_PROPAGATION_MODE` env var, the `propagation_mode` field on `BotanuConfig`, `BAGGAGE_KEYS_LEAN`, and the `lean_mode` parameter on `RunContextEnricher` / `RunContext.to_baggage_dict` are all gone.

### Added

- `botanu.event(...)` as context manager, async context manager, and decorator — a single API for marking business events.
- `botanu.step(name)` for nested phase spans inside an event.
- SDK initialises automatically on the first `botanu.event(...)` call. Customers no longer need to call any bootstrap function by hand.
- `botanu.set_correlation(**keys)` for SoR Tier-1 correlation.
- Security: OTLP bearer token is attached only when the endpoint host is botanu-owned (`*.botanu.ai`) or a local dev host, preventing tenant API-key leakage via a customer-supplied `OTEL_EXPORTER_OTLP_ENDPOINT`. Authorization / `x-api-key` / `botanu-api-key` headers and `user:pass@` URL credentials are redacted in logs.
- OTel coexistence: when the host app already has the OTel SDK wired up, botanu preserves the existing sampling ratio and adds itself alongside. `register.py` module for zero-code initialisation in containers / gunicorn / process runners.
- Content capture for eval, gated by `content_capture_rate`. Writes `botanu.eval.input_content` / `botanu.eval.output_content` with in-process PII scrub (regex by default; optional Microsoft Presidio via `pip install botanu[pii-nlp]`).
- `ResourceEnricher` span processor for deployment attributes.
- Release tooling: `scripts/pre_publish_check.py` — builds sdist + wheel, runs `twine check`, installs into a fresh venv, validates the public API surface, runs an end-to-end smoke test.

### Fixed

- `SampledSpanProcessor.on_start` now gates on the same ratio decision as `on_end`; forwarding `on_start` unconditionally while gating `on_end` leaked span bookkeeping inside wrapped exporters.

[Unreleased]: https://github.com/botanu-ai/botanu-sdk-python/commits/main
