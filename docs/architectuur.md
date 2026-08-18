# Architectuuroverzicht

Deze pagina beschrijft de **actuele doelarchitectuur van Energy Core v2**. De oudere v1-opzet met losse State Collector, Allocator Shadow en meerdere zelfstandige publishers is niet meer leidend.

## 1. Hoofdstructuur

```text
FYSIEKE INSTALLATIE / VEILIGHEID
3×25 A · P1 · Easee Equalizer · lokale apparaatbeveiligingen
                    │
                    ▼
               METEN / STATE
P1 · PV · Easee · boiler · Quatt · overige relevante devices
                    │
           1 centrale snapshot / 5 min
                    ▼
       EM v2 | 00 Core Tick | v0.9.7
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      State      Decision     Shadow
        │           │
        │      gedeeld energie-/flexbudget
        │           │
        └──────► Control intents
                    │
                    ▼
        afzonderlijk gevalideerde writers

Ondersteunend:
Prijs/PV-context · GitHub-publicatie · historie · website
```

De Energy Manager ligt niet in het fysieke stroompad. Hij meet, classificeert en verdeelt beschikbare flexibiliteit. Installatieveiligheid en lokale hardwarebeveiliging blijven altijd hoger in de hiërarchie.

## 2. Single-reader meetlaag

De actuele centrale kern is:

```text
EM v2 | 00 Core Tick | v0.9.7
```

Iedere vijf minuten gebruikt deze maximaal:

```text
1 × Homey.devices.getDevices()
1 × Homey.logic.getVariables()
```

Daaruit wordt één revision-consistente snapshot opgebouwd. P1, PV, Tesla/Easee, boiler, Quatt en appliance-status worden vervolgens in-memory verwerkt. Downstream-logica mag niet opnieuw dezelfde devices gaan pollen.

Prijs- en PV-forecastcontext wordt iedere 15 minuten vernieuwd zonder een extra device-scan.

## 3. Waarheidsbronnen

Voor de elektrische woningbalans is **P1 leidend**:

```text
P1 < 0 W → netto export
P1 > 0 W → netto import
```

Apparaatmetingen verklaren vervolgens waar die belasting vandaan komt en welke delen flexibel zijn.

Belangrijk gevolg: een grootverbruiker die al in P1 zit, zoals Quatt, mag niet nogmaals van P1-export worden afgetrokken. Dat zou dubbel tellen.

## 4. Rollen van energieverbruikers

Niet iedere belasting heeft dezelfde regelvrijheid.

| Verbruiker | Architectuurrol | Flexibel? | Fysieke v2-Control |
|---|---|---:|---|
| Normaal huishouden | basislast | nee | n.v.t. |
| Quatt | `COMFORT_BASELOAD` | voorlopig nee | `OBSERVE_ONLY` |
| Boiler | flexload met comfortdoel | ja | nog Shadow/afzonderlijke migratie |
| Tesla | flexload met optionele deadline | ja | afzonderlijke writer/migratie |
| Quooker | constraint/gebruikspatroon | beperkt | buiten centrale budgetwriter |
| Victron-batterij | toekomstige energie-/netbuffer | ja | later via Victron EMS |

Deze scheiding voorkomt dat comfortkritische ruimteverwarming op dezelfde manier wordt behandeld als een verplaatsbare boiler- of EV-load.

## 5. Quatt als serieuze comfortlast

De primaire elektrische Quatt-bron is:

```text
Quatt CIC.measure_power
```

Quatt wordt uit dezelfde bestaande Core-snapshot gelezen en veroorzaakt dus geen extra Homey-poll.

Naast elektrisch vermogen worden, waar beschikbaar, diagnostische waarden meegenomen zoals thermisch vermogen, COP, working mode, thermostaatvraag en CV-request.

Quatt wordt gepubliceerd als:

```text
role         = COMFORT_BASELOAD
control_mode = OBSERVE_ONLY
controllable = false
```

Energy Core mag Quatt dus **wel meewegen**, maar niet fysiek begrenzen, uitschakelen of van setpoint veranderen zolang daar geen aparte veilige Control-policy voor is gevalideerd.

## 6. Centraal vermogensbudget

Vanaf Core v0.9.7 publiceert State een expliciet `energy_budget`.

Belangrijkste grootheden:

- totale geschatte woninglast;
- bekende flexlast (Tesla + boiler);
- comfortlast (Quatt);
- overige woninglast;
- grid safety reserve;
- Quatt-rampreserve;
- werkelijk vrij exportbudget voor flexloads;
- discretionair importbudget;
- toekomstige batterijsteun.

### Flex-exportbudget

P1 bevat actueel Quatt-verbruik al. Alleen extra marge voor mogelijke Quatt-modulatie wordt gereserveerd:

```text
flex_export_budget
 = max(0,
       P1_export
       - 200 W gridreserve
       - Quatt-rampreserve)
```

Quatt-rampreserve:

```text
Quatt < 250 W        → 100 W reserve
Quatt ≥ 250 W        → max(350 W, 25% Quatt)
                        met maximum 750 W
```

Dit is een conservatieve startpolicy. Shadowdata kan later aanleiding geven om de reserve te kalibreren.

### Discretionair importbudget

Voor economische starts bij goedkope stroom wordt daarnaast bewaakt hoeveel extra netimport verantwoord is. De huidige bovengrens voor discretionaire flexstarts is 4.000 W totale actuele import.

Dit budget is **geen installatieveiligheidslimiet**. De echte installatiegrenzen en Easee-loadbalancing blijven hoger in de hiërarchie.

## 7. Decision-prioriteit

De doelarchitectuur gebruikt geen simpele vaste lijst “Tesla altijd vóór boiler”. De prioriteit is contextafhankelijk:

```text
1. Installatieveiligheid en lokale hardwarebeveiliging
2. Comfort-baseload: normaal huishouden + Quatt
3. Harde doelen/MUST
      ├─ Tesla deadline catch-up
      └─ warmwater catch-up
4. Economische flex-opportunities
      ├─ PV/flex-export
      ├─ negatieve prijs
      └─ goedkoop prijsvenster binnen importbudget
5. Rest naar net / later batterijbeleid
```

Hiermee kan een MUST-deadline terecht een opportunistische load verdringen, terwijl gewone PV-optimalisatie alleen vrije ruimte gebruikt.

## 8. Tesla

Voor Tesla gebruikt Decision vanaf v0.9.7 het **flex-exportbudget na Quatt-reserve** en niet alleen de kale P1-export.

Belangrijk:

- deadline/MUST blijft boven opportunistische optimalisatie staan;
- zonder deadline is Tesla een flexibele exportbuffer;
- goedkope prijs moet voldoende discretionair importbudget hebben;
- negatieve prijs is een aparte economische opportunity;
- Easee Equalizer blijft autonoom de feitelijke laadstroom begrenzen indien fase- of installatiebelasting dat vereist.

Werkelijk laadvermogen blijft belangrijker dan alleen het gevraagde laadsetpoint.

## 9. Warm water

De elektrische boiler blijft een verplaatsbare belasting met een comfortdoel:

```text
OP_TEMPERATUUR één keer per lokale kalenderdag
```

Confirmed-heating accounting gebruikt werkelijk verwarmingsvermogen in plaats van alleen relais-aan-tijd.

Warm Water Control v0.11 gebruikt vanaf Core v0.9.7 dezelfde gedeelde budgetcontext:

- PV-start vereist circa 1.900 W flex-exportbudget na Quatt/gridreserve;
- top-PV-forecast vraagt minimaal 500 W flex-exportbudget;
- goedkope prijsstart controleert of verwachte import binnen het discretionaire importbudget blijft;
- catch-up/deadline kan economische optimalisatie overrulen;
- alle huidige WW-intenties blijven Shadow zolang fysieke Control niet expliciet is vrijgegeven.

## 10. Veiligheidshiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Lokale apparaatbeveiligingen
          ↓
Easee Equalizer voor EV-loadbalancing
          ↓
Victron EMS voor batterij/net (later)
          ↓
Energy Core v2 flexorchestratie
          ↓
Gevalideerde actuator-writers
```

Homey probeert lokale beveiligingslagen nooit te overrulen.

## 11. Victron-doelarchitectuur

De geplande Victron-laag bestaat uit MultiPlus-II, Cerbo GX, VM/3P75CT en thuisbatterij. Victron wordt de primaire batterij-/netlaag; Homey blijft huishoudelijke orchestrator.

In het huidige schema is reeds ruimte gereserveerd voor:

```text
battery_support_w = 0
battery_integrated = false
```

Na integratie kan Victron een toegestane batterijbijdrage aan hetzelfde gedeelde budget leveren. Dat verandert de rol van Quatt niet: Quatt blijft een bekende comfortlast die het beschikbare flexbudget beïnvloedt, niet automatisch een aan te sturen flexload.

## 12. Publicatie en website

Core Tick publiceert een gethrottlede, revision-consistente snapshot naar:

```text
docs/data/energy-state-v2.json
```

Actueel:

```text
schema_version    = 2.5
publisher_version = EM2_CORE_PUBLISH_V0.9.7
control_mode      = SHADOW
```

Websitebezoek veroorzaakt geen Homey-calls. Historie en presentatie staan buiten de kritische fysieke regelroute.

## 13. Flowversionering

Voor iedere functionele flowfamilie geldt:

```text
inhoudelijke wijziging
      ↓
nieuwe hogere versie
      ↓
validatie
      ↓
nieuwe versie actief
oude versie uit
```

Er mag maximaal één versie van dezelfde Core-flow actief zijn. De v0.9.7-cut-over heeft daarom eerst v0.9.6 uitgeschakeld en pas daarna v0.9.7 geactiveerd.

## 14. Gevalideerde toestand v0.9.7

De eerste v0.9.7-publicatie op 18 augustus 2026 bevestigde:

- schema 2.5;
- State/Decision/Shadow allemaal revision 329;
- Quatt live in State;
- expliciet `energy_budget`;
- Quatt `OBSERVE_ONLY`;
- geen fysieke Quatt-write;
- behoud van Shadow-guards voor warm water.

Tijdens die sample gebruikte Quatt 10,3 W. Bij 184 W netexport, 200 W gridreserve en 100 W Quatt-idlereserve was het berekende flex-exportbudget terecht 0 W.

## 15. Ontwerpprincipes

- meten vóór sturen;
- veiligheid vóór optimalisatie;
- comfortload is niet automatisch flexload;
- P1 is leidend en apparaatvermogen wordt niet dubbel geteld;
- één centrale read, meerdere in-memory consumers;
- deadlines boven opportunistische optimalisatie;
- lokale hardwarebeveiliging nooit overrulen;
- eerst Shadow, daarna gecontroleerde fysieke Control;
- Homey zo licht mogelijk houden;
- iedere inhoudelijke flowwijziging krijgt een nieuwe versie;
- documentatie en architectuur worden tegelijk met operationele wijzigingen bijgewerkt.

> Laatste architectuurupdate: **18 augustus 2026 — Energy Core v2 / Core Tick v0.9.7.** Quatt is first-class `COMFORT_BASELOAD` en onderdeel van State, Decision en het gedeelde flexbudget, zonder extra device-poll en zonder fysieke Quatt-sturing.