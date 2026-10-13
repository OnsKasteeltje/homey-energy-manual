# EMS Mobile v0.2

Native SwiftUI client for private EMS observability plus one bounded EV deadline command.

## Scope

The app has two deliberately separate paths:

- **observability:** `GET /api/mobile/v1/overview`, read-only;
- **EV deadline:** `GET /web/commands/current` plus the single bounded write
  `POST /web/commands/tesla`.

It does **not**:

- call Homey directly;
- write Easee or another physical device directly;
- own planner/control policy;
- add a generic HTTP write client;
- store the Tesla control-PIN in source code or `UserDefaults` / `AppStorage`.

The Pi remains command and validation authority.

## Canonical Xcode project

Open:

`apps/ios/EMSMobile/EMS.xcodeproj`

The project is repository-relative and contains no site-specific base URL or control
credential.

The API base URL remains operator-configured in
`@AppStorage("emsBaseURL")`. The Tesla control-PIN is stored separately in the
iOS Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`.

## Network boundary

The Pi Web Data API remains bound to loopback. Native mobile access uses the
existing private Tailscale-only Caddy ingress.

Observability path:

`SwiftUI -> Tailscale -> Caddy /api/mobile/* -> 127.0.0.1:3200`

Deadline path:

`SwiftUI -> Tailscale -> Caddy /web/commands/tesla -> 127.0.0.1:3100 -> existing Pi deadline builder/control chain`

Caddy restricts the write route to the tailnet. The Pi command ingress additionally:

- accepts the route only from its loopback reverse proxy;
- requires `X-Tesla-Control-Pin`;
- validates SOC, deadline and max current server-side;
- requires a UUID `clientRequestId`;
- applies idempotency handling;
- persists the command atomically;
- invokes the existing Pi deadline-state builder;
- performs no direct physical write itself.

The iOS client keeps the same `clientRequestId` when retrying an ambiguous failed
submission with unchanged intent.

## Deadline UX

v0.2 adds a dedicated **Deadline** tab.

The user enters:

- current SOC;
- target SOC;
- deadline date/time;
- maximum charge current (6–16 A).

Deadline time is encoded explicitly as **Europe/Amsterdam** local time, matching the
canonical Pi ingress contract even if the phone is used from another timezone.

Before submission the app shows an explicit confirmation. After submission it reads
back `/web/commands/current` and refreshes Mobile V1. A Pi response of
`PENDING_WATCHDOG` is shown as accepted/pending rather than falsely labelled as
already active.

Cancellation is a separate destructive action with its own confirmation.

## Dashboard

The dashboard continues to show:

- signed grid state plus explicit import/export;
- PV power and other-house load when available;
- EV connected/charging/current/deadline semantics;
- warm-water card only when the effective source is `BOILER`;
- Heating SHADOW state;
- Flex freshness/consistency;
- manager state.

Missing values are suppressed rather than invented.

## Transport hardening

The current tailnet path is private but uses HTTP at the Caddy layer. The app
therefore still uses the existing development ATS allowance while commissioning.
The transport itself remains inside encrypted Tailscale.

A later hardened release should move the private endpoint to trusted HTTPS and
remove the arbitrary-load ATS allowance. Port 3100 and port 3200 must never be
published directly.
