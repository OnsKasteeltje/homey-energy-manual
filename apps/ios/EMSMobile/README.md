# EMS Mobile v0.2

Native SwiftUI client for private EMS observability plus one bounded EV deadline command.

## Scope

The app deliberately keeps two paths separate:

- `GET /api/mobile/v1/overview` for read-only observability;
- `GET /web/commands/current` plus `POST /web/commands/tesla` for the existing EV deadline command.

There is no generic mobile write API. The app does not call Homey or Easee directly,
does not own planner policy and does not create a second command source.

## Canonical Xcode project

Open `apps/ios/EMSMobile/EMS.xcodeproj`.

The EMS base URL remains operator-configured in `@AppStorage("emsBaseURL")`.
No site-specific address or credential is committed to Git.

## Deadline KISS flow

The Deadline tab contains only:

- current SOC;
- target SOC;
- deadline date/time;
- maximum current (6–16 A).

On submit or cancel the app shows one confirmation sheet and asks for the existing
Tesla control PIN. The PIN lives only in transient SwiftUI state for that confirmation,
is sent once in `X-Tesla-Control-Pin`, and is immediately cleared. It is not stored by
the app.

The app sends the same command contract as private Invoer V2:

`SwiftUI -> Tailscale -> Caddy /web/commands/tesla -> Pi Status API -> canonical deadline command/state -> normal Homey/Easee chain`

The Pi remains authoritative for future-deadline, SOC, max-current and command validation.
Deadline text is encoded as Europe/Amsterdam local time to match the existing Pi ingress.

Each intent gets a UUID `clientRequestId`. If the same intent is retried after an
ambiguous failure, the app reuses that UUID; changing the intent generates a new one.

After a successful POST the app reads `/web/commands/current` and refreshes Mobile V1.
`PENDING_WATCHDOG` is shown as accepted/pending, not as proof that execution is active.

## Network boundary

The private app uses the same Tailscale-only Caddy origin as the private EMS website.
Port 3100 and port 3200 remain internal/loopback service boundaries and must not be
published directly. Mobile API V1 remains read-only.

The current tailnet Caddy origin uses HTTP inside encrypted Tailscale, so the existing
development ATS allowance remains required while commissioning. Moving to trusted HTTPS
is a separate hardening step and must not create a public or second LAN ingress.
