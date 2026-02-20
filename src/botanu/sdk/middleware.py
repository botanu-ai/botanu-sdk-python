# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""FastAPI / Starlette middleware for span enrichment.

This middleware works alongside OpenTelemetry's FastAPIInstrumentor to enrich
spans with Botanu-specific context.
"""

from __future__ import annotations

import uuid
from typing import Optional

from opentelemetry import baggage as otel_baggage
from opentelemetry import trace
from opentelemetry.context import attach, detach, get_current
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


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
            workflow="customer_support",
        )
    """

    def __init__(
        self,
        app: object,
        *,
        workflow: str,
        auto_generate_run_id: bool = True,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.workflow = workflow
        self.auto_generate_run_id = auto_generate_run_id

    async def dispatch(self, request: Request, call_next: object) -> Response:  # type: ignore[override]
        """Process request and enrich span with Botanu context."""
        span = trace.get_current_span()

        run_id = otel_baggage.get_baggage("botanu.run_id")
        if not run_id:
            run_id = request.headers.get("x-botanu-run-id")

        if not run_id and self.auto_generate_run_id:
            run_id = str(uuid.uuid4())

        workflow = (
            otel_baggage.get_baggage("botanu.workflow") or request.headers.get("x-botanu-workflow") or self.workflow
        )
        customer_id = otel_baggage.get_baggage("botanu.customer_id") or request.headers.get("x-botanu-customer-id")

        if run_id:
            span.set_attribute("botanu.run_id", run_id)
        span.set_attribute("botanu.workflow", workflow)
        if customer_id:
            span.set_attribute("botanu.customer_id", customer_id)

        span.set_attribute("http.route", request.url.path)
        span.set_attribute("http.method", request.method)

        ctx = get_current()
        if run_id:
            ctx = otel_baggage.set_baggage("botanu.run_id", run_id, context=ctx)
        ctx = otel_baggage.set_baggage("botanu.workflow", workflow, context=ctx)
        if customer_id:
            ctx = otel_baggage.set_baggage("botanu.customer_id", customer_id, context=ctx)

        baggage_token = attach(ctx)
        try:
            response = await call_next(request)  # type: ignore[misc]
        finally:
            detach(baggage_token)

        if run_id:
            response.headers["x-botanu-run-id"] = run_id
        response.headers["x-botanu-workflow"] = workflow

        return response
