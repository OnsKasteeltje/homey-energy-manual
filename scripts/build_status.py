#!/usr/bin/env python3
import json, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "status-config.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "data" / "homey-status.json"

def read_json(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def normalize_collection(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # Homey API collections can be maps keyed by id or wrappers.
        for key in ("result", "flows", "advancedFlows", "items"):
            if key in obj:
                return normalize_collection(obj[key])
        return list(obj.values())
    return []

std = normalize_collection(read_json(os.environ.get("HOMEY_STD_FLOWS_FILE", "tmp/standard-flows.json")))
adv = normalize_collection(read_json(os.environ.get("HOMEY_ADV_FLOWS_FILE", "tmp/advanced-flows.json")))

all_flows = []
for flow in std + adv:
    if not isinstance(flow, dict): 
        continue
    name = flow.get("name", "")
    if name not in CONFIG["include_names"]:
        continue
    enabled = bool(flow.get("enabled", True))
    broken = bool(flow.get("broken", False))
    if broken:
        status = "error"
    elif not enabled:
        status = "off"
    elif name in CONFIG["shadow_flows"]:
        status = "shadow"
    else:
        status = "active"
    all_flows.append({
        "name": name,
        "category": "Energie Manager" if "Energie Manager" in name else ("Warm water" if "Warm water" in name else "Legacy"),
        "status": status,
        "enabled": enabled,
        "broken": broken,
        "detail": CONFIG.get("flow_details", {}).get(name, "")
    })

# Ensure missing configured flows are visible as unknown/error rather than silently disappearing.
seen = {f["name"] for f in all_flows}
for name in CONFIG["include_names"]:
    if name not in seen:
        all_flows.append({
            "name": name,
            "category": "Energie Manager" if "Energie Manager" in name else ("Warm water" if "Warm water" in name else "Legacy"),
            "status": "error",
            "enabled": False,
            "broken": True,
            "detail": "Niet aangetroffen in Homey API-resultaat"
        })

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source": "Homey API via GitHub Actions",
    "sync_ok": True,
    "flows": all_flows,
    "values": {}
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {OUT}")
