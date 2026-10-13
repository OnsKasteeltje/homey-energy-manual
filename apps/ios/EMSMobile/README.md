# EMS Mobile v0.1

Native SwiftUI read-only client for the Pi Mobile API V1.

## Scope

- reads only `GET /api/mobile/v1/overview`;
- no Homey calls;
- no planner/control writes;
- no physical writes;
- manual/pull-to-refresh only in v0.1.

## Xcode bootstrap

1. On the Mac, open Xcode and create a new **iOS App** project.
2. Product name: `EMSMobile`.
3. Interface: **SwiftUI**.
4. Language: **Swift**.
5. Deployment target: iOS 17 or newer.
6. Replace the generated app/content source with the files in this folder and add:
   - `Models/MobileOverview.swift`
   - `Services/EMSAPIClient.swift`
   - `Store/OverviewStore.swift`
7. Build once in the Simulator.

The app stores its API base URL in `@AppStorage("emsBaseURL")`. The initial value is intentionally empty. On first launch, enter the private
EMS gateway base URL under **Instellingen**. Do not commit site-specific
addresses, access tokens, or credentials to this public repository.

The app itself always appends:

`/api/mobile/v1/overview`

## LAN networking

The Pi Web Data API itself remains intentionally bound to `127.0.0.1:3200`.
The iPhone must therefore use the existing private gateway/reverse-proxy boundary,
not port 3200 directly.

Before device testing, verify that `GET /api/mobile/v1/overview` is reachable
through the private Tailscale gateway from a tailnet client; do not publish that API
to the internet.

If the private gateway uses another scheme/host, enter that base URL under
**Instellingen** in the app.

For the current private Tailscale path, the app uses the operator-configured private
tailnet gateway. The transport remains inside the encrypted tailnet, but iOS App
Transport Security does not infer that when the Caddy layer uses plain HTTP. For v0.1 device testing, add the development-only
Info.plist setting `NSAppTransportSecurity -> NSAllowsArbitraryLoads = YES`. Keep
this scoped to the current private read-only prototype. A later hardened release
should move the app endpoint to trusted HTTPS over the tailnet and remove this
allowance. Port 3200 must never be exposed directly.

## First UI

The first native dashboard shows:

- signed grid state plus explicit import/export;
- PV power and other-house load when available;
- EV connected/charging/current/deadline semantics;
- warm-water card only when the effective source is `BOILER`; it is hidden for `CV` or unknown source;
- Heating SHADOW state;
- Flex status, including `STALE` / `INCONSISTENT`;
- manager status;
- explicit read-only / no-write capabilities.

The UI deliberately suppresses missing values rather than inventing them.


The overview header formats `generatedAt` as local device time rather than exposing the raw ISO timestamp.
