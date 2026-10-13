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

## Native EV deadline command boundary

The SwiftUI v0.2 client may issue an EV deadline, but this does **not** make Mobile
API V1 writable. Command traffic uses the existing, separately governed private
command ingress:

`POST /web/commands/tesla`

The write path is:

`SwiftUI -> Tailscale-only Caddy -> localhost Status API -> canonical Tesla command file -> existing Pi deadline-state builder -> normal Pi/Homey execution chain`

The native client must not call Homey or Easee directly and must not introduce a
generic command/write API. Its deadline client is limited to this one route.

The existing ingress remains authoritative for validation and safety: control PIN,
loopback-only upstream access, SOC/deadline/max-current validation, UUID
idempotency, atomic persistence and the existing derived-state builder. The native
client asks for the existing control PIN only in the explicit submit/cancel
confirmation and clears it immediately after that request; it does not persist the
PIN.

Readback uses `GET /web/commands/current` plus Mobile V1 refresh. An accepted
command whose derived state is still pending must be presented as pending rather
than as confirmed active.

## Network exposure

The Web Data API continues to bind to localhost by default. Native mobile access
uses the same private Tailscale-only Caddy ingress as the private EMS frontend:
`/api/mobile/*` is reverse-proxied to the loopback Web Data API on
`127.0.0.1:3200`. Do not add a LAN/wildcard/public listener and do not expose
port 3200 directly.

The current tailnet transport is private but HTTP at the Caddy layer. SwiftUI may
use a development ATS allowance while commissioning; a hardened future release
should use trusted HTTPS on the private tailnet and remove that allowance.

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

## Current native-client state

SwiftUI v0.1 validated the read-only Mobile V1 path end-to-end. v0.2 adds only the
bounded EV deadline command path described above. All other mobile control
capabilities remain out of scope.
