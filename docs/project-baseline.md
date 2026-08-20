# Canonieke projectbaseline — Home Energy Management System

_Status: 20 augustus 2026_

## Doel en bronhiërarchie

Dit document is de centrale referentie voor toekomstige ontwerp-, code- en documentatiebesluiten. Bij conflicten geldt deze volgorde:

1. actuele, runtime-gevalideerde implementatie;
2. recente expliciete projectbesluiten;
3. `runtime-status-2026-08-20.md` en actuele GitHub-documentatie;
4. Integraal energierapport Victron ESS v35.1 voor hardware-, energieprofiel- en ontwerpachtergrond;
5. oudere rapport- en flowversies alleen als historie.

Statuslabels: `VERIFIED`, `IMPLEMENTED`, `SHADOW`, `DECIDED`, `OPEN`, `SUPERSEDED`.

## 1. Architectuur

- `VERIFIED` — Energy Core v2 gebruikt één centrale fysieke snapshot per 5 minuten en maximaal één `getDevices()` plus één `getVariables()` per Core Tick. Downstream-logica werkt in-memory op dezelfde revision.
- `VERIFIED` — P1 is leidend voor de netto woningbalans. Apparaatmetingen verklaren/classificeren belasting en mogen niet dubbel in de P1-balans worden verwerkt.
- `DECIDED` — Homey is huishoudelijke orkestratielaag. Installatieveiligheid en lokale apparaatbeveiligingen staan erboven.
- `DECIDED` — Victron wordt na installatie primaire batterij-/netregelaar; Homey blijft orkestreren over EV, warm water en andere flexloads.
- `VERIFIED` — Websitebezoek veroorzaakt geen Homey-devicecalls; de site leest gepubliceerde snapshots.

## 2. Huidige Energy Core

- `VERIFIED` — actuele publisher is `EM2_CORE_PUBLISH_V0.10.4` met publicatieschema `2.10`.
- `VERIFIED` — gecontroleerde runtime publiceerde State, Decision en Shadow revision-consistent op revision 924 en `control_mode = SHADOW`.
- `VERIFIED` — Core v0.10.4 splitst `grid_measurement_valid` en `derived_house_balance_valid`. Verse P1-data blijft autoritatief voor netimport/-export en flexbudget wanneer de afgeleide huis/PV-balans door `SOURCE_SKEW` ongeldig is.
- `IMPLEMENTED/VERIFIED` — Energy Core v2 bevat centrale State, Decision, Shadow, warmwaterstate/-intent en publicatie.
- `IMPLEMENTED` — Quatt is `COMFORT_BASELOAD`, `OBSERVE_ONLY`, niet automatisch regelbaar.
- `IMPLEMENTED` — gedeeld `energy_budget` houdt rekening met gridreserve, Quatt-rampreserve, flex-exportbudget en discretionair importbudget.
- `DECIDED` — deadlines/MUST gaan vóór opportunistische PV-/prijsoptimalisatie.
- `DECIDED` — per fysieke actuator uiteindelijk exact één automatische writer.
- `DECIDED` — iedere fysieke Control-route gaat eerst door Shadow-validatie.

Oudere documentatie die Core v0.9.7/schema 2.5 als actief noemt, beschrijft een eerdere gevalideerde toestand. Voor actuele versienummers is `runtime-status-2026-08-20.md` plus de live publicatie leidend.

## 3. Contract- en prijsarchitectuur

- `IMPLEMENTED/SHADOW` — ondersteunde contracttypes zijn uitsluitend `FIXED` en `DYNAMIC`.
- `IMPLEMENTED/SHADOW` — beide contracttypes normaliseren naar één uniforme prijscontext voordat downstream beslislogica de prijs gebruikt.
- `IMPLEMENTED/SHADOW` — `FIXED` gebruikt configureerbare import-/exporttarieven en heeft geen PBTH-afhankelijkheid.
- `IMPLEMENTED/SHADOW` — `DYNAMIC` gebruikt PBTH/DAP15 en classificeert prijs in de adapter; downstream M7-prijsafhankelijkheid is niet de doelarchitectuur.
- `DECIDED` — vaste dagelijkse contractkosten zijn geen marginale optimalisatie-input.
- `IMPLEMENTED` — prijscontext is null-safe; ontbrekende prijs is nooit impliciet EUR 0/kWh.
- `IMPLEMENTED/SHADOW` — prijshorizon bepaalt of prijs FULL, INTRADAY of alleen DIAGNOSTIC mag worden gebruikt.
- `IMPLEMENTED/SHADOW` — Contract History v0.1 verzamelt rolling kwartierdata zonder devicepolling of actuatorwrites.

## 4. Warm water

- `DECIDED` — comfortdoel en catch-up/deadline hebben voorrang op pure economische optimalisatie.
- `IMPLEMENTED/SHADOW` — confirmed-heating gebruikt werkelijk boilervermogen, niet alleen relais-aan-tijd.
- `VERIFIED` — actuele warmwaterstate is `EM2_WW_STATE_V0.8`.
- `VERIFIED` — actuele Warm Water Control is `EM2_CONTROL_WW_V0.11`, `SHADOW` en read-only.
- `IMPLEMENTED/SHADOW` — BOILER↔CV-bronkeuze vergelijkt marginale kosten per bruikbare kWh warmte.
- `IMPLEMENTED/SHADOW` — bij PV-export telt gemiste terugleverwaarde als opportunity cost; PV is economisch niet automatisch gratis.
- `IMPLEMENTED/SHADOW` — bronselector gebruikt hysterese en fail-safe `KEEP_CURRENT` bij stale/ongeldige inputs.
- `VERIFIED` — `WW_Boilermodus` blijft tijdens Shadow operationeel leidend; WW Source Advice verricht geen fysieke write.
- `OPEN` — rendementen, calorische gaswaarde en hysterese valideren vóór operationele cut-over.
- `OPEN` — voldoende FIXED- en DYNAMIC-shadowhistorie verzamelen vóór koppeling aan bron-/actuatorwrite.

## 5. Tesla / Easee

- `DECIDED` — Tesla is flexload met deadline/MUST boven opportunistische optimalisatie.
- `IMPLEMENTED` — PV-opportunity gebruikt beschikbaar flexbudget in plaats van blind kale P1-export.
- `VERIFIED` — Easee Equalizer blijft autonome harde load-balancing en mag door Homey niet worden overruled.
- `DECIDED` — werkelijk laadvermogen is belangrijker voor classificatie dan alleen gevraagd setpoint.

## 6. Quatt

- `IMPLEMENTED/VERIFIED` — primaire elektrische bron is Quatt CIC `measure_power` uit dezelfde Core-snapshot.
- `VERIFIED` — runtime publiceert Quatt als `COMFORT_BASELOAD`, `OBSERVE_ONLY`, `controllable=false`.
- `DECIDED` — Quatt is comfortload, niet automatisch flexload.
- `DECIDED` — thermisch vermogen/COP zijn diagnostiek en worden niet bij de elektrische energiebalans opgeteld.
- `OPEN` — fysieke Quatt-sturing vereist later een afzonderlijke veilige Control-policy en Shadow-validatie.

## 7. Live energie, meetkwaliteit en classificatie

- `VERIFIED` — P1/netmeting kan geldig blijven terwijl de afgeleide huis/PV-balans ongeldig is; `SOURCE_SKEW` in PV-bronnen degradeert de directe P1-meting niet.
- `DECIDED` — werkelijk gemeten P1-data wordt als gemeten behandeld, niet als indicatief.
- `DECIDED` — directe betrouwbare device-metingen hebben voor apparaatvermogen voorrang op afleiding.
- `VERIFIED` — wasmachine en droger kunnen via directe AEG-status worden geclassificeerd; idle wordt gepubliceerd als `AEG_DIRECT_IDLE` zonder geschat vermogen.
- `DECIDED` — alleen waar directe meting ontbreekt mag vermogen worden afgeleid uit de woningbalans/context; dit moet als afgeleid/indicatief herkenbaar blijven.
- `DECIDED` — kleine niet-herleidbare restbelasting hoort semantisch bij `Overig klein`/restlast en niet bij een willekeurig inactief apparaat.
- `DECIDED` — standby/lekstroom onder 20 W wordt niet als actieve energieverbruiker weergegeven.
- `DECIDED` — energiebalans moet rekenkundig sluiten; `NEGATIVE_HOUSE_BALANCE` is een diagnose die onderzoek vereist, geen normale toestand.

## 8. Website/app-refresh

- `IMPLEMENTED` — appdata wordt bij boot/openen expliciet opnieuw opgevraagd.
- `IMPLEMENTED` — periodieke datarefresh iedere 5 minuten.
- `IMPLEMENTED` — refresh bij terugkeer via visibility/pageshow/focus en opnieuw online komen.
- `IMPLEMENTED` — pull-to-refresh forceert eerst datarefresh; service-worker/assets en reload zijn aanvullend en niet de enige refreshstrategie.
- `IMPLEMENTED` — freshness-indicatie onderscheidt actueel, vertraagd en verouderd.
- `DECIDED` — navigeren History↔Live mag geen oude cached foutmelding/context terugbrengen.

## 9. Victron-doelarchitectuur

- `DECIDED` — hoofdaansluiting 3×25 A; MultiPlus-II 48/5000 als 1-fase ESS op L1; Cerbo GX MK2; VM-3P75CT centrale 3-fasemeting.
- `DECIDED` — VM meet L1/L2/L3 centraal; ESS gebruikt `Total of all phases` voor de netbalans terwijl MultiPlus fysiek op L1 werkt.
- `DECIDED` — VM staat in de meterkast; Cerbo/MultiPlus/batterij in de schuur; communicatie via lokaal netwerk.
- `DECIDED` — bestaande schuurverbinding is circa 20 m 5G2,5 mm² en wordt als 3×16 A behandeld totdat installatiegegevens anders bevestigen.
- `DECIDED` — GX Touch is optioneel.
- `SUPERSEDED` — de hybride SmartSolar/DC-PV-route uit rapport v35.1 is niet automatisch de actuele doelarchitectuur. Na latere projectanalyse is teruggekeerd naar AC-coupled als werkhypothese wegens string-/Vmp-compatibiliteit. Dit punt moet vóór bestelling nog technisch tegen actuele paneel/stringgegevens en Victron-specificaties worden herbevestigd.
- `OPEN` — definitieve batterijconfiguratie/capaciteit en definitieve PV-koppeling vóór bestelling opnieuw vastleggen.

## 10. Documentstatus

- `REFERENCE` — Integraal energierapport Victron ESS v35.1 blijft de laatste uitgebreide ontwerp-/analysebron voor hardware, PV-historie, dimensionering en businesscase.
- `SUPERSEDED/PARTIAL` — v35.1 is niet volledig actueel voor Homey/website/contractlogica en bevat een hybride SmartSolar-architectuur die na publicatie opnieuw is heroverwogen.
- `IMPLEMENTED` — `runtime-status-2026-08-20.md` legt de actuele Core v0.10.4/schema 2.10-status vast.
- `IMPLEMENTED` — actuele GitHub-documentatie bevat nieuwere Energy Core-, contract-, warmwater- en app-refreshbesluiten.
- `IN_PROGRESS` — Integraal energierapport v36 wordt opgebouwd vanuit deze canonieke baseline.

## 11. Open validatieregister

1. `RESOLVED` — runtime-versie Core Tick/publicatie geïnventariseerd: v0.10.4, schema 2.10, SHADOW; oudere v0.9.7-status is historisch.
2. `OPEN` — exacte actuele Price/PV Context-flowversie bij volgende Homey-runtime-audit expliciet vastleggen indien die niet uit publicatie blijkt.
3. `OPEN` — Contract History voldoende FIXED- en DYNAMIC-samples laten verzamelen en agreement beoordelen.
4. `OPEN` — WW Source Advice-kostenparameters valideren vóór enige fysieke cut-over.
5. `OPEN` — definitieve Victron PV-topologie (AC-coupled versus eventuele DC-route) technisch herbevestigen vóór bestelling.
6. `OPEN` — definitieve batterijbank en vermogenslimieten na keuze van PV-topologie bevestigen.
7. `OPEN` — Live Stream blijven toetsen op rekenkundige energiebalans, directe versus afgeleide meetbronnen en >20 W-actiefdrempel.
8. `IN_PROGRESS` — Integraal energierapport v36 genereren en v35.1 als historische baseline markeren.

## 12. Change-control

Bij iedere relevante wijziging:

1. wijziging ontwerpen;
2. Shadow/test waar fysieke sturing betrokken is;
3. runtime valideren;
4. status in deze baseline aanpassen;
5. bijbehorende GitHub-documentatie tegelijk bijwerken;
6. oude aanpak expliciet `SUPERSEDED` markeren in plaats van stilzwijgend te laten voortbestaan.

Dit voorkomt dat oude chatbesluiten, rapportteksten en actuele productiecode door elkaar als gelijktijdig waar worden behandeld.
