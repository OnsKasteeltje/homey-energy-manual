# AlphaESS VitaPower 3600 AC — Pi interface V0.1

**Repository status: READ_ONLY / SHADOW, manual execution only (14 November 2026).**
The 8 kWh VitaPower (Master + VitaMate 4000), AlphaESS P1, 3600 W activation and autonomous PV-surplus charging/grid-import discharging have been commissioned physically. This repository integration is **not deployed or scheduled in production**. Installation/Modbus verification is not EMS promotion.

## Authority and physical network

- **AlphaESS** is the only autonomous realtime charge/discharge optimizer and BMS/safety authority. Keep its existing P1 meter and reserve policy.
- **HomeWizard P1** remains the household grid import/export authority; AlphaESS battery observations must not overwrite P1 or be interpreted as solar generation.
- **Raspberry Pi** owns local Modbus observation and later analysis; **Homey** is not a second battery controller.
- **Victron Cerbo GX / VM-3P75CT** independently observe the shared three-phase shed feeder, not battery power in isolation.
- Local Modbus TCP has been verified through the VitaPower's *physical Ethernet port*, bridged via the existing U6 Lite wireless mesh/PoE injector to the home LAN. The wifi communication module's address did not expose port 502.
- Use **one Pi-owned Modbus client** only; rapid new TCP connections sometimes return Connection refused.

Private host addresses and any future secrets belong in host-local settings, **never** in the public repository. Do not publish battery serials, owner identifiers, network inventory or household telemetry to GitHub.

## Confirmed read-only register map

Register definitions: *AlphaESS - Alpha Micro Modbus Register Reference*, pp. 3–9. Firmware on the physical device was observed as inverter V3.05.011 / EMS V1.01.24CFU. Not every field in the general Alpha Micro document is necessarily valid on this firmware.

| Hex register | Metric | Scale / meaning | Verified evidence |
| --- | --- | --- | --- |
| 0102 | SOC | 0.1% | exact Energy Life match: 61.2% |
| 0118 | Battery num | count | 2 |
| 0119 | Battery capacity | 0.1 kWh | 8.0 kWh nominal |
| 011B | SOH | 0.1% | BMS reported 100%, not measured usable capacity |
| 0120–0121 | Charge energy | unsigned 32, 0.1 kWh | 44.4 kWh reported |
| 0122–0123 | Discharge energy | unsigned 32, 0.1 kWh | 38.7 → 39.2 kWh while discharging |
| 0124–0125 | Charge-from-grid energy | unsigned 32, 0.1 kWh | **UNVERIFIED** (49.3 > charge 44.4) |
| 0126 | Battery DC power | signed 16, W; positive discharge | +862 W |
| 040C–040D | Inverter total AC power | signed 32, W | +798 W vs ~800 W Energy Life two minutes later |

The normal (high-word first) 32-bit word order is plausible; swapped-word interpretations were unrealistic. AC-power sign while **charging** and device cumulative counter reset behaviour still require explicit testing.

The DC charge/discharge counters are not verified AC delivered-energy counters. For battery usable AC capacity, use a quality-gated time-integral of signed AC power over a measured SOC interval **after charge-direction verification**. A 100% SOH reading does not prove 8 kWh usable AC capacity.

## Interface implementation

Source: services/pi/integrations/alphaess/collect_readonly.py

- Protocol **Modbus TCP unit 85, function 03 only**; no Modbus writes, no device-control APIs, no systemd unit.
- Reads 0x0102 (37 registers) and 0x040C (2 registers) on **one** connection. Missing or invalid replies return unavailable/null data; no last-known data is silently treated as fresh or zero.
- Schema: EMS_PI_ALPHAESS_MODBUS_READONLY_V0.1; eligibleForControl=false, eligibleForHouseBalance=false, controlWrites=false, readOnly=true.
- sampledAtUtc is the **Pi polling time**, not a device-supplied timestamp. quality=OBSERVED_PI_POLL_TIME identifies that limitation.
- gridChargeReportedKWh is visible for diagnosis but excluded from the archive until its semantics are independently confirmed.
- Only opt-in --archive-db appends eight isolated metrics for device key battery_alphaess to the **existing** EMS SQLite database. It creates no extra database or historical reprocessing, is idempotent for the same timestamp, and does not affect existing Homey Core ingest or household-energy computations.

### Manual invocation from repo checkout

Run with a private LAN address resolved on the Pi (placeholder):

~~~bash
python3 services/pi/integrations/alphaess/collect_readonly.py --host YOUR_VITAPOWER_LAN_IP
python3 tests/integrations/alphaess/test_alphaess_readonly.py
~~~

**Do not pass --archive-db yet in production** until the snapshot/quality contract and interaction with the live 15-minute historian have been accepted separately. Its opt-in use is provided for isolated test databases first. No polling daemon or automatic run should be enabled as part of merging this PR.

If the TCP socket refuses a connection, record the failure and retry later as a deliberate separate check rather than creating parallel clients or tight loops. Do not reset the battery or relax safety limits just to get an observation.

## Controlled future commissioning

1. Review this PR as one atomic change on main, run targeted tests, repository gate and architecture gate. No failed CI gate may be bypassed.
2. Confirm source ↔ deployed Pi branch, uncommitted changes and drift before *any* deployment.
3. After approval, add an explicit source-to-runtime mapping, safe backup, drift check and optional disabled-by-default systemd timer/service in a **separate** controlled release. A GitHub merge does not deploy to the Pi.
4. Run sustained read-only tests for reconnect contention, charging-direction sign, AC energy integration, counter monotonicity and fault/temperature evidence. Missing data remains UNKNOWN and does not enter the planner.
5. Evaluate separately whether read-only evidence may enter household-energy accounting. The existing import + PV - export derivation is not sufficient to distinguish battery charging and discharging from genuine end-use consumption.
6. Any future strategic dispatch is a **different**, explicitly approved boundary with a sole owner, write gate, bounded priorities, safe SoC reserve, watchdog and autonomous fallback. This V0.1 contains **no writes**.

## Related governance

- docs/architecture/CURRENT-EMS-STATE.md — current battery boundary.
- docs/architecture/repository-structure.md — touch-it/place-it.
- docs/architecture/diagnostic-source-of-truth.md — diagnostic authority.
- CONTRIBUTING.md — atomic release + risk-driven regression.
