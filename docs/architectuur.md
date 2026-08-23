# Architectuuroverzicht

Deze pagina beschrijft de **actuele gecodeerde architectuur van Energy Core v2**. Procesflows en statusbeschrijvingen op deze site moeten altijd overeenkomen met de productiecode; een toekomstige doelarchitectuur wordt expliciet als SHADOW of toekomstig gemarkeerd.

## 1. Hoofdstructuur

```text
FYSIEKE INSTALLATIE / VEILIGHEID
3×25 A · P1 · Easee Equalizer · lokale apparaatbeveiligingen
                    │
                    ▼
               METEN / STATE
P1 · PV · Easee · boiler · Quatt · overige relevante devices
                    │
           centrale Core-snapshot / 5 min
                    ▼
             ENERGY CORE v2
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      State      Decision     Shadow
                    │
             realtime intents
                    │
                    ▼
        afzonderlijk gevalideerde writers

Ondersteunende planningslaag:
Contract-/prijscontext · Tesla/WW-verplichtingen · PV-context
                    │
                    ▼
      24h Energy Planner SHADOW / 15 min
                    │
                    ▼
  kostenvensters + flexplanning + Victron SHADOW-scenario
                    │
                    └──► uitsluitend Logic-state / advies

Bediening/configuratie:
Website selector / Tesla deadline
          │
          ▼
PIN → Cloudflare Worker → GitHub command
          │
          ▼
Homey Settings Sync → canonieke Logic-state
          │
          ▼
Core / productiecontrol → Publisher → website
```

De Energy Manager ligt niet in het fysieke stroompad. Installatieveiligheid, lokale apparaatbeveiligingen en Easee Equalizer blijven hoger in de hiërarchie.

## 2. Single-reader meetlaag en Homey-belasting

De Core draait op vijfminutencadans. Per Core Tick geldt als harde ontwerpgrens maximaal één volledige Homey-device-snapshot en één Logic-snapshot. Downstream-logica pollt dezelfde devices niet opnieuw wanneer de informatie al beschikbaar is.

Voor sneller veranderende signalen mag een **gerichte event-assisted detector** worden gebruikt wanneer de vijfminutencadans onvoldoende is. Zo'n detector mag geen nieuwe korte-interval `getDevices()`-scan introduceren.

Bindende volgorde voor nieuwe functionaliteit:

```text
1. Signaal al in Core-snapshot? → hergebruik
2. Gerichte event-trigger mogelijk? → event-driven/event-assisted
3. Vijfminuten-Core kan het meenemen? → centrale read uitbreiden
4. Alleen anders → expliciete aanvullende poller
```

De website veroorzaakt geen Homey-devicepolling. De nieuwe settings-write-route schrijft uitsluitend expliciete gebruikersconfiguratie en is daarmee gescheiden van de meetlaag.

## 3. Waarheidsbronnen en meetvaliditeit

Voor elektrische woningbalans en realtime flex-control is P1 leidend:

```text
P1 < 0 W → netto export
P1 > 0 W → netto import
```

De meetvaliditeit is bewust gesplitst:

- `gridMeasurementValid`: verse/geldige P1-netmeting en autoritatieve gate voor import, export en flex-exportbudget;
- `derivedHouseBalanceValid`: gereconstrueerde P1+PV/huisbalans, uitsluitend voor `house_load`, residual/Overig en diagnostiek.

Harde invariant:

```text
P1 geldig + SOURCE_SKEW in PV/huisreconstructie
→ flex-exportbudget blijft bruikbaar
→ afgeleide huis/Overig-diagnostiek degradeert

P1 stale/ongeldig
→ flex-exportbudget = 0 W (fail-closed)
```

Voor Quooker zijn de waarheidsbronnen gescheiden: Homey switch voor beschikbaar/aan-uit; P1/L3 voor daadwerkelijk verwarmen en vermogen.

## 4. Rollen van energieverbruikers

| Verbruiker | Architectuurrol | Flexibel? | Fysieke v2-Control |
|---|---|---:|---|
| Normaal huishouden | basislast | nee | n.v.t. |
| Quatt | `COMFORT_BASELOAD` | voorlopig nee | `OBSERVE_ONLY` |
| Boiler | flexload met comfortdoel | ja | bronkeuze productie-actief; actuatorroute gefaseerd |
| Tesla | flexload met deadline/opportunity | ja | afzonderlijke productiewriter |
| Quooker | comfort/gebruikspatroon + gemeten load | beperkt | bestaande Quooker-flows; detector observe-only |
| Victron-batterij | energie-/netbuffer | ja | later via Victron EMS/ESS; nu SHADOW-simulatie |

## 5. Centraal vermogensbudget en Decision-prioriteit

```text
flex_export_budget
 = max(0,
       P1_export
       - grid_safety_reserve
       - quatt_ramp_reserve)
```

De actuele gridreserve is 200 W. Het budget wordt uitsluitend vrijgegeven bij `gridMeasurementValid=true`.

Beslisprioriteit:

```text
1. Installatieveiligheid en lokale hardwarebeveiliging
2. Comfort-baseload
3. Harde doelen/MUST
4. Economische flex-opportunities
5. Rest naar net / later Victron-batterijbeleid
```

Tesla- en warmwaterverplichtingen gaan vóór economische optimalisatie.

## 6. Contract-aware prijsarchitectuur

Prijsoptimalisatie wordt geconsolideerd rond de geïsoleerde `EM2_ContractPrice_*` interface. De beslislaag ondersteunt `FIXED` en `DYNAMIC`.

```text
EM v2 | 40 Decision | Contract-aware v0.2
controlMode = SHADOW_CANDIDATE
noActuatorWrites = true
```

De website kan het contracttype inmiddels als beveiligde EMS-instelling schrijven. De volledige productie-cut-over is nog niet afgerond: resterende legacy `M7_Price_*`-afhankelijkheden, met name in Tesla-productie, moeten worden verwijderd zodat uitsluitend de contract-aware context leidend is.

Bij `FIXED` mogen dynamische prijsclassificaties geen productiegedrag veroorzaken. Dit is een expliciet regressiecriterium.

## 7. Warm water — actuele productiebronkeuze

De eerdere architectuurtekst waarin `BOILER ↔ CV` alleen SHADOW/advies was, is **vervallen**. De bronselector is nu productie-actief en E2E gevalideerd.

Actuele keten:

```text
Website: BOILER ↔ CV
        │
        ▼
PIN-beveiliging
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
        ├── CV     → elektrische boilercontrol BLOCKED_MODE
        │
        └── BOILER → normale WW timing/opportunity/deadline-logica
        │
        ▼
Publisher → energy-state-v2.json → website
```

`WW_Boilermodus` blijft de canonieke Homey-runtimevariabele, maar wordt nu door de beveiligde websiteconfiguratie gevoed. De website schrijft dus geen actuator aan; zij schrijft een expliciete configuratieopdracht die Homey valideert en vertaalt naar canonieke Logic-state.

### E2E-validatie 23 augustus 2026

Beide richtingen zijn live gevalideerd:

```text
BOILER → CV
website → PIN → Worker → GitHub → Settings Sync
→ WW_Boilermodus=false → Core BLOCKED_MODE → Publisher

CV → BOILER
website → PIN → Worker → GitHub → Settings Sync
→ WW_Boilermodus=true → Core normale WW-regels → Publisher
```

Na terugschakelen naar Boiler gaf de runtime terecht `AFTER_DEADLINE`: de bron stond weer op Boiler, maar na 19:00 werd geen nieuwe elektrische warmwater-run gestart.

## 8. EMS Settings Sync en configuratiewaarheid

Actieve configuratieflow:

```text
EM v2 | 05 Config | EMS Settings Sync v0.2
```

De sync leest primair via de authenticated GitHub Contents API met de bestaande status-tokenroute. Raw GitHub is alleen fallback. Dit voorkomt dat een nieuwe gebruikersopdracht door raw-content caching vertraagd wordt verwerkt.

Ondersteunde instellingen:

```text
hotWaterSource = BOILER | CV
contractType   = FIXED | DYNAMIC
```

Canonieke vertaling:

```text
hotWaterSource → WW_Boilermodus
contractType   → EMS_ContractType
```

Een selectorwijziging is zelf de opdracht: er is geen verborgen aparte knop `Instellingen opslaan`. Na selectie wordt direct de PIN-route gestart. Bij annuleren/falen wordt de laatst bevestigde waarde hersteld.

## 9. Tesla

Tesla gebruikt deadline/MUST vóór opportunity-control. Easee Equalizer blijft autonoom de feitelijke laadstroom en lokale elektrische veiligheid begrenzen.

De deadline-write-route en de EMS-settingsroute gebruiken hetzelfde beveiligingsprincipe met PIN + Cloudflare Worker. De Tesla-productieflow heeft een FIXED-gate gekregen zodat legacy dynamische prijssignalen bij een vast contract niet bedoeld zijn als productietrigger. Definitieve consolidatie naar uitsluitend de contract-aware prijsinterface blijft een open pre-Victron actie.

Voor Easee geldt: FLASH-belastende persistente configuratieacties worden niet gebruikt voor frequente automatische regeling. Dynamische laadstroomsturing en de autonome Equalizer-functie blijven daarvan gescheiden.

## 10. 24h Energy Planner — pre-Victron SHADOW

Actieve flow:

```text
EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW
cadans = 15 min + 45 s stagger
controlMode = SHADOW
noActuatorWrites = true
```

Het actuele simulatiescenario:

```text
MultiPlus-II 48/5000/70-50
Cerbo GX MK2
VM-3P75CT
3 × Pylontech US5000
nominaal                 = 14,4 kWh
SHADOW SOC-band          = 20–90%
SHADOW bruikbaar venster = 10,08 kWh
SHADOW AC charge limit   = 3,3 kW
SHADOW AC discharge      = 3,3 kW
SHADOW η charge          = 95%
SHADOW η discharge       = 95%
SHADOW roundtrip         = 90,25%
```

Dit zijn simulatieaannames, geen commissioninginstellingen. De planner maakt geen Victron-, Easee- of boilerwrites.

Vereenvoudigde actuele procesflow:

```text
15-min trigger
      │
      ▼
Lees State + WW + contract/prijs + Tesla deadline + PV-context
      │
      ▼
Contracttype FIXED / DYNAMIC
      │
      ▼
Leg Tesla/WW harde verplichtingen vast
      │
      ▼
Rangschik economische flexkansen
      │
      ▼
Simuleer Tesla / WW / batterij kwartieracties
      │
      ▼
Publiceer EM2_Energy_Plan_24h + status
      │
      ▼
STOP — SHADOW, geen fysieke writes
```

## 11. Victron-doelarchitectuur

De geplande Victron-laag bestaat uit MultiPlus-II 48/5000, Cerbo GX MK2, VM-3P75CT en 3 × Pylontech US5000. De bestaande PV-omvormers blijven AC-gekoppeld.

Victron/ESS wordt na installatie eigenaar van batterij-SOC, laden/ontladen en batterij-/netveiligheid. Homey blijft huishoudelijke orchestrator voor flexloads zoals Tesla en warm water en mag Victron-safety/ESS-regels niet dupliceren of omzeilen.

Zolang Victron niet fysiek geïntegreerd is, geldt batterijsteun in realtime Core/control als 0 W. Alleen de 24h-planner simuleert het afgesproken scenario.

## 12. Veiligheidshiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Lokale apparaatbeveiligingen
          ↓
Easee Equalizer
          ↓
Victron EMS / ESS (na installatie)
          ↓
Energy Core v2 + Homey-orchestratie
          ↓
Gevalideerde huishoudelijke actuator-writers
```

## 13. Publicatie, website en CI/CD

State, Decision en Shadow worden revision-consistent gepubliceerd. Live View en historie blijven observability en beïnvloeden geen fysieke regelbesluiten.

De website heeft daarnaast twee expliciete **control/configuratie-ingangen** die niet met observability mogen worden verward:

- Tesla deadline-opdracht;
- EMS-instellingen (`BOILER/CV`, `FIXED/DYNAMIC`).

Beide lopen uitsluitend via de beveiligde PIN/Worker-commandroute; frontendcode schrijft nooit rechtstreeks naar Homey of een actuator.

Cloudflare Workers Builds is gekoppeld aan GitHub `main` met root `/cloudflare`. Daardoor geldt voor Worker-code:

```text
GitHub main → Cloudflare build → Worker deployment
```

Voor websitepublicatie geldt dat wijzigingen in `ems-settings-command.json` een Pages-publicatie kunnen triggeren zodat bevestigde configuratiestatus niet onnodig achterloopt.

## 14. Control- en writerdiscipline

```text
Meetdata:
State → Decision → Shadow/validatie → Control intent → exact één writer → actuator

Configuratie:
Website → PIN → Worker → command → Settings Sync → canonieke Logic-state

Planning:
Context + State → 24h Planner SHADOW → plan/advies
                                      └── geen actuatorwrite
```

Per fysieke actuator bestaat uiteindelijk exact één automatische writer. Configuratie-, observatie-, historie-, detector- en plannerlagen mogen geen alternatieve actuatorroute creëren.

## 15. Test- en synchronisatieregel

Homey `start_flow()` bevestigt dat een flow gestart is, niet dat downstream verwerking al voltooid is. E2E-validatie mag daarom niet aannemen dat handmatig achter elkaar gestarte flows synchroon zijn. De bevestigde gepubliceerde runtime-state is leidend voor het einde van een E2E-test.

**Documentatie-invariant:** procesflowdiagrammen beschrijven altijd de actuele gecodeerde stand. Bij iedere relevante flowwijziging worden code, tekst en procesdiagram in dezelfde wijzigingscyclus bijgewerkt.

## 16. Pre-Victron open punten

Voor de stable pre-Victron baseline resteren primair:

1. FIXED/DYNAMIC productiepad consolideren en resterende legacy `M7_Price_*`-afhankelijkheden verwijderen;
2. Tesla laad-efficiëntie/deadline-calibratie afronden;
3. warmwater-actuatorroute verder valideren en gecontroleerd vrijgeven waar van toepassing;
4. formele regressietest op FIXED, DYNAMIC, Tesla deadline, PV opportunity, BOILER, CV, stale P1, SOURCE_SKEW, fail-safe en publicatie;
5. daarna software-/websiteprocesflows als pre-Victron stable baseline bevriezen.

## 17. Architectuur-review / regressiecriteria

Iedere wijziging wordt minimaal getoetst op:

- bijdrage aan laagste energiekosten en toekomstige Victron-integratie;
- geen onnodige Homey-load/API-calls;
- correcte waarheidsbron en geen dubbele writers;
- `gridMeasurementValid` en `derivedHouseBalanceValid` correct gescheiden;
- FIXED/DYNAMIC via de contract-aware abstractie;
- bij `FIXED` geen dynamische prijsactie uit legacy M7-signalen;
- BOILER/CV-configuratie uitsluitend via de beveiligde settingsroute;
- Tesla/WW MUST boven economische optimalisatie;
- 24h-planner blijft SHADOW;
- Victron/ESS eigenaar van batterij/SOC/netveiligheid;
- geen frequente Easee FLASH-belastende configuratiewrites;
- fail-safe gedrag bij stale/onbekende data;
- rollback en testbaarheid;
- synchroniteit tussen broncode, procesdiagrammen, frontendbundle en productie-artifact.

> Laatste update: **23 augustus 2026** — BOILER↔CV-selector productie-actief en in beide richtingen E2E gevalideerd; EMS Settings Sync v0.2 met authenticated GitHub Contents API; beveiligde PIN/Cloudflare/GitHub/Homey-configuratieketen gedocumenteerd; runtime terug op BOILER. Contract-aware FIXED/DYNAMIC productieconsolidatie blijft open pre-Victron werk.