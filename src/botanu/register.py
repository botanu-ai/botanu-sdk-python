# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Zero-code initialization entry point.

Import this module to auto-initialize Botanu SDK with no code changes.
All configuration is read from environment variables or botanu.yaml.

Usage::

    # As a Python module flag
    python -m botanu.register && python app.py

    # Or via PYTHONPATH preload (works with gunicorn, uvicorn, etc.)
    python -c "import botanu.register" && python app.py

    # Or in gunicorn config
    # gunicorn.conf.py:
    def on_starting(server):
        import botanu.register  # noqa: F401

    # Or in uvicorn
    uvicorn app:app --env-file .env

    # Or in Dockerfile
    ENV BOTANU_API_KEY=btnu_live_...
    ENV BOTANU_SERVICE_NAME=my-service
    CMD ["python", "-c", "import botanu.register; import uvicorn; uvicorn.run('app:app')"]

Configuration (env vars or botanu.yaml):

    BOTANU_API_KEY        - API key (required for Botanu Cloud)
    BOTANU_SERVICE_NAME   - Service name (recommended)
    BOTANU_ENVIRONMENT    - Environment (default: production)

See docs/getting-started/configuration.md for full options.
"""

from __future__ import annotations

import logging

from botanu.sdk.bootstrap import enable

logger = logging.getLogger(__name__)

result = enable()

if result:
    logger.info("Botanu SDK auto-initialized via botanu.register")
