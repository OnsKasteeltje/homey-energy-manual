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
- `VERIFIED` — P1 is leidend voor de netto woningbalans. Apparaatmetingen verklaren/classificeren belasting en mogen niet dubbel in de P1-balans worden verwerkt.
- `DECIDED` — Homey is huishoudelijke orkestratielaag. Installatieveiligheid en lokale apparaatbeveiligingen staan erboven.
- `DECIDED` — Victron wordt na installatie primaire batterij-/netregelaar; Homey blijft orkestreren over EV, warm water en andere flexloads.
- `VERIFIED` — Websitebezoek veroorzaakt geen Homey-devicecalls; de site leest gepubliceerde snapshots.
- `IMPLEMENTED` — `requirements-traceability.md` is de vaste koppeling tussen requirements, procesflow, implementatie en vrijgavecriteria.

## 2. Huidige Energy Core

De actuele runtime-implementatie en versienummers worden vastgelegd in de runtime-status en gespecialiseerde softwaredocumentatie. Architectuurinvarianten blijven leidend boven historische versienummers in deze baseline.

- `IMPLEMENTED/VERIFIED` — Energy Core v2 bevat centrale State, Decision, Shadow, warmwaterstate/-intent en publicatie.
- `IMPLEMENTED` — Quatt is `COMFORT_BASELOAD`, `OBSERVE_ONLY`, niet automatisch regelbaar.
- `IMPLEMENTED` — gedeeld `energy_budget` houdt rekening met gridreserve, Quatt-rampreserve, flex-exportbudget en discretionair importbudget.
- `DECIDED` — deadlines/MUST gaan vóór opportunistische PV-/prijsoptimalisatie.
- `DECIDED` — per fysieke actuator uiteindelijk exact één automatische writer.
- `DECIDED` — iedere fysieke Control-route gaat eerst door Shadow-validatie.

## 3. Contract- en prijsarchitectuur

- `IMPLEMENTED/SHADOW` — ondersteunde contracttypes zijn uitsluitend `FIXED` en `DYNAMIC`.
- `IMPLEMENTED/SHADOW` — beide contracttypes normaliseren naar één uniforme prijscontext voordat downstream beslislogica de prijs gebruikt.
- `DECIDED` — vaste dagelijkse contractkosten zijn geen marginale optimalisatie-input.
- `IMPLEMENTED` — prijscontext is null-safe; ontbrekende prijs is nooit impliciet EUR 0/kWh.

## 4. Warm water

- `DECIDED` — comfortdoel en catch-up/deadline hebben voorrang op pure economische optimalisatie.
- `IMPLEMENTED/SHADOW` — confirmed-heating gebruikt werkelijk boilervermogen, niet alleen relais-aan-tijd.
- `IMPLEMENTED/SHADOW` — BOILER↔CV-bronkeuze vergelijkt marginale kosten per bruikbare kWh warmte.
- `OPEN` — rendementen, calorische gaswaarde en hysterese valideren vóór operationele cut-over.

## 5. Tesla / Easee

- `DECIDED` — Tesla is flexload met deadline/MUST boven opportunistische optimalisatie.
- `IMPLEMENTED` — PV-opportunity gebruikt beschikbaar flexbudget in plaats van blind kale P1-export.
- `VERIFIED` — Easee Equalizer blijft autonome harde load-balancing en mag door Homey niet worden overruled.
- `VERIFIED` — Tesla/Easee laadt 3-fase nagenoeg symmetrisch; tijdens de gevalideerde deadline-run werd circa 2,35 kW per fase waargenomen.
- `DECIDED` — werkelijk laadvermogen is belangrijker voor classificatie dan alleen gevraagd setpoint.

## 6. Quatt

- `IMPLEMENTED/VERIFIED` — primaire elektrische Quatt-bron is Quatt CIC `measure_power` uit dezelfde Core-snapshot.
- `DECIDED` — Quatt is comfortload, niet automatisch flexload.
- `DECIDED` — thermisch vermogen/COP zijn diagnostiek en worden niet bij de elektrische energiebalans opgeteld.

## 7. Live energie, meetkwaliteit en fasebewaking

- `DECIDED` — werkelijk gemeten P1-data wordt als gemeten behandeld, niet als indicatief.
- `DECIDED` — directe betrouwbare device-metingen hebben voor apparaatvermogen voorrang op afleiding.
- `DECIDED` — standby/lekstroom onder 20 W wordt niet als actieve energieverbruiker weergegeven.
- `DECIDED` — energiebalans moet rekenkundig sluiten; `NEGATIVE_HOUSE_BALANCE` is een diagnose die onderzoek vereist, geen normale toestand.
- `DECIDED` — fase-onbalans is op zichzelf geen foutconditie. Het EMS gebruikt zowel totaal P1-vermogen als L1/L2/L3 afzonderlijk als regelinput.
- `DECIDED` — de 3×25 A fasegrenzen en lokale beveiligingen hebben voorrang op opportunistische flexsturing.

## 8. Website/app-refresh

- `IMPLEMENTED` — appdata wordt bij boot/openen expliciet opnieuw opgevraagd.
- `IMPLEMENTED` — periodieke datarefresh iedere 5 minuten.
- `IMPLEMENTED` — refresh bij terugkeer via visibility/pageshow/focus en opnieuw online komen.
- `DECIDED` — navigeren History↔Live mag geen oude cached foutmelding/context terugbrengen.

## 9. Hardwarearchitectuur — Victron ESS en PV-fasen

### 9.1 Hoofdaansluiting en ESS

- `DECIDED` — hoofdaansluiting **3×25 A**.
- `DECIDED` — **MultiPlus-II 48/5000 als 1-fase ESS op L1**.
- `DECIDED` — **Cerbo GX** als GX-/communicatielaag.
- `DECIDED` — **VM-3P75CT** in de meterkast als centrale 3-fasemeting van L1/L2/L3.
- `DECIDED` — ESS gebruikt **`Total of all phases`**: de MultiPlus werkt fysiek op L1, terwijl de netregeling de som L1+L2+L3 gebruikt.
- `DECIDED` — VM staat in de meterkast; Cerbo/MultiPlus/batterij in de schuur; communicatie via lokaal netwerk.
- `DECIDED` — GX Touch is optioneel.

Voor een single-phase ESS op een 3-fase net is L1 de ontwerp-/installatiefase. De centrale 3-fasemeter blijft alle fasen afzonderlijk meten; de fysieke batterij-injectie/-afname vindt op L1 plaats.

### 9.2 Gevalideerde PV-fasemapping — 22 augustus 2026

De drie PV-omvormers zijn gecontroleerd fysiek uit- en ingeschakeld terwijl de directe P1-fasewaarden werden gevolgd. De fysieke schakelactie en P1-respons waren ground truth; vertraagde Homey/inverterstatus is niet als primaire fase-identificatie gebruikt.

| Fase | PV-omvormer(s) | Status |
|---|---|---|
| **L1** | geen PV-omvormer | `VALIDATED` |
| **L2** | GoodWe GW4200D-NS, grote GoodWe in schuur, 12 panelen | `VALIDATED / HIGH` |
| **L3** | SolarEdge SE3680H-RW000BEN4 + GoodWe GW2000-XS, kleine GoodWe/CV, 6 panelen | `VALIDATED / HIGH` |

Hierdoor is een structurele fase-onbalans bij PV-productie verklaarbaar: L3 kan aanzienlijk sterker exporteren dan L1/L2. Dit is geen storing zolang de installatie- en fasegrenzen worden gerespecteerd.

### 9.3 Fysieke doelstructuur

```text
NET / HOOFDAANSLUITING 3×25 A
          │
     hoofdschakelaar
          │
      VM-3P75CT
     meet L1/L2/L3
          │
 ┌────────┼────────┐
 L1       L2       L3
 │        │        ├─ SolarEdge SE3680H
 │        │        └─ GoodWe GW2000-XS
 │        └────────── GoodWe GW4200D-NS
 │
 └─ bestaande schuurvoeding 5G2,5 mm², circa 20 m
          │
      beveiliging
          │
 MultiPlus-II 48/5000
      AC-IN L1
       │     │
    AC-OUT  48 V DC
       │     │
 geselecteerde  batterijbank
 backupgroepen     │
                 Cerbo GX
```

### 9.4 Bestaande schuurverbinding en AC-limiet

- `DECIDED` — bestaande meterkast–schuurverbinding: circa **20 m 5G2,5 mm²**.
- `DECIDED` — deze wordt als **3×16 A** behandeld totdat installatiegegevens of een installatietechnische herbeoordeling anders bevestigen.
- `DECIDED` — zolang deze infrastructuur niet wordt verzwaard geldt als ontwerpgrens **MultiPlus AC input current limit ≤16 A**.
- Bij circa 230 V is 16 A ongeveer **3,68 kVA** op de betreffende fase.
- PowerAssist kan batterijvermogen toevoegen aan AC-out, maar verhoogt niet de toegestane stroom door de bestaande voedingskabel of beveiliging.

### 9.5 AC-out / noodstroom

- `DECIDED` — niet de volledige woning/schuur achter AC-out; een aparte selectie essentiële backupgroepen heeft de voorkeur.
- `DECIDED` — Tesla, elektrische boiler en andere zware niet-kritische flexloads komen niet standaard op AC-out.
- `DECIDED` — één MultiPlus op L1 vormt geen 3-fase eiland. De bestaande PV-omvormers op L2/L3 zijn in deze basisarchitectuur daarom niet beschikbaar als noodstroom-PV.
- Een echte 3-fase ESS/backuparchitectuur vereist ten minste één inverter/charger per fase.

### 9.6 DC-zijde

- `OPEN` — definitieve batterijbank/capaciteit.
- `OPEN` — definitieve DC-kabeldoorsnede, hoofdzekering, DC-disconnect, rails en batterijbeveiliging.
- Deze waarden worden vóór bestelling uit de actuele handleidingen van exact de gekozen MultiPlus-II- en batterijvariant gedimensioneerd.

### 9.7 Phase-aware ontwerpregel

De hardware- en softwarearchitectuur behandelen drie verschillende begrippen afzonderlijk:

1. **netto energiebalans** — som L1+L2+L3;
2. **fasebalans** — verdeling van import/export over L1/L2/L3;
3. **faseveiligheid** — stroom en beveiligingsgrens per afzonderlijke fase.

Een gunstige netto energiebalans betekent dus niet automatisch dat iedere fase lokaal in balans is. Dit wordt meegenomen in Tesla/Easee-, Victron- en toekomstige flexloadbesluiten.

### 9.8 Superseded hardwarevariant

- `SUPERSEDED` — de hybride SmartSolar/DC-PV-route uit rapport v35.1 is niet automatisch de actuele doelarchitectuur.
- `DECIDED` — de huidige werkarchitectuur houdt de bestaande PV-omvormers **AC-coupled**.
- Een DC-PV-route vereist een nieuwe string-/Vmp-/Voc-/temperatuurvalidatie voordat die opnieuw kandidaat kan worden.

Voor detailengineering geldt `docs/victron-hardware-baseline.md` als gespecialiseerde hardwarebron.

## 10. Documentstatus

- `REFERENCE / CANONICAL` — Integraal energierapport Victron ESS + Home Energy Management System **v37** blijft de integrale rapportbaseline totdat een nieuwe formele rapportversie wordt uitgebracht.
- `REFERENCE` — v35.1 blijft historische bron voor uitgebreide PV-/degradatieanalyse voor zover nieuwere besluiten die niet vervangen.
- `IMPLEMENTED / CANONICAL` — `requirements-traceability.md` koppelt requirements aan procesflow, implementatie, status en vrijgavecriteria.
- `IMPLEMENTED` — `docs/architectuur.md` bevat de bindende softwarearchitectuurinvarianten.
- `IMPLEMENTED` — `docs/victron-hardware-baseline.md` bevat de actuele gespecialiseerde Victron-hardwarearchitectuur.
- `IMPLEMENTED` — `docs/phase-aware-ems.md` bevat de fasebewuste EMS-regels.

## 11. Open validatieregister

1. `OPEN` — Contract History voldoende FIXED- en DYNAMIC-samples laten verzamelen en agreement beoordelen.
2. `OPEN` — WW Source Advice-kostenparameters valideren vóór enige fysieke cut-over.
3. `RESOLVED` — actuele Victron PV-topologie: bestaande PV blijft AC-coupled; faseposities zijn fysiek gevalideerd.
4. `OPEN` — definitieve batterijbank en vermogenslimieten bevestigen.
5. `OPEN` — definitieve Victron beveiligingsmatrix AC/DC.
6. `OPEN` — definitieve lijst backupgroepen achter AC-out.
7. `OPEN` — Live Stream blijven toetsen op rekenkundige energiebalans, directe versus afgeleide meetbronnen, >20 W-actiefdrempel en caching.

## 12. Requirements traceability als change-control

Iedere inhoudelijke wijziging die een functionele of niet-functionele requirement raakt, moet ook de betreffende ID in `requirements-traceability.md` bijwerken. Nieuwe requirements krijgen een nieuwe unieke ID.

## 13. Change-control

Bij iedere relevante wijziging:

1. requirement-ID bepalen of toevoegen;
2. wijziging ontwerpen;
3. architectuur- en Homey-loadimpact controleren;
4. Shadow/test waar fysieke sturing betrokken is;
5. runtime valideren;
6. requirements-traceability en deze projectbaseline aanpassen;
7. bijbehorende gespecialiseerde GitHub-documentatie tegelijk bijwerken;
8. oude aanpak expliciet `SUPERSEDED` markeren in plaats van stilzwijgend te laten voortbestaan.
