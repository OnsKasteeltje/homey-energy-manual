# Victron Schuurmonitor V0.1 — SHADOW commissioning

Status: candidate only; **not installed or promoted on the Raspberry Pi**.
Purpose: observe the 3-phase net power of the cable between house and shed.
The Victron VM-3P75CT is attached to the Cerbo GX over LAN (Modbus/UDP);
the Raspberry Pi reads the Cerbo GX **Modbus TCP server** only.

## Known physical quality issue (1 November 2026)
L1 and L3 power readings were checked and are useful; the L2 measurement is known faulty
and will be physically inspected next weekend. Do not publish 3-phase
total power, import/export, derived consumption, or any battery/EV control
from this meter until L2 is corrected and the full phase/direction test passes.

The candidate does not access or change the Pi planner, P1, canonical
`ems-history.sqlite`, Homey, Easee, or AlphaESS.

## Cerbo GX prerequisites
1. Settings → Integrations → Modbus TCP Server → Enable.
2. Set **Access permissions = Read only**.
3. Open **Available services**, find **com.victronenergy.acload**
   belonging to the VM-3P75CT; note its actual **Unit ID**.
   Do NOT assume Unit ID 100; that is normally the system service.
4. Note Cerbo GX LAN IP. Use DHCP reservation for stability if appropriate.
5. Restrict access to trusted LAN hosts where possible. Modbus TCP is not
   authenticated/encrypted; do not expose TCP/502 to the internet.

The AC-load map uses Modbus holding-register function FC03:
- 3900..3902 = L1/L2/L3 power W
- 3903..3909 = seven words of serial number, **NOT current**
- 3910 / 3912 / 3914 = phase voltages, uint16 / 10 V
- 3911 / 3913 / 3915 = phase currents, int16 / 10 A

On 2026-11-01 the first prototype misread serial register 3903 as
1851.3 A (ASCII "HQ" = 0x4851 = 18513), and 3905 as 1336.3 A
(ASCII "43" = 0x3433 = 13363). Those bytes exactly match the VM-3P75CT
serial prefix HQ2543. The GX UI displayed real plausible currents
L1 8.1 A and L3 6.6 A. The revised candidate reads correct current
registers and labels their quality PENDING_GUI_COMPARISON until a new
simultaneous live comparison. Current values are NOT yet stored in
SQLite; total power and L2 remain invalid.

Register mappings cross-checked with Victron's official register-list
documentation description and sfstar/hass-victron's published
AC-load register declarations. The exact live values still require
commissioning on this GX device.

The meter's own Ethernet
connection is Modbus/UDP; don't accidentally target it on TCP port 502.

## Dry-run on the Pi (no writes anywhere)
```bash
cd /home/jeroen/ems/repo/homey-energy-manual
python3 -m unittest discover -s tests/integrations -p 'test_victron_schuur_monitor.py' -v

CERBO_IP=192.168.X.Y
ACLOAD_UNIT_ID=40     # REPLACE with actual GX Available services Unit ID

python3 services/pi/integrations/victron/schuur_monitor.py \
  --host "$CERBO_IP" --unit-id "$ACLOAD_UNIT_ID"
```

Compare L1 and L3 reported **power, voltage, and current** with the Cerbo UI
at the same instant. Phase-current quality remains PENDING_GUI_COMPARISON
until validated. The screenshot at ~15:13 local had L1=1876W/8.1A,
L2=108W/2.5A/PF=0.182 (not accepted), L3=1531W/6.6A/PF=-0.995.
The negative L3 PF should receive a dedicated sign/direction check. Check sign direction with EV charge and high shed PV.
L2 remains unavailable even when a number comes back from the meter.

## Optional private shadow data collection (after successful dry-run)
```bash
python3 services/pi/integrations/victron/schuur_monitor.py \
  --host "$CERBO_IP" --unit-id "$ACLOAD_UNIT_ID" \
  --shadow-db /home/jeroen/ems/data/victron-schuur-shadow.sqlite \
  --json-out /home/jeroen/ems/data/victron-schuur-current.json
```

This stores only L1/L3 **power** in an independent SQLite file; the
private JSON includes unvalidated currents tagged PENDING_GUI_COMPARISON.
Do not run this optional persistence command until the interactive readback
has been checked against the Cerbo UI. There is no L2 column and no valid total.
The script fails visibly if Modbus is unreachable; no stale snapshot is
silently treated as fresh. A future consumer must gate on timestamp
freshness, quality, and both eligibleFor... flags.

## Next acceptance gates
- Confirm actual Cerbo IP, AC-load Unit ID and registers on the Pi.
- Review real sample units/signs, networking and sampling frequency.
- Add managed systemd service + timer and operational health only after
  successful manual commissioning; run read-only initially.
- After L2 physical repair: separately validate L2, phase alignment,
  direction and 3x16 A feeder context, then explicitly promote trusted
  totals and controlled integration into EMS history/API/dashboard.
- Nothing in V0.1 gives Victron battery/control authority; P1 remains the
  canonical full-house grid source.
