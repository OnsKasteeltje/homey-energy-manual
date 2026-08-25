---
title: Energy State v2 datamodel
version: 2.12
status: active
architecture_status: validated
last_verified: 2026-08-25
source:
  - Homey Advanced Flow: EM v2 | 04 Publisher | v1.0.4 (Tesla lifecycle)
  - docs/data/energy-state-v2.json
  - docs/data/energy-state-v2.schema.json
  - scripts/build_frontend_bundles.py
  - docs/javascripts/energy-core-v2-adapter-v2.8.93.js
  - docs/javascripts/live-energy-model-v2.js
---

# Energy State v2 datamodel

## 1. Doel

`EM2_Public_State` en het daaruit gepubliceerde `docs/data/energy-state-v2.json` vormen het publieke read-model tussen Homey Energy Core v2, de website/frontend en downstream SHADOW-consumenten zoals Power Intent.

Het model is revisioned en gebruikt momenteel `meta.schema_version = 2.12`.

## 2. Bronnen van waarheid

De contractketen is:

`Homey Core state -> EM2_Public_State -> Publisher -> docs/data/energy-state-v2.json -> Energy Core v2 frontend adapter -> view models/UI`.

De JSON Schema-definitie `docs/data/energy-state-v2.schema.json` is het formele frontendcontract. `scripts/build_frontend_bundles.py` leest daaruit minimaal `schema_version`, `publisher_version`, compatible major en compatible schema-versies en genereert `window.EnergyStateContract`.

## 3. Revision contract

De publieke payload bevat minimaal:

- `meta.state_revision`
- `meta.decision_revision`
- `meta.shadow_revision`

De frontend-adapter accepteert de payload alleen wanneer alle drie numeriek zijn en exact gelijk zijn. Een mismatch maakt de gehele Energy State-feed contractueel ongeldig.

Power Intent gebruikt aanvullend `meta.state_revision` als bronrevision en eist alignment met `EM2_State`, `EM2_Decision` en `EM2_Control_WW`.

## 4. Freshness contract

De frontend onderscheidt drie tijden:

- `meta.generated_at`: publicatiemoment;
- `meta.source_sample_at`: bron-sample waarop de state gebaseerd is;
- `meta.heartbeat_at`: publisher-heartbeat.

De actuele frontendgrenzen zijn:

- publicatie maximaal 15 minuten oud;
- source sample maximaal 15 minuten oud;
- heartbeat maximaal 45 minuten oud.

`feedFresh` vereist zowel een verse publicatie als een verse source sample. Heartbeat freshness wordt apart gebruikt voor health.

## 5. Top-level secties

De live schema-2.12 payload bevat de volgende belangrijke secties:

| Sectie | Rol |
|---|---|
| `meta` | schema, timestamps, revisions, publisher- en freshnessmetadata |
| `balance` | afgeleide huisbalans, source timing en control gates |
| `grid` | P1 netvermogen en fasevermogens |
| `pv` | totale en inverter-specifieke PV-productie |
| `battery` | toekomstige/actuele batterijstatus; nu `integrated=false` |
| `quatt` | directe/afgeleide ruimteverwarmingscontext |
| `energy_budget` | flex-export- en discretionary-importbudgetten |
| `tesla` | connectie, laadstatus, elektrisch context en deadline lifecycle |
| `equalizer` | Easee Equalizer-context |
| `hot_water` | boilerstatus, WW day state en WW control |
| `loads` | wasmachine, droger, vaatwasser, Quooker en uitbreidbare load-attributie |
| `manager` | Core manager state, decision, priority en publieke budgetten |

Het formele JSON Schema vereist momenteel `meta`, `balance`, `grid`, `pv`, `battery`, `energy_budget`, `tesla`, `hot_water`, `loads` en `manager`. `quatt` en `equalizer` zijn live aanwezig maar zijn nog niet als verplichte top-level schema-properties gemodelleerd; zij blijven geldig via `additionalProperties=true`.

## 6. Balance/control-gate semantiek

`balance.valid` en `energy_budget.balance_valid` zijn backwards-compatible aliases voor de geldigheid van de afgeleide huis/PV-reconstructie. Voor control is de belangrijke scheiding:

- `grid_measurement_valid`: P1/netmeting is bruikbaar voor import/export en flexbudget;
- `derived_house_balance_valid`: reconstructie van huis/rest/PV is bruikbaar;
- `fail_closed_flex_budget`: wordt alleen waar wanneer de P1/grid-gate faalt.

Daardoor mag stale of asynchrone PV-data diagnostische `Huis/Overig`-weergave blokkeren zonder verse P1-export-opportunity automatisch te blokkeren.

## 7. Frontend-consumptie

`energy-core-v2-adapter-v2.8.93.js` valideert vóór publicatie aan `EnergyStore`:

1. compatible schema-major/version;
2. aanwezigheid van `meta`, `grid`, `pv` en `battery`;
3. numerieke `grid.power_w`;
4. drie geldige en gelijke revisions.

`live-energy-model-v2.js` consumeert vervolgens onder meer:

- `grid.power_w`;
- `pv.total_w` en invertervelden;
- `battery.power_w`;
- `energy_budget.house_load_w`;
- `balance.physical_house_candidate_w`;
- `balance.control_gate.derived_house_balance_valid`;
- `tesla.power_w` en `tesla.connected`;
- `hot_water.boiler_power_w` en `hot_water.boiler_on`;
- `quatt.*`;
- `loads.washer`, `loads.dryer`, `loads.quooker`, `loads.dishwasher`.

Direct gemeten apparaatvermogens blijven geldig onafhankelijk van de afgeleide P1/PV-huisbalans. Alleen afgeleide `Huis/Overig`-waarden worden onderdrukt wanneer `derived_house_balance_valid=false`.

## 8. Load extensibility

Het schema definieert een generieke `$defs.load` met ten minste:

- `active`;
- `power_w`;
- `phase`;
- `measurement`.

Omdat `additionalProperties=true` geldt, kunnen runtime-detectors extra velden publiceren, bijvoorbeeld Quooker `switch_on`, `status`, `fresh`, baseline- en transitionmetadata. Frontendcode mag zulke extra velden gebruiken, maar moet ontbrekende optionele metadata fail-safe behandelen.

## 9. Schema-compatibiliteit

De frontend accepteert expliciet schema-versies `2.10`, `2.11` en `2.12`, en daarnaast dezelfde major `2.x`. Een toekomstige breaking change moet daarom een major-versie verhogen; additive velden binnen 2.x moeten backwards compatible blijven.

## 10. Bekende inconsistentie

De live Homey Publisher heet `EM2_PUBLISHER_V1.0.4`, maar schrijft momenteel bewust/feitelijk nog `meta.publisher_version = EM2_PUBLISHER_V1.0.3`. Het JSON Schema heeft eveneens `EM2_PUBLISHER_V1.0.3` als `const`, waardoor runtime en frontendcontract technisch consistent zijn, maar de metadata niet overeenkomt met de werkelijke flowversie.

Dit moet bij een gecontroleerde Publisher-release in één change worden aangepast in:

1. Homey Publisher payload;
2. `energy-state-v2.schema.json`;
3. gegenereerde `energy-contract-v2.generated.js`;
4. opnieuw gebouwde frontend bundle.

Alleen de Homey-string wijzigen zou het frontendcontract inconsistent maken en is daarom niet toegestaan.

## 11. Wijzigingsregel

Elke wijziging aan een publiek veld dat door website, Power Intent of een andere consumer wordt gebruikt vereist minimaal:

- schema-impact bepalen;
- producer en consumers in dezelfde change beoordelen;
- compatible/additive versus breaking expliciet classificeren;
- frontend contract opnieuw genereren wanneer schema-consts wijzigen;
- runtime JSON tegen het schema valideren;
- deze datamodeldocumentatie en relevante Mermaid-flows opnieuw verifiëren.
