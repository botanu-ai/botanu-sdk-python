# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial open-source release
- `enable()` / `disable()` bootstrap
- `@botanu_use_case` decorator with UUIDv7 run_id
- `emit_outcome()` and `set_business_context()` span helpers
- `RunContextEnricher` span processor
- LLM tracking with OTel GenAI semconv alignment
- Data tracking for database, storage, and messaging
- Resource detection for K8s, AWS, GCP, Azure, serverless
- Auto-instrumentation for 20+ libraries
- Optional extras: `[sdk]`, `[instruments]`, `[genai]`, `[carriers]`, `[all]`

[Unreleased]: https://github.com/botanu-ai/botanu-sdk-python/compare/v0.0.0...HEAD
