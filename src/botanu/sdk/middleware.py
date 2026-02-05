# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""FastAPI / Starlette middleware for span enrichment.

This middleware works alongside OpenTelemetry's FastAPIInstrumentor to enrich
spans with Botanu-specific context.
"""

from __future__ import annotations

import uuid
from typing import Optional

from opentelemetry import baggage, trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from botanu.sdk.context import set_baggage


class BotanuMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to enrich spans with Botanu context.

    This middleware should be used **after** OpenTelemetry's
    ``FastAPIInstrumentor``.  It extracts Botanu context from incoming
    requests and enriches the current span with Botanu attributes.

    Example::

        from fastapi import FastAPI
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from botanu.sdk.middleware import BotanuMiddleware

        app = FastAPI()
        FastAPIInstrumentor.instrument_app(app)
        app.add_middleware(
            BotanuMiddleware,
            use_case="customer_support",
            workflow="ticket_api",
        )
    """

    def __init__(
        self,
        app: object,
        *,
        use_case: str,
        workflow: Optional[str] = None,
        auto_generate_run_id: bool = True,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.use_case = use_case
        self.workflow = workflow or use_case
        self.auto_generate_run_id = auto_generate_run_id

    async def dispatch(self, request: Request, call_next: object) -> Response:  # type: ignore[override]
        """Process request and enrich span with Botanu context."""
        span = trace.get_current_span()

        # Extract run_id from baggage or headers
        run_id = baggage.get_baggage("botanu.run_id")
        if not run_id:
            run_id = request.headers.get("x-botanu-run-id")

        if not run_id and self.auto_generate_run_id:
            run_id = str(uuid.uuid4())

        use_case = baggage.get_baggage("botanu.use_case") or request.headers.get("x-botanu-use-case") or self.use_case
        workflow = baggage.get_baggage("botanu.workflow") or request.headers.get("x-botanu-workflow") or self.workflow
        customer_id = baggage.get_baggage("botanu.customer_id") or request.headers.get("x-botanu-customer-id")

        # Enrich span with Botanu attributes
        if run_id:
            span.set_attribute("botanu.run_id", run_id)
            set_baggage("botanu.run_id", run_id)

        span.set_attribute("botanu.use_case", use_case)
        set_baggage("botanu.use_case", use_case)

        span.set_attribute("botanu.workflow", workflow)
        set_baggage("botanu.workflow", workflow)

        if customer_id:
            span.set_attribute("botanu.customer_id", customer_id)
            set_baggage("botanu.customer_id", customer_id)

        span.set_attribute("http.route", request.url.path)
        span.set_attribute("http.method", request.method)

        response = await call_next(request)  # type: ignore[misc]

        if run_id:
            response.headers["x-botanu-run-id"] = run_id
        response.headers["x-botanu-use-case"] = use_case
        response.headers["x-botanu-workflow"] = workflow

        return response
