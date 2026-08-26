---
component: planner-power-intent
title: 24h Energy Planner and Power Intent
status: shadow
architecture_status: implemented-shadow
last_verified: 2026-08-26
sources:
  - Homey Advanced Flow: EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | WW Power v0.1 SHADOW
  - Homey Advanced Flow: EM v2 | 60 Adapter | Actuator Commands v0.2 SHADOW
---

# 24h Energy Planner and Power Intent

## 1. Doel

Deze laag vertaalt EMS-policy naar actuator-neutrale intent en vervolgens via apparaatadapters naar een theoretisch fysiek uitvoerbare opdracht. De kernarchitectuur is:

`EMS policy -> Power Intent -> EV_target_W / WW_target_W-or-intent -> EV/WW Power Adapter -> Easee/Boiler`

De huidige adapterketen is SHADOW. Zij publiceert input, mapping en berekende output, maar neemt de fysieke writer-boundary nog niet over.

## 2. Architectuurgrens

Verantwoordelijkheden zijn strikt gescheiden:

- **EMS policy / Energy Core** bezit policy, prioriteit, MUST/opportunity-arbitrage, hysterese en economische beslissing;
- **Power Intent** projecteert die beslissing naar actuator-neutrale doelen;
- **EV Power Adapter** vertaalt `EV_target_W` naar een veilige, theoretisch uitvoerbare Easee-opdracht;
- **WW Power Adapter** vertaalt WW-intent naar een veilige, theoretisch uitvoerbare boileropdracht;
- **writer lifecycle** bezit commanded/confirmed tracking, idempotency, dedupe, run-lease, retries en throttling;
- **Easee en Boiler** mogen uiteindelijk elk slechts één actieve fysieke writer hebben.

Adapters mogen geen nieuwe EMS-policy introduceren en mogen een upstream toegewezen vermogensbudget nooit verhogen.

## 3. 24h Energy Planner v0.2 SHADOW

De planner draait iedere 15 minuten met 45 seconden vertraging en kan handmatig gestart worden. Hij adviseert over tijdslots, maar bepaalt geen apparaat-specifieke runtime-setpoints.

### 3.1 Simulatiescenario

Het huidige vaste SHADOW-scenario is Victron MultiPlus-II 48/5000/70-50 met 3 x Pylontech US5000, 14.4 kWh nominaal, SOC-band 20-90%, 3.3 kW AC charge/discharge, 95% charge- en discharge-efficiency en 90.25% round-trip efficiency. Dit zijn simulatie-aannames, geen commissioningwaarden.

### 3.2 Tesla

Bij een actieve Tesla-deadline gebruikt de planner de bestaande deadline/latest-start als hard planningsvenster en rangschikt prijs-slots binnen dat venster. Hij verzint geen laadvermogen of throughput.

### 3.3 Warm water

Voor warm water gebruikt de planner het gemodelleerde boilerniveau van circa 1.9 kW. Het resterende fallback-volume wordt omgerekend naar kWh en verdeeld over goedkope 15-minutenslots vóór 19:00.

### 3.4 Batterij

Batterijplanning is theoretisch. Zonder actuele SOC, gedetailleerde base-load en echte 15-min PV-forecast mag `theoreticalUpperBoundEuro` niet als gerealiseerde besparing worden geïnterpreteerd.

## 4. Power Intent v0.2 SHADOW

Power Intent wordt getriggerd door wijziging van `EM2_Public_State` en is idempotent per source revision. Voor geldige output moeten Public State revision, Core State revision, Decision sourceRevision en WW Control sourceRevision gelijk zijn.

Bij mismatch is `valid=false`, `status=REVISION_MISMATCH` en het EV-doel fail-closed 0 W.

## 5. EV-target contract

Power Intent maakt `targets.ev.target_W` op basis van de bestaande Core Decision.

### Deadline

Bij `TESLA_CHARGE_DEADLINE` geldt, indien resterende energie en toekomstige deadline geldig zijn:

`target_W = remaining_kWh / hours_to_deadline * 1000`

### Export-opportunity

Bij `TESLA_CHARGE_OPPORTUNITY` met minimaal 800 W flexbudget:

`target_W = flexExportBudget_W`

### Prijs-opportunity

Als geen exportbudget beschikbaar is maar prijs negatief/goedkoop is:

`target_W = discretionaryImportBudget_W`

### Geen geldige opportunity

Dan is `target_W = 0`.

Power Intent converteert niet naar ampère. Elektrische feasibility en clamping horen bij de EV Power Adapter.

## 6. WW-target contract

De architectuur gebruikt conceptueel `WW_target_W` als actuator-neutraal vermogensdoel voor numerieke warmwatersturing. De **huidige Power Intent v0.2 produceert dit nog niet numeriek**; de live interface is:

- `BOILER_ON -> target_on=true`
- `BOILER_OFF -> target_on=false`
- `HOLD -> target_on=null`

Daarom geldt tijdens deze overgang:

`EMS policy -> Power Intent -> WW target_on -> WW Power Adapter -> shadow boiler command`

Wanneer een toekomstige producer `WW_target_W` invoert, moet dit als expliciete schemawijziging met revision/schema-validatie worden geïntroduceerd. De adapter mag niet zelf uit policy een watt-target verzinnen.

## 7. EV Power Adapter v0.1 SHADOW

De EV-adapter accepteert `EM2_POWER_INTENT_V0.2` en voert uitsluitend deterministische apparaatvertaling uit. Hij leest geen policy uit devices en voert geen fysieke Easee-write uit.

De elektrische topologie is 3 fasen, 230 V per fase, minimaal 6 A, maximaal de geconfigureerde veilige stroom met harde bovengrens 16 A, zonder automatische 1↔3-faseschakeling.

`theoretical_A = EV_target_W / (3 × 230)`

`requested_A = floor(theoretical_A)`

Daarna volgt veilige clamping. Als `requested_A < 6 A`, wordt `requested_A=0`. Er wordt nooit omhoog afgerond naar het minimale laadvermogen.

De adapter valideert revision/schema alignment, freshness, numerieke constraints en charger-beschikbaarheid. Bij stale of ongeldige input valt hij fail-closed terug naar 0 A.

De output scheidt `requested_A`, `commanded_A` en `confirmed_A`. In SHADOW blijft `commanded_A=null`.

Een toekomstige LIVE-cut-over mag uitsluitend Easee dynamic/volatile current-control gebruiken; persistente chargerinstellingen met flash-wear-risico zijn geen EMS-runtimewriter.

## 8. WW Power Adapter v0.1 SHADOW

De WW Power Adapter vormt dezelfde architectuurgrens voor de boiler als de EV Power Adapter voor Easee. Hij accepteert uitsluitend de upstream WW-intent van Power Intent en bevat geen eigen EMS-policy, prijsbeslissing, opportunityselectie of deadline-arbitrage.

De adapter moet minimaal:

- source schema en revision alignment valideren;
- freshness van de control-input bewaken;
- `target_on=true/false/null` deterministisch vertalen naar respectievelijk ON/OFF/HOLD shadow command;
- HOLD onderscheiden van OFF zodat afwezigheid van een nieuwe opdracht niet als uitschakelopdracht wordt geïnterpreteerd;
- requested, commanded en confirmed state gescheiden houden;
- dedupe/idempotency toepassen voordat een toekomstige writer wordt aangeroepen;
- fail-closed reageren op ongeldige/stale control-input;
- `deviceWrites=false` behouden zolang SHADOW actief is.

Wanneer `WW_target_W` later numeriek wordt ingevoerd, wordt elektrische mapping onderdeel van deze adapter, niet van Energy Core of Power Intent. Tot die tijd blijft de binaire interface de feitelijke runtimewaarheid.

De bestaande boilerproductiewriter blijft fysieke eigenaar totdat de WW Adapter-validatiegate en atomic cut-over expliciet zijn geslaagd.

## 9. Generieke Actuator Commands v0.2 SHADOW

Actuator Commands accepteert de overgangsschema's `EM2_POWER_INTENT_V0.1` en `EM2_POWER_INTENT_V0.2`, publiceert `EM2_ACTUATOR_COMMANDS_V0.2` en dedupliceert op source revision én input schema.

EV-elektrische vertaling wordt gedelegeerd aan de EV Power Adapter. WW-vertaling wordt gedelegeerd aan de WW Power Adapter. Batterij blijft SHADOW/NOT_INTEGRATED.

## 10. End-to-end actuatorarchitectuur

De softwarearchitectuur is voor EV en warm water symmetrisch:

`EMS policy -> Power Intent -> actuator target -> Device Power Adapter -> writer lifecycle -> physical actuator`

Voor EV:

`Energy Core -> Power Intent -> EV_target_W -> EV Power Adapter -> Easee writer -> Easee`

Voor WW in de huidige implementatie:

`Energy Core -> Power Intent -> WW target_on -> WW Power Adapter -> Boiler writer -> Boiler`

Voor de toekomstige numerieke WW-interface:

`Energy Core -> Power Intent -> WW_target_W -> WW Power Adapter -> Boiler writer -> Boiler`

Deze scheiding voorkomt dat apparaatdetails teruglekken naar EMS-policy en maakt adapters afzonderlijk testbaar in SHADOW.

## 11. Single-writer boundary en cut-over

Een fysieke writer mag pas worden geactiveerd via gecontroleerde atomic cut-over waarbij de bestaande productiewriter wordt uitgefaseerd. Vereisten zijn:

- bewezen revision/schema alignment;
- bewezen freshness/fail-closed gedrag;
- bewezen mapping en fysieke feasibility;
- bewezen dedupe/idempotency;
- geen dubbele notificaties/history/writes;
- rollback naar de vorige bewezen writer;
- nooit twee fysieke writers tegelijk voor dezelfde actuator.

## 12. Safety invariants

Deze laag moet altijd voldoen aan:

- geen device writes in SHADOW;
- geen policy-arbitrage in adapters;
- revision alignment vóór actuatorvertaling;
- fail-closed bij ontbrekende, ongeldige of stale control-input;
- adapter verhoogt nooit upstream vermogensbudget;
- requested, commanded en confirmed blijven afzonderlijke begrippen;
- Easee-runtimecontrol gebruikt uitsluitend dynamic/volatile control;
- automatische phaseswitching vereist een aparte state machine;
- WW HOLD is semantisch verschillend van OFF;
- één fysieke writer per actuator na cut-over.

## 13. Huidige status

| Onderdeel | Status |
|---|---|
| 24h Planner v0.2 | ACTIVE SHADOW |
| Power Intent v0.2 | ACTIVE SHADOW |
| EV_target_W | ACTIVE SHADOW, numeriek |
| WW target_on | ACTIVE SHADOW, binair |
| WW_target_W | ARCHITECTUURCONTRACT / nog niet numeriek geproduceerd |
| EV Power Adapter v0.1 | ACTIVE SHADOW |
| WW Power Adapter v0.1 | ACTIVE SHADOW |
| Actuator Commands v0.2 | ACTIVE SHADOW |
| EV fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| WW fysieke writer via nieuwe adapterketen | NIET ACTIEF |
| Victron fysieke writer | NIET ACTIEF |
