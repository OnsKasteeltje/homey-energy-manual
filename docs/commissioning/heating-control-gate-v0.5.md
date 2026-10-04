# Heating Control Gate V0.5 SHADOW commissioning

**Status:** commissioning shadow  
**Control impact:** none  
**Physical writes:** forbidden  
**Canonical source:** `services/pi/control/heating/`

V0.5 proves the control/rollback contract before any Heating Pi->Homey transport
or Honeywell actuator exists.

```text
Honeywell -> room model -> V0.2 -> V0.3 -> Flex Priority -> V0.4
                                                    |
                                                    v
                                     V0.5 Control Gate SHADOW
                                                    |
                                                   -X-
                                     no Homey / no Honeywell write
```

Per room it emits `HOLD`, `WOULD_SET_TEMP`, `WOULD_KEEP_TEMP` or
`WOULD_RESET_TO_SCHEDULE`. Reset is ownership-bounded: it is proposed only
when the same V0.5 shadow previously simulated ownership. Shadow ownership is
not physical proof.

LIVE promotion requires a separate Pi->Homey contract, Homey translation
adapter and gate, exactly one Honeywell writer, acknowledgement/readback,
idempotent set/reset behaviour, health/alerting and rollback validation.
At LIVE cutover this commissioning shadow must be promoted or retired/archived;
it must not remain as a parallel controller.
