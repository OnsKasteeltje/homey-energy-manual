# Victron Schuurmonitor V0.1 — SHADOW commissioning

Status: candidate only; **not installed or promoted on the Raspberry Pi**.
Purpose: observe the 3-phase net power of the cable between house and shed.
The Victron VM-3P75CT is attached to the Cerbo GX over LAN (Modbus/UDP);
the Raspberry Pi reads the Cerbo GX **Modbus TCP server** only.

## Known physical quality issue (1 November 2026)
L1 and L3 were checked and are useful; the L2 measurement is known faulty
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

The AC-load map uses holding-register function 03, addresses 3900..3902
for phase powers (signed W), 3903..3905 for signed phase currents
(scale 0.1 A), subject to comparison with the current official Victron
register list and a real-device readback. The meter's own Ethernet
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

Compare L1 and L3 reported power/current with the Cerbo UI at the
same instant. Check sign direction with EV charge and high shed PV.
L2 remains unavailable even when a number comes back from the meter.

## Optional private shadow data collection (after successful dry-run)
```bash
python3 services/pi/integrations/victron/schuur_monitor.py \
  --host "$CERBO_IP" --unit-id "$ACLOAD_UNIT_ID" \
  --shadow-db /home/jeroen/ems/data/victron-schuur-shadow.sqlite \
  --json-out /home/jeroen/ems/data/victron-schuur-current.json
```

This stores only L1/L3 power and current in an independent SQLite file
and a private JSON snapshot. There is no L2 column and no valid total.
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
