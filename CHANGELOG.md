# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-02-05

### Added

- Initial open-source release under Apache-2.0 license
- **Core SDK**
  - `enable()` / `disable()` bootstrap functions for SDK initialization
  - `@botanu_workflow` decorator with UUIDv7 run_id generation
  - `@botanu_outcome` decorator for sub-function outcome tracking
  - `emit_outcome()` helper for recording business outcomes
  - `set_business_context()` for cost attribution dimensions
  - `RunContextEnricher` span processor for automatic run_id propagation

- **LLM Tracking** (aligned with OTel GenAI semantic conventions)
  - `track_llm_call()` context manager for LLM/model operations
  - `track_tool_call()` context manager for tool/function calls
  - Token usage tracking (input, output, cached)
  - Provider normalization for 15+ LLM providers
  - Support for all GenAI operations (chat, embeddings, etc.)

- **Data Tracking**
  - `track_db_operation()` for database operations
  - `track_storage_operation()` for object storage (S3, GCS, Azure Blob)
  - `track_messaging_operation()` for message queues (SQS, Kafka, Pub/Sub)
  - System normalization for 30+ database/storage systems

- **Context Propagation**
  - W3C Baggage propagation for cross-service run_id correlation
  - Lean mode (default) and full mode propagation options
  - `RunContext` model with retry tracking and deadline support

- **Resource Detection**
  - Kubernetes (pod, namespace, container)
  - AWS (EC2, ECS, Lambda, Fargate)
  - GCP (GCE, Cloud Run, Cloud Functions)
  - Azure (VM, Container Apps, Functions)

- **Auto-Instrumentation Support**
  - HTTP clients: requests, httpx, urllib3, aiohttp
  - Web frameworks: FastAPI, Flask, Django, Starlette
  - Databases: SQLAlchemy, psycopg2, asyncpg, pymongo, Redis
  - Messaging: Celery, Kafka
  - GenAI: OpenAI, Anthropic, Vertex AI, Google GenAI, LangChain

- **Optional Extras**
  - `[sdk]` - OTel SDK + OTLP exporter
  - `[instruments]` - Common library instrumentation
  - `[genai]` - GenAI provider instrumentation
  - `[carriers]` - Cross-service propagation helpers
  - `[all]` - Everything included
  - `[dev]` - Development and testing tools

- **Documentation**
  - Comprehensive docs in `/docs` following LF format
  - Getting started guides
  - API reference
  - Best practices and anti-patterns

### Dependencies

- Core: `opentelemetry-api >= 1.20.0`
- SDK extra: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`
- Python: `>= 3.9`

[Unreleased]: https://github.com/botanu-ai/botanu-sdk-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/botanu-ai/botanu-sdk-python/releases/tag/v0.1.0
