# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Security**
  - OTLP bearer token is attached only when the endpoint host is botanu-owned
    (`*.botanu.ai`) or a local dev host, preventing tenant API-key leakage
    via a customer-supplied `OTEL_EXPORTER_OTLP_ENDPOINT`.
  - Authorization / `x-api-key` / `botanu-api-key` headers and `user:pass@`
    URL credentials are redacted in logs.
- **Brownfield OTel coexistence**
  - `SampledSpanProcessor` preserves the host app's existing TracerProvider
    sampling ratio when botanu is bootstrapped into a project that already
    has OTel wired up.
  - `register.py` entry point for explicit opt-in without decorator-side
    provider mutation.
  - Bootstrap detects a pre-configured provider and hands off instead of
    overriding it.
- **Content capture for eval**
  - Workflow-level input/output capture gated by `content_capture_rate`
    config and a shared `content_sampler`. Writes
    `botanu.eval.input_content` / `botanu.eval.output_content`.
  - `set_input_content()` / `set_output_content()` on `LLMTracker` with the
    same gate, plus matching helpers on data-tracking helpers.
- **Multi-step workflows**
  - `@botanu_workflow(..., step=...)` parameter (stored in `RunContext`,
    not yet emitted to span attributes — kept backward compatible until the
    collector servicegraph work lands).
- **Resources**
  - `ResourceEnricher` span processor for deployment attributes.
- **Release tooling**
  - `scripts/pre_publish_check.py` red/green gate: builds sdist + wheel,
    runs `twine check`, installs into a fresh venv, validates the public
    API surface, runs an end-to-end decorator + `emit_outcome` smoke test.

### Fixed

- `SampledSpanProcessor.on_start` now gates on the same ratio decision as
  `on_end`; forwarding `on_start` unconditionally while gating `on_end`
  leaked span bookkeeping inside wrapped exporters (QUAL-C1).

### Initial release contents

Carried forward from the pre-tag scaffolding (never published):

- `enable()` / `disable()` bootstrap, `@botanu_workflow`,
  `@botanu_outcome`, `emit_outcome()`, `set_business_context()`,
  `RunContextEnricher` — with UUIDv7 run_ids.
- LLM tracking aligned with OTel GenAI semconv: `track_llm_call()`,
  `track_tool_call()`, token accounting, 15+ provider normalization.
- Data tracking: `track_db_operation()`, `track_storage_operation()`,
  `track_messaging_operation()`; 30+ system normalizations.
- W3C Baggage propagation with `RunContext` (retry tracking + deadline).
- Cloud resource detectors via optional extras (`aws`, `gcp`, `azure`,
  `container`, `cloud`).
- Auto-instrumentation bundled in the base install — HTTP clients, web
  frameworks, databases, messaging, and GenAI providers; instrumentation
  packages no-op when their target library is not installed.

[Unreleased]: https://github.com/botanu-ai/botanu-sdk-python/commits/main
