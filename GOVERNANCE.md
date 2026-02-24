# Governance

This document describes the governance model for the Botanu SDK project.

## Roles

### Users

Anyone who uses the SDK. Users are encouraged to participate by filing issues,
asking questions on [GitHub Discussions](https://github.com/botanu-ai/botanu-sdk-python/discussions),
and providing feedback.

### Contributors

Anyone who contributes to the project — opening issues, submitting pull requests,
improving documentation, or participating in discussions. All contributions
require [DCO sign-off](./CONTRIBUTING.md#developer-certificate-of-origin-dco).

### Maintainers

Maintainers are responsible for:

- Reviewing and merging pull requests
- Triaging issues
- Releasing new versions
- Ensuring project quality and direction

Current maintainers are listed in [MAINTAINERS.md](./MAINTAINERS.md).

## Becoming a Maintainer

Maintainers are contributors who have demonstrated:

- Sustained, high-quality contributions over time
- Deep understanding of the codebase and project goals
- Commitment to the community and the Code of Conduct

New maintainers are nominated by existing maintainers and approved by consensus.

## Decision Making

- Day-to-day technical decisions are made through pull request reviews
- Significant changes require approval from at least one maintainer
- Architectural or breaking changes should be discussed in a GitHub issue or
  discussion before implementation
- Disputes are resolved by maintainer consensus; if consensus cannot be reached,
  the lead maintainer has final say

## Scope

### In Scope

- The Botanu Python SDK (`botanu` PyPI package)
- Documentation in the `docs/` directory
- CI/CD workflows and release automation
- Integration guides for OpenTelemetry Collector

### Out of Scope

- The Botanu Collector (separate repository)
- The Botanu Cost Engine (separate repository)
- The Botanu UI (separate repository)
- Vendor-specific backend integrations

## Code of Conduct

All participants must follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## License

This project is licensed under [Apache-2.0](./LICENSE).
