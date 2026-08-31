from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from prometheus_client import make_asgi_app
from psycopg.rows import dict_row

API_SCHEMA = "PI_EMS_MANAGEMENT_API_V0.1"
RELEASE = os.getenv("EMS_RELEASE", "pi-ems-bootstrap-v0.1")
MODE = os.getenv("EMS_MODE", "SHADOW").upper()
DATABASE_URL = os.getenv("DATABASE_URL", "")
MANAGEMENT_API_TOKEN = os.getenv("MANAGEMENT_API_TOKEN", "")
HOMEY_BASE_URL = os.getenv("HOMEY_BASE_URL", "")
HOMEY_TOKEN = os.getenv("HOMEY_TOKEN", "")
VICTRON_HOST = os.getenv("VICTRON_HOST", "")

if MODE != "SHADOW":
    raise RuntimeError("Management API v0.1 may only start while EMS_MODE=SHADOW")
if not MANAGEMENT_API_TOKEN:
    raise RuntimeError("MANAGEMENT_API_TOKEN is required")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")

app = FastAPI(
    title="Pi EMS Management API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/metrics", make_asgi_app())


def require_token(authorization: str | None = Header(default=None)) -> None:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Bearer token required")
    supplied = authorization[len(prefix) :]
    if not hmac.compare_digest(supplied, MANAGEMENT_API_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid token")


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "mode": MODE, "write_capability": False}


@app.get("/v1/status", dependencies=[Depends(require_token)])
def status() -> dict[str, Any]:
    db_ok = True
    try:
        fetch_one("SELECT 1 AS ok")
    except Exception:
        db_ok = False
    return {
        "schema": API_SCHEMA,
        "release": RELEASE,
        "mode": MODE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": "OK" if db_ok else "DEGRADED",
        "homey_configured": bool(HOMEY_BASE_URL and HOMEY_TOKEN),
        "victron_configured": bool(VICTRON_HOST),
        "write_capability": False,
        "control_operations": False,
    }


@app.get("/v1/state", dependencies=[Depends(require_token)])
def latest_state() -> dict[str, Any]:
    row = fetch_one(
        "SELECT captured_at, schema_version, source_revision, payload "
        "FROM state_snapshots ORDER BY captured_at DESC LIMIT 1"
    )
    return {"schema": API_SCHEMA, "state": row}


@app.get("/v1/shadow-comparisons", dependencies=[Depends(require_token)])
def shadow_comparisons(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT created_at, module, input_revision, equivalent, difference, "
        "homey_output, pi_output FROM shadow_comparisons "
        "ORDER BY created_at DESC LIMIT %s",
        (limit,),
    )
    return {"schema": API_SCHEMA, "items": rows}


@app.get("/v1/system-health", dependencies=[Depends(require_token)])
def system_health(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT captured_at, component, status, payload FROM system_health "
        "ORDER BY captured_at DESC LIMIT %s",
        (limit,),
    )
    return {"schema": API_SCHEMA, "items": rows}


@app.get("/v1/power-intents", dependencies=[Depends(require_token)])
def power_intents(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT created_at, source_revision, ev_target_w, ww_target_w, payload "
        "FROM power_intents ORDER BY created_at DESC LIMIT %s",
        (limit,),
    )
    return {"schema": API_SCHEMA, "items": rows}


@app.get("/v1/gate-results", dependencies=[Depends(require_token)])
def gate_results(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT created_at, gate_name, outcome, reason, payload FROM gate_results "
        "ORDER BY created_at DESC LIMIT %s",
        (limit,),
    )
    return {"schema": API_SCHEMA, "items": rows}
