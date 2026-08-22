# Canonieke projectbaseline — Home Energy Management System

_Status: 22 augustus 2026_

## Doel en bronhiërarchie

Dit document is de centrale referentie voor toekomstige ontwerp-, code- en documentatiebesluiten. Bij conflicten geldt deze volgorde:

1. actuele, runtime-gevalideerde implementatie;
2. recente expliciete projectbesluiten;
3. `requirements-traceability.md`, runtime-status en actuele GitHub-documentatie;
4. Integraal energierapport Victron ESS + Home Energy Management System **v37** als actuele integrale projectbaseline;
5. v35.1 voor historische PV-/hardwareanalyse voor zover v36/v37 die niet expliciet heeft vervangen;
6. oudere rapport- en flowversies alleen als historie.

Statuslabels: `VERIFIED`, `IMPLEMENTED`, `SHADOW`, `DECIDED`, `OPEN`, `KNOWN / MONITOR`, `SUPERSEDED`.

## 1. Architectuur

- `VERIFIED` — Energy Core v2 gebruikt één centrale fysieke snapshot per 5 minuten en maximaal één `getDevices()` plus één `getVariables()` per Core Tick. Downstream-logica werkt in-memory op dezelfde revision.
- `VERIFIED` — P1 is leidend voor de netto woningbalans.
- `DECIDED` — Homey is huishoudelijke orkestratielaag; installatieveiligheid en lokale apparaatbeveiligingen staan erboven.
- `DECIDED` — Victron wordt na installatie primaire batterij-/netregelaar; Homey blijft EV, warm water en andere flexloads orkestreren.

## 2. Energy Core en besluitvorming

Energy Core v2 bevat centrale State, Decision, Shadow, warmwaterstate/-intent en publicatie. Deadlines/MUST gaan vóór opportunistische PV-/prijsoptimalisatie. Per fysieke actuator bestaat uiteindelijk exact één automatische writer en iedere fysieke Control-route gaat eerst door Shadow-validatie.

## 3. Contract en warm water

Ondersteunde contracttypes zijn `FIXED` en `DYNAMIC`. Comfortdoel en catch-up/deadline hebben voorrang op pure economische optimalisatie. BOILER↔CV-bronkeuze vergelijkt marginale kosten per bruikbare kWh warmte; definitieve parameters blijven vóór operationele cut-over te valideren.

## 4. Tesla / Easee

Tesla is flexload met deadline/MUST boven opportunistische optimalisatie. Easee Equalizer blijft autonome harde load-balancing. Tesla/Easee laadt 3-fase nagenoeg symmetrisch; werkelijk laadvermogen is belangrijker voor classificatie dan alleen gevraagd setpoint.

## 5. Live energie, meetkwaliteit en fasebewaking

P1 is autoritatief voor de netto netbalans. Fase-onbalans is op zichzelf geen foutconditie. Het EMS gebruikt zowel totaal P1-vermogen als L1/L2/L3 afzonderlijk als regelinput. De 3×25 A fasegrenzen en lokale beveiligingen hebben altijd voorrang op opportunistische flexsturing.

## 6. Hardwarearchitectuur — Victron ESS en PV-fasen

### 6.1 Hoofdaansluiting en ESS

- `DECIDED` — hoofdaansluiting **3×25 A**.
- `DECIDED` — **MultiPlus-II 48/5000 als 1-fase ESS op L1**.
- `DECIDED` — **Cerbo GX** als GX-/communicatielaag.
- `DECIDED` — **VM-3P75CT** in de meterkast als centrale 3-fasemeting van L1/L2/L3.
- `DECIDED` — ESS gebruikt **`Total of all phases`**.
- `DECIDED` — VM staat in de meterkast; Cerbo/MultiPlus/batterij in de schuur; communicatie via lokaal netwerk.

### 6.2 Gevalideerde PV-fasemapping — 22 augustus 2026

| Fase | PV-omvormer(s) | Status |
|---|---|---|
| **L1** | geen PV-omvormer | `VALIDATED` |
| **L2** | GoodWe GW4200D-NS, grote GoodWe schuur | `VALIDATED / HIGH` |
| **L3** | SolarEdge SE3680H-RW000BEN4 + GoodWe GW2000-XS | `VALIDATED / HIGH` |

De mapping is vastgesteld met gecontroleerde fysieke uit-/inschakeltests en directe P1-faserespons. Vertraagde Homey/inverterwaarden waren niet de primaire ground truth.

### 6.3 Fysieke doelstructuur

Onderstaand schema is de canonieke conceptuele hardwarearchitectuur. De definitieve beveiligingswaarden en DC-dimensionering volgen uit detailengineering.

```text
                NET / HOOFDAANSLUITING 3×25 A
                         │
                  Hoofdschakelaar
                         │
                ┌────────┴─────────┐
                │ VM-3P75CT        │  ← meet L1/L2/L3
                │ netmeting        │
                └────────┬─────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
         L1             L2             L3
          │              │              │
          │              │              ├─ SolarEdge SE3680H
          │              │              └─ GoodWe GW2000-XS
          │              └─ GoodWe GW4200D-NS
          │
          └─ groep/voeding schuur, bestaand 5G2,5 mm² ~20 m
                     │
                 beveiliging
                     │
              MultiPlus-II 48/5000
                 AC-IN op L1
                     │
              ┌──────┴──────┐
              │             │
           AC-OUT         48 V DC
              │             │
       geselecteerde     DC-hoofd-
       backupgroepen     beveiliging
                            │
                    Pylontech US5000
                       batterijbank
                            │
                         Cerbo GX
                            │
             CAN-BMS + VE.Bus + Ethernet
```

### 6.4 Bestaande schuurverbinding en AC-limiet

- `DECIDED` — bestaande meterkast–schuurverbinding circa **20 m 5G2,5 mm²**.
- `DECIDED` — behandelen als **3×16 A** totdat installatietechnische herbeoordeling anders bevestigt.
- `DECIDED` — huidige ontwerpgrens **MultiPlus AC input current limit ≤16 A**.
- PowerAssist verhoogt niet de toegestane stroom door de bestaande voedingskabel of beveiliging.

### 6.5 AC-out / noodstroom

Een aparte selectie essentiële backupgroepen heeft de voorkeur. Tesla, elektrische boiler en andere zware niet-kritische flexloads komen niet standaard op AC-out. Eén MultiPlus op L1 vormt geen 3-fase eiland; PV op L2/L3 is in deze basisarchitectuur niet beschikbaar als noodstroom-PV.

### 6.6 DC-zijde en batterij

De doelstructuur gebruikt een Pylontech US5000-batterijbank met CAN-BMS-communicatie naar Cerbo GX. Definitieve batterijcapaciteit, DC-kabeldoorsnede, hoofdzekering, DC-disconnect, rails en batterijbeveiliging blijven `OPEN` totdat deze tegen de exacte gekozen hardwarevarianten zijn gedimensioneerd.

### 6.7 Phase-aware ontwerpregel

De architectuur onderscheidt:

1. **netto energiebalans** — som L1+L2+L3;
2. **fasebalans** — verdeling import/export over L1/L2/L3;
3. **faseveiligheid** — stroom en beveiligingsgrens per afzonderlijke fase.

Een gunstige netto energiebalans betekent niet automatisch dat iedere fase lokaal in balans is.

### 6.8 Superseded hardwarevariant

De hybride SmartSolar/DC-PV-route uit rapport v35.1 is `SUPERSEDED` als actuele doelarchitectuur. De bestaande PV-omvormers blijven in de huidige werkarchitectuur AC-coupled. Een DC-PV-route vereist nieuwe string-/Vmp-/Voc-/temperatuurvalidatie.

Voor detailengineering geldt `docs/victron-hardware-baseline.md` als gespecialiseerde hardwarebron.

## 7. Documentstatus

- `REFERENCE / CANONICAL` — integraal energierapport v37 blijft de formele rapportbaseline totdat een nieuwe rapportversie wordt uitgebracht.
- `IMPLEMENTED` — `docs/victron-hardware-baseline.md` bevat de actuele gespecialiseerde Victron-hardwarearchitectuur.
- `IMPLEMENTED` — `docs/phase-aware-ems.md` bevat de fasebewuste EMS-regels.
- `IMPLEMENTED` — `docs/architectuur.md` bevat de bindende softwarearchitectuurinvarianten.

## 8. Open validatieregister

1. `OPEN` — definitieve batterijbank/capaciteit en vermogenslimieten bevestigen.
2. `OPEN` — definitieve Victron beveiligingsmatrix AC/DC.
3. `OPEN` — definitieve lijst backupgroepen achter AC-out.
4. `OPEN` — definitieve DC-kabeldoorsnede, hoofdzekering, DC-disconnect en rails.

## 9. Change-control

Bij iedere relevante wijziging worden requirement, architectuurimpact, Shadow/test waar nodig, runtimevalidatie, requirements-traceability, projectbaseline en gespecialiseerde documentatie synchroon bijgewerkt. Oude aanpakken worden expliciet `SUPERSEDED` gemarkeerd.
