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

The app stores its API base URL in `@AppStorage("emsBaseURL")`. The initial value is:

`http://192.168.1.42`

The app itself always appends:

`/api/mobile/v1/overview`

## LAN networking

The Pi Web Data API itself remains intentionally bound to `127.0.0.1:3200`.
The iPhone must therefore use the existing private gateway/reverse-proxy boundary,
not port 3200 directly.

Before device testing, prove that this URL is reachable from the Mac/iPhone LAN:

`http://192.168.1.42/api/mobile/v1/overview`

If the private gateway uses another scheme/host, enter that base URL under
**Instellingen** in the app.

For local-network development, Xcode may require an Info.plist local-network usage
description and an App Transport Security allowance if plain HTTP is used. Prefer
the existing private HTTPS boundary when available; do not expose port 3200 to the
internet.

## First UI

The first native dashboard shows:

- signed grid state plus explicit import/export;
- PV power and other-house load when available;
- EV connected/charging/current/deadline semantics;
- warm-water mode, boiler state and seasonal advice;
- Heating SHADOW state;
- Flex status, including `STALE` / `INCONSISTENT`;
- manager status;
- explicit read-only / no-write capabilities.

The UI deliberately suppresses missing values rather than inventing them.
