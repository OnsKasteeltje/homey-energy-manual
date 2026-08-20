#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "status-config.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "data" / "homey-status.json"


def read_json(path: str) -> tuple[Any, bool, str | None]:
    """Read a Homey API snapshot without silently treating failures as success."""
    p = Path(path)
    if not p.exists():
        return {}, False, f"Bronbestand ontbreekt: {p}"
    try:
        return json.loads(p.read_text(encoding="utf-8")), True, None
    except (OSError, json.JSONDecodeError) as exc:
        return {}, False, f"Bronbestand ongeldig: {p}: {exc}"


def normalize_collection(obj: Any) -> list[Any]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # Homey API collections can be maps keyed by id or wrappers.
        for key in ("result", "flows", "advancedFlows", "items"):
            if key in obj:
                return normalize_collection(obj[key])
        return list(obj.values())
    return []


def strict_bool(value: Any, default: bool) -> bool:
    """Accept actual booleans and well-known serialized boolean values only."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def category_for(name: str) -> str:
    if "Energie Manager" in name:
        return "Energie Manager"
    if "Warm water" in name:
        return "Warm water"
    return "Legacy"


std_path = os.environ.get("HOMEY_STD_FLOWS_FILE", "tmp/standard-flows.json")
adv_path = os.environ.get("HOMEY_ADV_FLOWS_FILE", "tmp/advanced-flows.json")
std_raw, std_ok, std_error = read_json(std_path)
adv_raw, adv_ok, adv_error = read_json(adv_path)
std = normalize_collection(std_raw)
adv = normalize_collection(adv_raw)

all_flows: list[dict[str, Any]] = []
for flow in std + adv:
    if not isinstance(flow, dict):
        continue
    name = str(flow.get("name", ""))
    if name not in CONFIG["include_names"]:
        continue
    enabled = strict_bool(flow.get("enabled"), True)
    broken = strict_bool(flow.get("broken"), False)
    if broken:
        status = "error"
    elif not enabled:
        status = "off"
    elif name in CONFIG["shadow_flows"]:
        status = "shadow"
    else:
        status = "active"
    all_flows.append(
        {
            "name": name,
            "category": category_for(name),
            "status": status,
            "enabled": enabled,
            "broken": broken,
            "detail": CONFIG.get("flow_details", {}).get(name, ""),
        }
    )

# Ensure missing configured flows are visible rather than silently disappearing.
seen = {flow["name"] for flow in all_flows}
for name in CONFIG["include_names"]:
    if name not in seen:
        all_flows.append(
            {
                "name": name,
                "category": category_for(name),
                "status": "unknown" if not (std_ok and adv_ok) else "error",
                "enabled": False,
                "broken": bool(std_ok and adv_ok),
                "detail": (
                    "Niet te beoordelen: Homey API-bron onvolledig"
                    if not (std_ok and adv_ok)
                    else "Niet aangetroffen in volledig Homey API-resultaat"
                ),
            }
        )

errors = [error for error in (std_error, adv_error) if error]
sync_ok = std_ok and adv_ok

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source": "Homey API via GitHub Actions",
    "sync_ok": sync_ok,
    "diagnostics": {
        "standard_flows_source_ok": std_ok,
        "advanced_flows_source_ok": adv_ok,
        "standard_flows_count": len(std),
        "advanced_flows_count": len(adv),
        "errors": errors,
    },
    "flows": all_flows,
    "values": {},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {OUT} (sync_ok={sync_ok})")
