# Mobile API V1

Status: **candidate, read-only presentation contract**.

## Purpose

Expose one stable endpoint for native mobile clients without reintroducing GitHub as a
runtime data path. The Raspberry Pi remains the runtime authority. GitHub remains
source control, test and deployment history only.

Endpoint:

`GET /api/mobile/v1/overview`

Schema:

`EMS_MOBILE_OVERVIEW_V1`

## Boundary

Mobile V1 is a presentation aggregation over existing allowlisted Web Data API
resources.

It MUST NOT:

- make planner decisions;
- write to Homey or physical devices;
- become an authority for EV, WW, heating or flex control;
- read runtime status from GitHub;
- expose internal source payloads wholesale.

The response therefore always declares:

```json
{
  "readOnly": true,
  "presentationOnly": true,
  "capabilities": {
    "controlWrites": false,
    "physicalWrites": false
  }
}
```

## Runtime sources

The mandatory source is the canonical Pi Live V2 energy state already projected by
`state_current_resource()`.

Secondary presentation resources are best-effort:

- WW seasonal advice;
- Flex Priority SHADOW.

If a secondary resource is unavailable, the mobile endpoint remains available and
marks that section `UNAVAILABLE`. Failure of the canonical live energy state fails
the endpoint closed with HTTP 503.

Flex Priority SHADOW is presentation evidence, not live authority. Mobile V1 compares
its EV deadline-active state with the canonical Live V2 EV state and exposes its
decision only when they agree. A Flex source older than 75 minutes is marked `STALE`;
a semantic mismatch is marked `INCONSISTENT`. In both cases current Flex/Heating
decision fields are suppressed rather than shown as current facts.

## Initial response surface

Mobile V1 contains only fields required for a first native dashboard:

- grid power plus explicit import/export projection;
- PV power, other-house load and state freshness;
- EV connected/charging/power/current/deadline state; inactive deadlines do not expose
  old deadline timestamps or remaining-kWh values;
- hot-water mode, boiler state/action and seasonal advice availability; hot-water mode
  is limited to `CV` or `BOILER` and otherwise returned as null;
- Heating ready rooms and current SHADOW grant;
- Flex source timestamp, age, Live-V2 deadline consistency and, only while current
  and consistent, priority owner / EV role / reason;
- current EMS manager decision.

No command endpoint is part of Mobile V1.

## Network exposure

The Web Data API continues to bind to localhost by default. Remote iPhone access
must be implemented separately through the hardened HTTPS gateway/authentication
boundary. Do not expose port 3200 directly to the internet.

## Validation

Targeted regression:

```bash
python3 tests/integrations/test_mobile_api_v1.py
```

Existing Web Data API regression remains authoritative:

```bash
python3 tests/integrations/test_web_data_api.py
bash ./scripts/ems_architecture_gate.sh
```

## Next step

After Pi deployment and local validation of `/api/mobile/v1/overview`, build the
first SwiftUI client as read-only. Authentication and remote access are a separate
security step and should precede any future mobile command capability.
