# Energie Manager PV

**Status:** 🟡 Actief in shadow mode  
**Flow:** `Energie Manager PV - Shadow Mode`

De flow draait iedere 2 minuten en stuurt geen apparaten aan.

## Berekening

```text
PV beschikbaar = max(0, -P1 + werkelijk Tesla-vermogen + werkelijk boilervermogen)
```

## Tesla-prioriteit

| Beschikbaar PV | Shadow-doel |
|---:|---:|
| < 4.140 W | 0 A |
| 4.140–4.829 W | 6 A |
| 4.830–5.519 W | 7 A |
| 5.520–6.209 W | 8 A |
| 6.210–6.899 W | 9 A |
| 6.900–7.589 W | 10 A |
| ≥ 7.590 W | 11 A |

Boiler wordt alleen toegestaan als na Tesla-reservering minimaal circa **2,1 kW** resteert.

## Shadowstate
Iedere 2 minuten wordt lokaal een sample toegevoegd aan `EM_SHADOW_STATE`. Er worden maximaal 720 lokale samples bewaard, ongeveer 24 uur.

Voor de website wordt de lokale state niet meer als geheel vanuit een andere flow uitgelezen. Ongeveer iedere 15 minuten schrijft dezelfde scriptkaart één actueel sample rechtstreeks bij in:

`docs/data/shadow-baseline-v01.json`

De GitHub-JSON vormt daarmee een aparte persistente websitehistorie van maximaal 720 gepubliceerde samples.

## Volgende versie
`Energie Manager PV - Shadow Mode v0.2 Quooker` voegt Quooker-context, Tesla-sessieregistratie en de warmwatergarantie van 240 minuten vóór 19:00 toe. Deze versie publiceert na activatie op dezelfde manier naar `docs/data/shadow-v02-quooker.json`.
