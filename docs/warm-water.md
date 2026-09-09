# Warm water — Energy Core v2

**Status:** bronkeuze `BOILER ↔ CV` is productie-actief en E2E gevalideerd.  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.10.12 (WW post-goal SHOULD)`  
**Settings sync:** `EM v2 | 05 Config | EMS Settings Sync v0.2`  
**Fysieke v2-boilerwriter:** nog SHADOW / niet vrijgegeven.

## Bronkeuze op de website

De Live View bevat een EMS-instelling voor de warmwaterbron:

- **Boiler** → `hotWaterSource = BOILER` → Homey `WW_Boilermodus = true`;
- **CV** → `hotWaterSource = CV` → Homey `WW_Boilermodus = false`.

De selector is zelf de opdracht. Er is geen aparte knop *Instellingen opslaan* meer. Een wijziging start direct dezelfde beveiligde PIN-route als Tesla deadline laden. Bij annuleren of een mislukte write wordt de UI teruggezet naar de laatst bevestigde waarde.

## E2E write-route

```text
Website selector
      │
      ▼
control-PIN
      │
      ▼
Cloudflare Worker
      │
      ▼
docs/data/ems-settings-command.json
      │
      ▼
EM v2 | 05 Config | EMS Settings Sync v0.2
      │
      ▼
WW_Boilermodus
      │
      ▼
Energy Core v2
      │
      ▼
Publisher / energy-state-v2.json
      │
      ▼
Website bevestigde runtime-status
```

Settings Sync v0.2 leest de opdracht primair via de authenticated GitHub Contents API met `GH_Status_Token`; de raw GitHub-route is alleen fallback. Hiermee wordt voorkomen dat een recente bronkeuze door raw-content caching achterloopt.

De route is op 23 augustus 2026 live in beide richtingen gevalideerd:

```text
BOILER → CV     ✓
CV → BOILER     ✓
```

De bevestigde eindstatus na de test is **BOILER** (`hot_water.mode = true`).

## Gedrag van Core

Core gebruikt `WW_Boilermodus` rechtstreeks als `state.hotWater.mode`.

### CV geselecteerd

```text
mode = false
→ elektrische boilerregeling geblokkeerd
→ opportunity = BLOCKED_MODE
→ geen BOILER_ON-intent
```

Als de boiler nog fysiek aan zou staan terwijl CV wordt gekozen, is de veilige gewenste actie `BOILER_OFF`. De fysieke v2-writer blijft echter afzonderlijk beheerd en is nog niet als productie-writer vrijgegeven.

### Boiler geselecteerd

```text
mode = true
→ normale warmwaterpolicy actief
→ timing, dagdoel, catch-up en opportunities worden beoordeeld
```

Na 19:00 wordt geen nieuwe elektrische warmwater-run gestart. Tijdens de E2E-retourtest naar Boiler was daarom terecht zichtbaar:

```text
mode        = true
opportunity = AFTER_DEADLINE
reason      = Na 19:00 geen elektrische warmwater-run
```

Dit betekent: **Boiler is geselecteerd**, maar de tijdpolicy verhindert een nieuwe run.

## Dagdoel en post-goal gedrag

Het primaire comfortdoel blijft dat de elektrische boiler eenmaal per lokale kalenderdag aantoonbaar `OP_TEMPERATUUR` bereikt. `goalReachedToday` blijft daarna voor die kalenderdag gelatcht.

Na het bereiken van het dagdoel:

- vervalt de MUST/fallback-verplichting;
- een gevalideerde post-goal opportunity vóór 19:00 mag maximaal `SHOULD` zijn;
- een post-goal opportunity wist de daglatch nooit;
- na 19:00 geldt `AFTER_DEADLINE`.

De fallback telt bevestigde verwarmingsminuten en niet alleen relais-aan-tijd:

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

Als `OP_TEMPERATUUR` al is bereikt, wordt de fallbackverplichting voor die dag beëindigd.

## Contracttype

Dezelfde EMS-instellingenroute beheert ook:

```text
FIXED | DYNAMIC → EMS_ContractType
```

Warmwaterbron en contracttype zijn afzonderlijke instellingen. `BOILER/CV` bepaalt welke warmwaterbron operationeel geldt; `FIXED/DYNAMIC` bepaalt welke economische prijscontext gebruikt mag worden.

Bij `FIXED` mogen legacy dynamische `M7_Price_*`-signalen geen productie-aansturing veroorzaken. Contract-aware prijslogica loopt via de geïsoleerde `EM2_ContractPrice_*` context.

## Test- en synchronisatieleerpunt

Een handmatige `start_flow()` bevestigt dat een Homey-flow gestart is, niet dat die volledig afgerond is voordat een volgende handmatige flow wordt gestart. Voor E2E-validatie van de keten `Settings Sync → Core → Publisher` moet daarom op de nieuwe runtime-state/revision worden gewacht in plaats van flows direct na elkaar als synchroon te beschouwen.

## Veiligheidsgrenzen

- Website schrijft geen Homey-devicewaarden rechtstreeks.
- PIN-beveiligde settings gaan via Cloudflare en het commandbestand.
- Core blijft eigenaar van de warmwaterbeslissing.
- Per fysieke actuator blijft exact één gevalideerde writer het architectuurdoel.
- Lokale installatie- en apparaatveiligheid staat altijd boven EMS-optimalisatie.

> **Laatste E2E-status 23 augustus 2026:** bronselector in beide richtingen gevalideerd; systeem staat bevestigd terug op **Boiler**.
## Pi historical hot-water demand model

The Pi stores hot-water boiler observations in the canonical SQLite history database:

`/home/jeroen/ems/data/ems-history.sqlite`

The processing chain is:

`Homey Insights → measurements → measurements_15m → daily_energy_history`

Daily boiler energy is reconstructed resolution-aware. Where source intervals overlap,
the finest available resolution is used. Homey weekly aggregates are deliberately
excluded from daily reconstruction; source data up to six-hour resolution may be used
for daily totals and long-term demand analysis.

`daily_energy_history` records, among other fields:

- local calendar date
- daily energy in kWh
- coverage percentage
- finest source resolution used
- coarsest source resolution used
- quality (`complete`, `usable`, or `partial`)

The validated complete-day history currently supports the following weekday median
hot-water energy demand model:

| Day | Median |
| --- | ---: |
| Monday | 5.8 kWh |
| Tuesday | 4.5 kWh |
| Wednesday | 6.3 kWh |
| Thursday | 7.0 kWh |
| Friday | 5.9 kWh |
| Saturday | 7.7 kWh |
| Sunday | 7.7 kWh |

These values are currently used as a **shadow forecast only** under source
`WEEKDAY_MEDIAN_SQLITE_V0.2`.

Production planning remains based on `WW_EXPECTED_DAILY_KWH = 6.0 kWh` until the
weekday model has been validated against actual boiler consumption and PV utilisation.

WW forecast snapshots are persisted in SQLite table `forecast_ww_daily`, allowing
forecast-versus-actual backtesting.

The 240-minute planner fallback corresponds to approximately 7.6 kWh at the nominal
1.9 kW boiler load. It is a planning/fallback parameter and must not be interpreted
as a physical maximum daily boiler-energy consumption.
