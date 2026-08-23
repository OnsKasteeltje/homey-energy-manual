# Energiehistorie

<div id="energy-history-dashboard">
  <p><em>Energiehistorie wordt geladen…</em></p>
</div>

!!! info "Canonieke telemetry-history v0.5.4"
    **Dag** gebruikt `energy-day-v2.json` uit `EM v2 | 70 History | Day Series v0.5.4`. De historylaag blijft onafhankelijk van de fysieke control-loop. P1 wordt iedere vijf minuten gericht en rechtstreeks gelezen; een ontbrekende P1-waarde blijft `null`/ongeldig en wordt nooit stilzwijgend `0 W`. Daarnaast worden de cumulatieve P1-tellers voor import en export vastgelegd als onafhankelijke energetische controle.

!!! note "Meten en beslissen zijn gescheiden"
    De telemetry-history registreert **wat fysiek gebeurde**. `EM v2 | 70 History | Control Audit v0.2` registreert afzonderlijk **waarom een controlbesluit werd genomen**, inclusief action, priority, reason, opportunity, guards en beschikbare actuator-evidence. Een opportunity-gestuurde boileractie verandert dus niet de meetketen en omgekeerd.

!!! note "Schema-hardening"
    History accepteert compatibele `ENERGY_STATE_V2.x`-states en valideert daarnaast de daadwerkelijk benodigde velden. Een kleine Core-schema-bump hoeft daardoor de historieketen niet meer stil te leggen; incompatibele input blijft fail-safe geweigerd.

!!! warning "Null-semantiek"
    `null` betekent **onbekend / niet geldig gemeten**, nooit nul verbruik. Alleen intervallen waarvan de noodzakelijke P1-samples geldig zijn mogen voor vermogensintegratie worden gebruikt. Waar een geldige dagbaseline beschikbaar is, hebben cumulatieve P1-import- en exporttellers voor de dagenergie voorrang boven vermogensintegratie.

## Berekeningsprincipes

```text
PV-productie = SolarEdge + GoodWe GW4200D-NS + GoodWe GW2000-XS
P1-netvermogen = directe gerichte P1-meting
Netimport = max(P1, 0)          alleen indien P1 geldig
Netexport = max(-P1, 0)         alleen indien P1 geldig
Woningverbruik = PV-productie + P1-netvermogen, alleen bij geldige/synchroniseerbare bronnen
Tesla-energie = integraal(teslaW × werkelijke sampletijd)
Dagimport/-export = bij voorkeur delta cumulatieve P1-tellers
```

De baseline-history draait iedere vijf minuten. Elk sample bewaart naast de Core-context de directe P1-velden `p1W`, `p1L1W`, `p1L2W`, `p1L3W`, `p1Valid`, `p1PhaseValid`, `p1ConsumedKWh`, `p1ReturnedKWh` en bijbehorende validiteitsinformatie. Daarmee kan een nacht ook worden gereconstrueerd als incidentele instantane P1-samples ontbreken.

## Twee resoluties voor apparaatdetectie

De vijfminutenreeks is bedoeld voor het continue energiebeeld, nacht-/daganalyse, Tesla, boiler en langdurige verbruikers. Kortdurende apparaatfingerprints worden **event-first** verwerkt en niet door een continue hoogfrequente poller:

- wasmachine/droger: directe AEG-status is leidend; overgangsevents nemen een P1-fasesnapshot en de bestaande 5-minutenreeks is fallback;
- Quooker: Homey-switch is autoritatief voor ON/OFF; P1-event heartbeat activeert alleen wanneer nodig een gerichte P1/L3-meting;
- toekomstige fingerprints volgen hetzelfde patroon: event-gated/armed hoge-resolutiemeting, zodat Homey niet permanent hoogfrequent wordt gepolld.

Directe apparaatstatus of direct gemeten vermogen blijft altijd leidend boven fingerprint/inference.

## Persistente dagketen

```text
Directe P1 (5 min) ─────────────┐
                                ├─ canonical telemetry sample
EM2_State / bekende loads ──────┘
              ↓
EM2_Day_History (lopende dagbuffer)
              ↓
energy-day-v2.json → Dag / vandaag
              ↓ kalenderwissel
1. compacte dagarchive → energy-daily-history.json
2. full-resolution archive → energy-day-series-7d.json
```

De rolling file bewaart maximaal zes afgesloten dagen plus vandaag. Als een archive-write faalt, wordt de oude lokale buffer niet weggegooid en kan de rollover veilig opnieuw worden geprobeerd.

## Onafhankelijke control-audit

```text
EM2_State + EM2_WW_State + EM2_Control_WW
              ↓ logic-only, geen device-read/write
Control Audit v0.2
              ↓
energy-control-history-v2.json
```

Deze auditlaag bevat onder andere `action`, `priority`, `reason`, `opportunity`, relevante guards en beschikbare actuatorstatus. Daarmee kunnen achteraf twee losse vragen worden beantwoord:

1. **Wat gebeurde er fysiek?** → canonical telemetry-history.
2. **Waarom gebeurde het?** → decision/writer/control-audit.

## Freshness en health

De history-publicatie bevat healthinformatie over Core-age, P1-validiteit, fasevaliditeit, teller-validiteit en eventuele `held`-status. Een ongeldige P1-meting wordt als `P1_INVALID` zichtbaar gemaakt in plaats van als nulverbruik te worden opgeslagen.

De interface gebruikt één freshnessmodel:

- **< 15 minuten:** actueel;
- **15–30 minuten:** vertraagd / waarschuwing;
- **> 30 minuten:** data verouderd / foutstatus.

## Homey-load

De wijziging voegt geen continue hoogfrequente P1-poller toe. De baseline doet één gerichte P1-read per vijf minuten. Hogere resolutie wordt alleen event-gated gebruikt voor specifieke classifiers/fingerprints. Control Audit leest uitsluitend bestaande Logic-state en doet geen devicecalls of actuatorwrites.

## Productieversies

- `EM v2 | 70 History | Day Series v0.5.4` — actief; canonieke 5-min telemetry, directe P1, null-safe, cumulatieve P1-checksum.
- `EM v2 | 70 History | Day Series v0.5.3` — uitgeschakeld / rollback.
- `EM v2 | 70 History | Control Audit v0.2` — actief; onafhankelijke WHY-laag.
- `EM v2 | 70 History | Control Audit v0.1` — uitgeschakeld / rollback.

> Laatste update: **23 augustus 2026** — Day Series **v0.5.4** en Control Audit **v0.2**: canonical null-safe P1 telemetry, cumulatieve import/export-checksum, expliciete scheiding tussen measurement en control, en event-first fingerprinting zonder continue extra Homey-load.
