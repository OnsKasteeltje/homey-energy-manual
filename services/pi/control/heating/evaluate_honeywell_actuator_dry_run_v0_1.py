#!/usr/bin/env python3
"""Six-room Honeywell actuation DRY-RUN V0.1. Local JSON in, stdout JSON out.

No network, Homey access, Honeywell API access, device write, or runtime timer.
A prospective candidate is not a physical permission or ownership proof.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "EMS_HEATING_HONEYWELL_ACTUATOR_DRY_RUN_V0.1"
ROOM_IDS = {
    "woonkamer": "6a79bb86-8c02-43db-be22-6f51e01efc6d",
    "eetkamer": "dd7ef4a3-ed9f-4e4d-92bb-090502068421",
    "keuken": "b7aec05b-953f-41e1-a7b4-ad09c9bf911e",
    "serre": "13625cb2-8fb5-4466-a21f-7addd8d72a88",
    "douwe_slaapkamer": "f74252a1-2879-4967-ba2d-41f56364e39b",
    "erker_douwe": "f9db36cd-8c0f-4beb-aa28-0127597652cf",
}
# The 4-room SHADOW Homey bridge is deliberately NOT touched by this evaluator.
DATA = Path("/home/jeroen/ems/data")
DEFAULTS = {
    "heating": DATA / "heating-preheat-shadow-v0.3.json",
    "gate": DATA / "heating-control-gate-shadow-v0.5.json",
    "grant": DATA / "heating-production-grant-v0.1.json",
    "honeywell": Path("/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json"),
    "p1": DATA / "energy-state-v2.json",
}
# Evidence-check horizons, not settings of any live actuator.
MAX_AGE = {"heating": 420, "gate": 120, "grant": 120, "honeywell": 420, "p1": 120}
FUTURE_SKEW_SECONDS = 30


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def obj(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def room_map(items: Any) -> dict[str, dict] | None:
    if not isinstance(items, list):
        return None
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            return None
        if item["key"] in result:
            return None
        result[item["key"]] = item
    return result


def fresh(value: Any, now: datetime, max_age_seconds: int) -> bool:
    at = timestamp(value)
    return at is not None and -FUTURE_SKEW_SECONDS <= (now - at).total_seconds() <= max_age_seconds


def check_source(name: str, data: dict, now: datetime) -> str | None:
    requirements = {
        "heating": ("EMS_HEATING_PREHEAT_SHADOW_V0.3", "READ_ONLY", "SHADOW"),
        "gate": ("EMS_HEATING_CONTROL_GATE_SHADOW_V0.5", "READ_ONLY", "SHADOW"),
        "grant": ("EMS_PI_DYNAMIC_HEATING_GRANT_V0.1", "PRODUCTION_PLANNER_GRANT", None),
        "honeywell": ("EMS_HONEYWELL_STATE_V0.2", "READ_ONLY", None),
        "p1": (None, None, None),
    }
    schema, mode, control_mode = requirements[name]
    if schema and data.get("schema") != schema:
        return f"{name.upper()}_SCHEMA_INVALID"
    if mode and data.get("mode") != mode:
        return f"{name.upper()}_MODE_INVALID"
    if control_mode and data.get("controlMode") != control_mode:
        return f"{name.upper()}_CONTROL_MODE_INVALID"
    if name in ("heating", "gate") and data.get("controlWrites") is not False:
        return f"{name.upper()}_WRITE_GUARD_INVALID"
    if name in ("gate", "grant") and data.get("physicalWriteAllowed") is not False:
        return f"{name.upper()}_WRITE_GUARD_INVALID"
    if name in ("heating", "gate", "grant") and data.get("baselineAuthority") != "HONEYWELL":
        return f"{name.upper()}_BASELINE_AUTHORITY_INVALID"
    if name == "grant" and data.get("allocationAuthority") != "DYNAMIC_PI_PLANNER":
        return "GRANT_PLANNER_AUTHORITY_INVALID"
    # For P1 use the actual P1 measurement timestamp, not a republished snapshot time.
    at = obj(data.get("meta")).get("source_sample_at") if name == "p1" else data.get("generatedAt")
    if not fresh(at, now, MAX_AGE[name]):
        return f"{name.upper()}_SOURCE_STALE_OR_UNTIMED"
    return None


# Presentation only. Original denialReasons remain untouched and authoritative.
# Lower rank means a more informative primary explanation, not control priority.
REASON_INFO = {
    "HONEYWELL_OVERRIDE_ACTIVE": (10, "Honeywell", "Handmatige Honeywell-override actief",
                                  "De ruimte volgt nu niet het gewone programma. EMS verandert deze instelling niet.",
                                  "Alleen een wijziging door de gebruiker naar het normale programma kan dit opheffen."),
    "HONEYWELL_MODE_UNKNOWN": (5, "Gegevens", "Honeywell-modus is onbekend",
                              "De huidige thermostaatmodus kan niet veilig worden geïnterpreteerd.",
                              "Controleer of Honeywell opnieuw geldige modusgegevens levert."),
    "HONEYWELL_OVERRIDE_UNTIL_UNEXPECTED": (5, "Gegevens", "Honeywell-gegevens spreken elkaar tegen",
                                           "Honeywell meldt het normale programma maar ook een override-eindtijd.",
                                           "Controleer de actuele Honeywell-stand; niet automatisch corrigeren."),
    "HONEYWELL_DEVICE_ID_MISMATCH": (5, "Configuratie", "Thermostaatkoppeling klopt niet",
                                     "Het Honeywell-apparaat komt niet overeen met de vaste kamerkoppeling.",
                                     "Controleer de room-to-device mapping."),
    "ROOM_SOURCE_MISSING": (5, "Gegevens", "Kamergegevens ontbreken",
                            "De kamer ontbreekt in minimaal één van de benodigde gegevensbronnen.",
                            "Controleer de beschikbare Heating- en Honeywell-snapshots."),
    "DUPLICATE_OR_INVALID_ROOM_KEYS": (5, "Gegevens", "Kamerlijst is ongeldig",
                                       "Een bron bevat ontbrekende of dubbele kamersleutels.",
                                       "Controleer de bronbestanden en sleutels."),
    "HONEYWELL_TARGET_MISMATCH": (5, "Gegevens", "Honeywell-target komt niet overeen",
                                  "De actuele Honeywell-target wijkt af van de target waarmee de planner rekende.",
                                  "Nieuwe, consistente waarnemingen zijn nodig."),
    "HONEYWELL_SYSTEM_MODE_MISMATCH": (5, "Gegevens", "Honeywell-systeemmodus verschilt",
                                       "De twee Honeywell-waarnemingen beschrijven niet dezelfde systeemmodus.",
                                       "Controleer of de laatste Honeywell-gegevens zijn bijgewerkt."),
    "P1_GRID_POWER_INVALID": (5, "Gegevens", "P1-vermogen is ongeldig",
                              "P1-import of -export ontbreekt of bevat een ongeldige waarde.",
                              "Controleer de P1-meetketen."),
    "GRANT_EXPIRED": (5, "Gegevens", "Planner-vrijgave is verlopen",
                      "De geldigheidsduur van de Heating grant is verstreken.",
                      "Wacht op een nieuwe geldige plannerbeslissing."),
    "NO_SCHEDULED_UP": (20, "Honeywell-schema", "Geen geplande temperatuurverhoging",
                        "De volgende Honeywell-programmawisseling is geen verhoging.",
                        "Geen actie nodig: wacht op een geschikte geplande verhoging."),
    "SCHEDULED_UP_EXPIRED": (21, "Honeywell-schema", "Geplande verhoging is voorbij",
                             "Het tijdstip van de beoogde Honeywell-verhoging ligt al in het verleden.",
                             "Wacht op het volgende geschikte tijdslot."),
    "HONEYWELL_PREHEAT_NOT_ALLOWED": (30, "Verwarming", "Deze ruimte is nu niet geschikt voor voorverwarmen",
                                      "De Honeywell- en verwarmingsvoorwaarden staan geen vervroegde stap toe.",
                                      "Controleer het verwarmingsadvies; behoud de normale regeling."),
    "INITIAL_STEP_EXCEEDS_0_5C": (24, "Veiligheid", "Temperatuurstap is te groot",
                                  "De voorgestelde eerste stap is groter dan de toegestane 0,5 °C.",
                                  "De planner moet een kleinere stap voorstellen."),
    "TARGET_OUTSIDE_UP_BOUNDS": (65, "Planner-detail", "Geen geldige temperatuurstap",
                                 "V0.5 heeft geen doel binnen de actuele en de toekomstige Honeywell-target.",
                                 "Zie de onderliggende planner- en schemavoorwaarden."),
    "NO_PRODUCTION_HEATING_GRANT": (40, "Planning", "Planner geeft verwarming geen ruimte",
                                    "De centrale planner heeft preheating op dit moment niet vrijgegeven.",
                                    "Dit verandert pas bij een nieuwe, geldige plannerbeslissing."),
    "ROOM_NOT_IN_PRODUCTION_GRANT": (43, "Planning", "Deze kamer is niet geselecteerd",
                                     "De centrale planner heeft deze ruimte niet opgenomen in de vrijgave.",
                                     "Wacht op een Heating grant waarin de kamer voorkomt."),
    "P1_NOT_EXPORTING_WITHOUT_IMPORT": (50, "Energie", "Geen bruikbaar P1-overschot",
                                        "De P1-meting toont op dit moment geen netto teruglevering zonder afname.",
                                        "Er is eerst daadwerkelijk export nodig; een momentopname is nog geen stabiele vrijgave."),
    "UPSTREAM_SIX_ROOM_SCOPE_MIGRATION_REQUIRED": (15, "Integratie", "Kamer valt nog buiten de upstream preheat-scope",
                                                    "De V0.3-kamerconfiguratie staat deze ruimte nog niet toe.",
                                                    "Controleer de SHADOW-only scopeconfiguratie."),
    "V05_SIX_ROOM_SCOPE_MIGRATION_REQUIRED": (15, "Integratie", "Kamer valt nog buiten de V0.5-scope",
                                              "De V0.5-kamerconfiguratie staat deze ruimte nog niet toe.",
                                              "Controleer de SHADOW-only scopeconfiguratie."),
    "V05_KEEP_HAS_NO_PHYSICAL_OWNERSHIP_PROOF": (16, "Veiligheid", "V0.5 wil een stand behouden, zonder eigendomsbewijs",
                                                "Een SHADOW KEEP bewijst niet dat EMS de thermostaat fysiek heeft ingesteld.",
                                                "Geen nieuwe actie; eerst een aparte, gecontroleerde actuatorvalidatie."),
    "V05_NO_NEW_SET_CANDIDATE": (70, "Planner-detail", "V0.5 stelt geen nieuwe verwarmingsstap voor",
                                "De control gate heeft geen nieuwe temperatuurverhoging vrijgegeven.",
                                "Controleer eerst de overige voorwaarden."),
    "V05_ROOM_CHECKS_NOT_ALL_TRUE": (71, "Planner-detail", "V0.5-controles blokkeren",
                                     "Minimaal één beveiligingscontrole van V0.5 is niet geslaagd.",
                                     "Bekijk bij behoefte de technische codes en V0.5-checks."),
    "V05_UPSTREAM_NOT_SAFE": (6, "Gegevens", "V0.5 mist geldige upstream-voorwaarden",
                              "Een voorafgaande bron is volgens V0.5 niet consistent of actueel.",
                              "Controleer de freshness/ordering in V0.5."),
    "V05_SOURCE_EVIDENCE_MISSING": (5, "Gegevens", "V0.5-bronbewijs ontbreekt",
                                    "De V0.5-keten heeft geen controleerbare herkomstgegevens.",
                                    "Controleer de V0.5-uitvoer."),
    "UPSTREAM_HONEYWELL_OVERRIDE_OR_MODE": (67, "Planner-detail", "Override blokkeert al upstream",
                                            "De planner heeft de Honeywell-modus als blokkade verwerkt.",
                                            "EMS respecteert deze modus."),
    "V05_COMMAND_WRITE_CONTRACT_INVALID": (5, "Veiligheid", "V0.5-writebeveiliging klopt niet",
                                           "Een SHADOW-commando voldoet niet aan de no-write-afspraak.",
                                           "Stop de evaluatie en controleer het V0.5-contract."),
    "GRANT_ROOM_LIST_INVALID": (5, "Gegevens", "Planner-kamerlijst ongeldig",
                                "De Heating grant bevat geen geldige kamerlijst.",
                                "Controleer de uitvoer van de centrale planner."),
}
def describe_reason(code: str, observed_mode: str | None, observed_target: float | None) -> dict:
    known = REASON_INFO.get(code)
    if known is None:
        if any(flag in code for flag in ("INVALID", "STALE", "UNTIMED", "MISMATCH", "FROM_FUTURE")):
            known = (4, "Gegevens", "Onvoldoende betrouwbare brongegevens",
                     "Een noodzakelijke EMS-bron is ontbrekend, onjuist of verouderd.",
                     "Controleer de technische code en herstel eerst de betreffende bron.")
        else:
            known = (60, "Overig", "Aanvullende veiligheidscontrole blokkeert",
                     "Een EMS-voorwaarde is niet geslaagd.",
                     "Bekijk de oorspronkelijke technische code voor details.")
    rank, category, title, explanation, next_step = known
    if code == "HONEYWELL_OVERRIDE_ACTIVE":
        if observed_mode == "permanent_override":
            target = f" op {observed_target:g} °C" if observed_target is not None else ""
            title = f"Permanente Honeywell-override{target}"
        elif observed_mode == "temporary_override":
            title = "Tijdelijke Honeywell-override"
    return {
        "code": code, "category": category, "title": title,
        "explanation": explanation, "nextStep": next_step, "priority": rank,
    }


# These translations are based on the actual reason contract in
# build_heating_production_grant_v0_1.py. Unknown priority codes are not guessed.
PLANNER_EXPLANATIONS = {
    "NO_HEATING_PREHEAT_CANDIDATE": "Er is op dit moment geen ruimte die voldoet aan de voorwaarden voor vervroegd opwarmen.",
    "DYNAMIC_PLAN_STALE_OR_NOT_CURRENT": "De centrale energieplanning is niet actueel of niet geldig.",
    "NO_CURRENT_DYNAMIC_PLAN_SLOT": "Er is geen geldig planningsinterval voor dit moment.",
    "FLEX_PRIORITY_PRE_DATES_HEATING": "De energieprioriteiten zijn ouder dan de verwarmingsinformatie.",
    "FLEX_PRIORITY_DID_NOT_GRANT_HEATING": "De centrale energieverdeling heeft voorverwarmen niet geselecteerd.",
}
PRIORITY_LABELS = {
    "EV": "autoladen", "WW": "warm water", "QUOOKER": "Quooker",
    "HEATING": "ruimteverwarming",
}


def explain_planner(grant: dict) -> dict:
    """Report the documented planner decision, never infer priority from P1 alone."""
    heating = obj(grant.get("heating"))
    reason = heating.get("reason")
    priority_reason = heating.get("priorityReason")
    priority_owner = heating.get("priorityOwner")
    detail = PLANNER_EXPLANATIONS.get(reason)
    if detail is None and isinstance(reason, str):
        if reason.endswith("_STALE") or "STALE" in reason:
            detail = "Een bron van de energieplanner is niet actueel."
        elif reason.startswith("PRODUCTION_GRANT_"):
            detail = "De plannerreden en de ontbrekende verwarmingsvrijgave zijn niet eenduidig."
    if detail is None:
        detail = "Voorverwarmen is momenteel niet ingepland; de precieze plannerreden is nog niet vertaald."
    # Only state the declared owner. An owner is not proof of available PV.
    if reason not in {"NO_HEATING_PREHEAT_CANDIDATE", "DYNAMIC_PLAN_STALE_OR_NOT_CURRENT",
                      "NO_CURRENT_DYNAMIC_PLAN_SLOT", "FLEX_PRIORITY_PRE_DATES_HEATING"}:
        owner_label = PRIORITY_LABELS.get(priority_owner)
        if owner_label and priority_owner != "HEATING":
            detail += f" De planner registreert {owner_label} als huidige prioriteit."
    return {
        "code": "NO_PRODUCTION_HEATING_GRANT",
        "category": "Planning",
        "title": "Voorverwarmen momenteel niet ingepland",
        "explanation": detail,
        "plannerReasonCode": reason if isinstance(reason, str) else None,
        "priorityReasonCode": priority_reason if isinstance(priority_reason, str) else None,
        "priorityOwner": priority_owner if isinstance(priority_owner, str) else None,
    }


# Diagnostic consequences are deliberately retained in raw denialReasons.
# They do not become duplicate human-facing conditions.
DERIVED_ROOM = {
    "UPSTREAM_HONEYWELL_OVERRIDE_OR_MODE", "V05_NO_NEW_SET_CANDIDATE",
    "V05_ROOM_CHECKS_NOT_ALL_TRUE",
}


def general_conditions(reasons: list[str], grant: dict) -> list[dict]:
    conditions = []
    for code in reasons:
        if code == "NO_PRODUCTION_HEATING_GRANT":
            conditions.append(explain_planner(grant))
        else:
            d = describe_reason(code, None, None)
            conditions.append({
                "code": code, "category": d["category"], "title": d["title"],
                "explanation": d["explanation"],
            })
    return conditions


def room_conditions(reasons: list[str], shared: list[str],
                    observed_mode: str | None, observed_target: float | None,
                    command_action: str | None) -> tuple[list[dict], list[str]]:
    """Split local conditions and derived details; do not pick a primary room reason."""
    unique = [code for code in reasons if code not in shared]
    suppressed = set(DERIVED_ROOM)
    if command_action != "WOULD_SET_TEMP":
        suppressed.add("TARGET_OUTSIDE_UP_BOUNDS")
    if "HONEYWELL_OVERRIDE_ACTIVE" in unique:
        suppressed.add("HONEYWELL_PREHEAT_NOT_ALLOWED")
    if "NO_PRODUCTION_HEATING_GRANT" in shared:
        suppressed.add("ROOM_NOT_IN_PRODUCTION_GRANT")
    visible = [describe_reason(code, observed_mode, observed_target)
               for code in unique if code not in suppressed]
    visible.sort(key=lambda d: (d["priority"], d["code"]))
    return ([{"code": d["code"], "category": d["category"],
              "title": d["title"], "explanation": d["explanation"]}
             for d in visible],
            [code for code in unique if code in suppressed])


def human_report(payload: dict) -> str:
    """Read-only Dutch CLI rendering. Original raw denialReasons stay in JSON."""
    lines = ["Honeywell preheat | zes kamers | DRY-RUN", "GEEN FYSIEKE AANSTURING",
             "", "ALGEMENE VOORWAARDEN"]
    general = payload.get("generalConditions") or []
    if not general:
        lines.append("Geen algemene blokkades in deze momentopname.")
    for cond in general:
        lines.append(f"- {cond['title']}: {cond['explanation']}")
    lines += ["", "PER KAMER (aanvullend op algemene voorwaarden)"]
    for room in payload.get("rooms") or []:
        title = room["key"].replace("_", " ").capitalize()
        lines.append(f"{title}:")
        local = room.get("roomConditions") or []
        if not local:
            lines.append("  Geen aanvullende kamerblokkades.")
        else:
            for cond in local:
                lines.append(f"  - {cond['title']}")
    lines += ["", "Technische codes: denialReasons in de standaard JSON-uitvoer.",
              "Dit overzicht verleent GEEN toestemming voor fysieke aansturing."]
    return "\n".join(lines)


def evaluate(docs: dict[str, Any], *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include UTC offset")
    now = now.astimezone(timezone.utc)
    iso = now.isoformat().replace("+00:00", "Z")
    data = {name: obj(docs.get(name)) for name in DEFAULTS}
    global_reasons = [reason for name, document in data.items()
                      if (reason := check_source(name, document, now))]
    if timestamp(data["grant"].get("validUntil")) is None or timestamp(data["grant"].get("validUntil")) <= now:
        global_reasons.append("GRANT_EXPIRED")
    if obj(data["grant"].get("heating")).get("grant") != "PRODUCTION_GRANT":
        global_reasons.append("NO_PRODUCTION_HEATING_GRANT")
    for name in ("heating", "gate", "grant"):
        age = timestamp(data[name].get("generatedAt"))
        if age and age > now.replace(tzinfo=timezone.utc):
            # Recent future skew permitted by freshness check, but never physical execution.
            global_reasons.append(f"{name.upper()}_FROM_FUTURE")
    heat, gate, vendor = (room_map(data[k].get("rooms" if k != "honeywell" else "zones"))
                          for k in ("heating", "gate", "honeywell"))
    if any(x is None for x in (heat, gate, vendor)):
        global_reasons.append("DUPLICATE_OR_INVALID_ROOM_KEYS")
    if not isinstance(obj(data["grant"].get("heating")).get("readyRooms"), list):
        global_reasons.append("GRANT_ROOM_LIST_INVALID")
    p1 = obj(data["p1"].get("grid"))
    export_w = numeric(p1.get("export_w"))
    import_w = numeric(p1.get("import_w"))
    if export_w is None or import_w is None or export_w < 0 or import_w < 0:
        global_reasons.append("P1_GRID_POWER_INVALID")
    elif export_w <= 0 or import_w > 0:
        global_reasons.append("P1_NOT_EXPORTING_WITHOUT_IMPORT")
    if data["gate"].get("sourceFreshness") and (
        obj(obj(data["gate"]["sourceFreshness"]).get("heating")).get("status") != "OK"
        or obj(obj(data["gate"]["sourceFreshness"]).get("progression")).get("status") != "OK"
        or obj(data["gate"]["sourceFreshness"]).get("progressionConsistentWithHeating") is not True
        or obj(data["gate"]["sourceFreshness"]).get("progressionUpstreamSafe") is not True
    ):
        global_reasons.append("V05_UPSTREAM_NOT_SAFE")
    if data["gate"].get("sourceFreshness") is None:
        global_reasons.append("V05_SOURCE_EVIDENCE_MISSING")
    results = []
    for key, device_id in ROOM_IDS.items():
        h = (heat or {}).get(key)
        g = (gate or {}).get(key)
        v = (vendor or {}).get(key)
        reasons = list(dict.fromkeys(global_reasons))
        if not h or not g or not v:
            reasons.append("ROOM_SOURCE_MISSING")
        if v and v.get("homeyDeviceId") != device_id:
            reasons.append("HONEYWELL_DEVICE_ID_MISMATCH")
        vendor_mode = str(v.get("setpointMode") or "").lower() if v else None
        effective = obj(h.get("effective")) if h else {}
        effective_mode = str(effective.get("setpointMode") or "").lower()
        if v and vendor_mode == "follow_schedule" and v.get("overrideUntil") not in (None, ""):
            reasons.append("HONEYWELL_OVERRIDE_UNTIL_UNEXPECTED")
        if v and vendor_mode != "follow_schedule":
            reasons.append("HONEYWELL_OVERRIDE_ACTIVE" if vendor_mode in ("permanent_override", "temporary_override")
                           else "HONEYWELL_MODE_UNKNOWN")
        if h and effective_mode != "follow_schedule":
            reasons.append("UPSTREAM_HONEYWELL_OVERRIDE_OR_MODE")
        if h and effective.get("preheatAdvanceAllowed") is not True:
            reasons.append("HONEYWELL_PREHEAT_NOT_ALLOWED")
        if h and v:
            actual = numeric(v.get("targetTemperature_C"))
            upstream = numeric(effective.get("currentTargetTemperature_C"))
            if actual is None or upstream is None or abs(actual - upstream) > 0.01:
                reasons.append("HONEYWELL_TARGET_MISMATCH")
            if effective.get("systemMode") != obj(data["honeywell"].get("location")).get("systemMode"):
                reasons.append("HONEYWELL_SYSTEM_MODE_MISMATCH")
        # Upstream six-room preheatScope is observed on Pi; check it independently of Homey egress.
        if h and h.get("preheatScope") is not True:
            reasons.append("UPSTREAM_SIX_ROOM_SCOPE_MIGRATION_REQUIRED")
        if g and g.get("preheatScope") is not True:
            reasons.append("V05_SIX_ROOM_SCOPE_MIGRATION_REQUIRED")
        if g and obj(g.get("command")).get("action") == "WOULD_KEEP_TEMP":
            reasons.append("V05_KEEP_HAS_NO_PHYSICAL_OWNERSHIP_PROOF")
        elif g and obj(g.get("command")).get("action") != "WOULD_SET_TEMP":
            reasons.append("V05_NO_NEW_SET_CANDIDATE")
        if g and (not isinstance(g.get("checks"), dict) or not all(val is True for val in g["checks"].values())):
            reasons.append("V05_ROOM_CHECKS_NOT_ALL_TRUE")
        if g and obj(g.get("command")).get("physicalWrite") is not False:
            reasons.append("V05_COMMAND_WRITE_CONTRACT_INVALID")
        ready = obj(data["grant"].get("heating")).get("readyRooms")
        if not isinstance(ready, list) or key not in ready:
            reasons.append("ROOM_NOT_IN_PRODUCTION_GRANT")
        target, end = None, None
        if g:
            baseline, cmd = obj(g.get("baseline")), obj(g.get("command"))
            current = numeric(baseline.get("currentTarget_C"))
            future = numeric(baseline.get("futureTarget_C"))
            target = numeric(cmd.get("target_C"))
            end = timestamp(baseline.get("changeAt"))
            if baseline.get("direction") != "UP":
                reasons.append("NO_SCHEDULED_UP")
            if target is None or current is None or future is None or not(current < target <= future):
                reasons.append("TARGET_OUTSIDE_UP_BOUNDS")
            elif target > current + 0.5 + 0.00001:
                # The actual incremental bound must be enforced by the planner;
                # absent physical ownership proof, never infer a larger first step.
                reasons.append("INITIAL_STEP_EXCEEDS_0_5C")
            if end is None or end <= now:
                reasons.append("SCHEDULED_UP_EXPIRED")
        reasons = list(dict.fromkeys(reasons))
        candidate = len(reasons) == 0
        local_conditions, derived_details = room_conditions(
            reasons, global_reasons, vendor_mode,
            numeric(v.get("targetTemperature_C")) if v else None,
            obj(g.get("command")).get("action") if g else None,
        )
        results.append({
            "key": key, "homeyDeviceId": device_id,
            "observedMode": vendor_mode,
            "simulatedAction": "WOULD_SET_TEMP" if candidate else "HOLD",
            "status": "CANDIDATE_ONLY" if candidate else "BLOCKED",
            "simulatedTarget_C": target if candidate else None,
            "simulatedExpiryAt": end.isoformat().replace("+00:00", "Z") if candidate else None,
            "denialReasons": reasons,
            "roomConditions": local_conditions,
            "technicalOnly": derived_details,
            "liveExecutionAllowed": False,
            "physicalWrite": False,
            "physicalOwnershipProven": False,
        })
    return {
        "schema": SCHEMA, "generatedAt": iso,
        "mode": "READ_ONLY", "controlMode": "DRY_RUN",
        "liveExecutionAllowed": False, "physicalWriteAllowed": False,
        "physicalWrites": 0, "deviceReads": 0, "networkCalls": 0,
        "rooms": results, "roomCount": len(results),
        "globalDenialReasons": list(dict.fromkeys(global_reasons)),
        "generalConditions": general_conditions(list(dict.fromkeys(global_reasons)), data["grant"]),
        "edgeProofMissing": ["SUSTAINED_P1_EXPORT_UNPROVEN", "HOMEY_EDGE_READ_UNPROVEN",
                             "TEMPORARY_OVERRIDE_ACK_UNPROVEN", "INDEPENDENT_HONEYWELL_READBACK_UNPROVEN",
                             "GRANT_REVISION_NOT_BOUND_TO_V05",
                             "PHYSICAL_OWNERSHIP_UNPROVEN"],
        "source": "PI_LOCAL_JSON_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, default in DEFAULTS.items():
        parser.add_argument(f"--{key}", type=Path, default=default)
    parser.add_argument("--human", action="store_true",
                        help="Toon korte Nederlandstalige blokkadeverklaringen i.p.v. JSON")
    args = parser.parse_args()
    docs = {}
    for key in DEFAULTS:
        try:
            docs[key] = json.loads(getattr(args, key).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            docs[key] = {}
            print(f"WARN: {key}: {type(error).__name__}", file=__import__("sys").stderr)
    result = evaluate(docs)
    if args.human:
        print(human_report(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
