# Runtime-status Energy Core v2 - 20 augustus 2026

Dit document legt de actuele, runtime-gevalideerde referentie vast en heeft voor versienummers voorrang op oudere architectuurpagina's.

## VERIFIED runtime

Laatste gecontroleerde publicatie in `docs/data/energy-state-v2.json`:

- `publisher_version = EM2_CORE_PUBLISH_V0.10.4`
- `schema_version = 2.10`
- `control_mode = SHADOW`
- `state_revision = decision_revision = shadow_revision = 924`
- publicatiecadans: minimaal 300 s

## Meetgeldigheid

Core v0.10.4 splitst de geldigheid van de directe netmeting en de afgeleide huis/PV-balans:

- `grid_measurement_valid = true` wanneer P1 vers en bruikbaar is;
- `derived_house_balance_valid` kan onafhankelijk `false` zijn bij stale/skewed PV-bronnen;
- P1 blijft in dat geval autoritatief voor netimport/-export en flexbudget;
- een ongeldige afgeleide balans is diagnostiek en maakt betrouwbare P1-data niet indicatief of ongeldig.

De gecontroleerde sample had `balance.reason = SOURCE_SKEW`, doordat PV-bronnen onderling te oud/verschoven waren, terwijl P1 vers bleef. Daarom bleef `flex_budget_source = P1_NET_EXPORT` correct actief.

## Actuele componentstatus

- Quatt: `COMFORT_BASELOAD`, `OBSERVE_ONLY`, niet fysiek regelbaar.
- Warm Water Control: `EM2_CONTROL_WW_V0.11`, `SHADOW`, read-only.
- Warmwaterstate: `EM2_WW_STATE_V0.8`.
- Victron-batterij: nog niet geïntegreerd (`battery.integrated = false`).
- Wasmachine en droger: directe AEG-status beschikbaar; idle-status wordt als `AEG_DIRECT_IDLE` gepubliceerd en niet als geschat apparaatvermogen.
- Quooker: waar geen directe vermogensmeting beschikbaar is kan een expliciet gemarkeerde P1-signatuur worden gebruikt (`inferred = true`).

## Documentatieconsequentie

Oudere pagina's die nog Core v0.9.7/schema 2.5 als 'actief' noemen, beschrijven een eerdere gevalideerde toestand. Voor actuele runtimeversies geldt dit document plus de actuele `energy-state-v2.json` als waarheid. De architectuurprincipes uit die oudere documenten blijven alleen geldig voor zover ze niet door deze runtime-status of `project-baseline.md` zijn vervangen.
