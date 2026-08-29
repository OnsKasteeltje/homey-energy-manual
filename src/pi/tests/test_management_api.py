from __future__ import annotations

import importlib
import os
import sys

from fastapi.testclient import TestClient


def load_api():
    os.environ["EMS_MODE"] = "SHADOW"
    os.environ["DATABASE_URL"] = "postgresql://unused"
    os.environ["MANAGEMENT_API_TOKEN"] = "test-token-0123456789abcdef0123456789abcdef"
    sys.modules.pop("management_api", None)
    return importlib.import_module("management_api")


def test_healthz_is_read_only():
    module = load_api()
    client = TestClient(module.app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["mode"] == "SHADOW"
    assert response.json()["write_capability"] is False


def test_management_endpoint_requires_bearer_token():
    module = load_api()
    client = TestClient(module.app)
    response = client.get("/v1/state")
    assert response.status_code == 401


def test_no_mutating_http_routes_exist():
    module = load_api()
    allowed = {"GET", "HEAD"}
    for route in module.app.routes:
        methods = getattr(route, "methods", None)
        if methods:
            assert set(methods).issubset(allowed)
