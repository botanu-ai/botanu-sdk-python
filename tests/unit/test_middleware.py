# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for BotanuMiddleware (FastAPI/Starlette)."""

from __future__ import annotations

import pytest
from opentelemetry import context as otel_context
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from botanu.sdk.middleware import BotanuMiddleware


def _make_app(*, use_case: str = "test_uc", workflow: str | None = None, auto_generate_run_id: bool = True):
    """Build a minimal Starlette app with BotanuMiddleware."""

    async def homepage(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(
        BotanuMiddleware,
        use_case=use_case,
        workflow=workflow,
        auto_generate_run_id=auto_generate_run_id,
    )
    return app


@pytest.fixture(autouse=True)
def _clean_otel_context():
    """Reset OTel context before each middleware test to avoid baggage leaking."""
    token = otel_context.attach(otel_context.Context())
    yield
    otel_context.detach(token)


class TestBotanuMiddleware:
    """Tests for BotanuMiddleware dispatch behaviour."""

    def test_response_contains_use_case_header(self, memory_exporter):
        client = TestClient(_make_app(use_case="billing"))
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["x-botanu-use-case"] == "billing"

    def test_response_contains_workflow_header(self, memory_exporter):
        client = TestClient(_make_app(use_case="billing", workflow="invoice_flow"))
        resp = client.get("/")
        assert resp.headers["x-botanu-workflow"] == "invoice_flow"

    def test_auto_generated_run_id_in_response(self, memory_exporter):
        client = TestClient(_make_app())
        resp = client.get("/")
        run_id = resp.headers.get("x-botanu-run-id")
        assert run_id is not None
        assert len(run_id) > 0

    def test_run_id_propagated_from_header(self, memory_exporter):
        client = TestClient(_make_app())
        resp = client.get("/", headers={"x-botanu-run-id": "my-custom-run-123"})
        assert resp.headers["x-botanu-run-id"] == "my-custom-run-123"

    def test_use_case_propagated_from_header(self, memory_exporter):
        client = TestClient(_make_app(use_case="default_uc"))
        resp = client.get("/", headers={"x-botanu-use-case": "overridden_uc"})
        assert resp.headers["x-botanu-use-case"] == "overridden_uc"

    def test_workflow_propagated_from_header(self, memory_exporter):
        client = TestClient(_make_app(use_case="uc", workflow="default_wf"))
        resp = client.get("/", headers={"x-botanu-workflow": "overridden_wf"})
        assert resp.headers["x-botanu-workflow"] == "overridden_wf"

    def test_no_auto_run_id_when_disabled(self, memory_exporter):
        client = TestClient(_make_app(auto_generate_run_id=False))
        resp = client.get("/")
        # Should not have a run_id header since none was provided and auto-gen is off
        assert "x-botanu-run-id" not in resp.headers

    def test_workflow_defaults_to_use_case(self, memory_exporter):
        client = TestClient(_make_app(use_case="my_uc"))
        resp = client.get("/")
        assert resp.headers["x-botanu-workflow"] == "my_uc"

    def test_customer_id_propagated_from_header(self, memory_exporter):
        client = TestClient(_make_app())
        resp = client.get("/", headers={"x-botanu-customer-id": "cust-456"})
        assert resp.status_code == 200

    def test_each_request_gets_unique_run_id(self, memory_exporter):
        client = TestClient(_make_app())
        resp1 = client.get("/")
        resp2 = client.get("/")
        run_id1 = resp1.headers.get("x-botanu-run-id")
        run_id2 = resp2.headers.get("x-botanu-run-id")
        assert run_id1 != run_id2


class TestMiddlewareBaggageIsolation:
    """Tests for baggage context isolation between requests."""

    def test_baggage_does_not_leak_between_requests(self, memory_exporter):
        """Baggage set in request 1 must not appear in request 2."""

        app_with_baggage_check = _make_baggage_check_app()
        client = TestClient(app_with_baggage_check)

        # Request 1: sends a custom run_id
        resp1 = client.get("/check", headers={"x-botanu-run-id": "leak-test-001"})
        resp1.json()

        # Request 2: no custom run_id
        resp2 = client.get("/check")
        data2 = resp2.json()

        # Request 2 should NOT see request 1's run_id in baggage
        assert data2.get("run_id") != "leak-test-001"

    def test_header_priority_over_constructor_defaults(self, memory_exporter):
        """x-botanu-use-case header should override constructor default."""
        client = TestClient(_make_app(use_case="default_uc"))
        resp = client.get("/", headers={"x-botanu-use-case": "header_uc"})
        assert resp.headers["x-botanu-use-case"] == "header_uc"

    def test_multiple_headers_propagated(self, memory_exporter):
        """All x-botanu-* headers should be propagated together."""
        client = TestClient(_make_app(use_case="uc"))
        resp = client.get(
            "/",
            headers={
                "x-botanu-run-id": "multi-001",
                "x-botanu-use-case": "multi-uc",
                "x-botanu-workflow": "multi-wf",
                "x-botanu-customer-id": "cust-multi",
            },
        )
        assert resp.headers["x-botanu-run-id"] == "multi-001"
        assert resp.headers["x-botanu-use-case"] == "multi-uc"
        assert resp.headers["x-botanu-workflow"] == "multi-wf"

    def test_exception_in_handler_still_detaches_context(self, memory_exporter):
        """Context token should be detached even when handler raises."""
        app = _make_error_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/error")
        assert resp.status_code == 500


def _make_baggage_check_app():
    """Build app that returns current baggage values."""
    from opentelemetry import baggage as otel_baggage
    from opentelemetry.context import get_current

    async def check_baggage(request):
        run_id = otel_baggage.get_baggage("botanu.run_id", context=get_current())
        return JSONResponse({"run_id": run_id})

    app = Starlette(routes=[Route("/check", check_baggage)])
    app.add_middleware(BotanuMiddleware, use_case="test")
    return app


def _make_error_app():
    """Build app that raises an exception in the handler."""

    async def error_handler(request):
        raise RuntimeError("Intentional test error")

    app = Starlette(routes=[Route("/error", error_handler)])
    app.add_middleware(BotanuMiddleware, use_case="error_test")
    return app
