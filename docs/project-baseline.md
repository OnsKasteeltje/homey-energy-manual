# Canonieke projectbaseline — Home Energy Management System

_Status: 20 augustus 2026_

## Doel en bronhiërarchie

Dit document is de centrale referentie voor toekomstige ontwerp-, code- en documentatiebesluiten. Bij conflicten geldt deze volgorde:

1. actuele, runtime-gevalideerde implementatie;
2. recente expliciete projectbesluiten;
3. actuele GitHub-documentatie;
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

- `IMPLEMENTED/VERIFIED` — Energy Core v2 met centrale State, Decision, Shadow, warmwaterstate/-intent en publicatie.
- `IMPLEMENTED` — Quatt is `COMFORT_BASELOAD`, `OBSERVE_ONLY`, niet automatisch regelbaar.
- `IMPLEMENTED` — gedeeld `energy_budget` houdt rekening met gridreserve, Quatt-rampreserve, flex-exportbudget en discretionair importbudget.
- `DECIDED` — deadlines/MUST gaan vóór opportunistische PV-/prijsoptimalisatie.
- `DECIDED` — per fysieke actuator uiteindelijk exact één automatische writer.
- `DECIDED` — iedere fysieke Control-route gaat eerst door Shadow-validatie.

Let op: documentatie bevat nog verschillende genoemde Core-/Context-versies (o.a. Core v0.9.7 versus latere operationele updates). Versienummers zijn daarom pas `VERIFIED` wanneer runtime/publicatie ze bevestigt; de architectuurprincipes hierboven zijn leidend.

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
- `DECIDED` — Quatt is comfortload, niet automatisch flexload.
- `DECIDED` — thermisch vermogen/COP zijn diagnostiek en worden niet bij de elektrische energiebalans opgeteld.
- `OPEN` — fysieke Quatt-sturing vereist later een afzonderlijke veilige Control-policy en Shadow-validatie.

## 7. Live energie, meetkwaliteit en classificatie

- `DECIDED` — werkelijk gemeten P1-data wordt als gemeten behandeld, niet als indicatief.
- `DECIDED` — directe betrouwbare device-metingen hebben voor apparaatvermogen voorrang op afleiding.
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
- `OPEN` — definitieve batterijconfiguratie/capaciteit en definitieve PV-koppeling vóór bestelling opnieuw vastleggen in een nieuwe rapportversie.

## 10. Documentstatus

- `REFERENCE` — Integraal energierapport Victron ESS v35.1 blijft de laatste uitgebreide ontwerp-/analysebron voor hardware, PV-historie, dimensionering en businesscase.
- `SUPERSEDED/PARTIAL` — v35.1 is niet volledig actueel voor Homey/website/contractlogica en bevat een hybride SmartSolar-architectuur die na publicatie opnieuw is heroverwogen.
- `IMPLEMENTED` — actuele GitHub-documentatie bevat nieuwere Energy Core-, contract-, warmwater- en app-refreshbesluiten.
- `OPEN` — maak na consolidatie een nieuwe integrale rapportversie (v36) waarin de actuele architectuur en implementatiestatus zijn verwerkt.

## 11. Open validatieregister

1. Runtime-versies van Core Tick, Price/PV Context en relevante Control/Shadow-flows opnieuw inventariseren en documentatieversies harmoniseren.
2. Contract History voldoende FIXED- en DYNAMIC-samples laten verzamelen en agreement beoordelen.
3. WW Source Advice-kostenparameters valideren vóór enige fysieke cut-over.
4. Definitieve Victron PV-topologie (AC-coupled versus eventuele DC-route) technisch herbevestigen vóór bestelling.
5. Definitieve batterijbank en vermogenslimieten na keuze van PV-topologie bevestigen.
6. Live Stream blijven toetsen op rekenkundige energiebalans, directe versus afgeleide meetbronnen en >20 W-actiefdrempel.
7. Na bovenstaande punten Integraal energierapport v36 genereren en v35.1 als historische baseline markeren.

## 12. Change-control

Bij iedere relevante wijziging:

1. wijziging ontwerpen;
2. Shadow/test waar fysieke sturing betrokken is;
3. runtime valideren;
4. status in deze baseline aanpassen;
5. bijbehorende GitHub-documentatie tegelijk bijwerken;
6. oude aanpak expliciet `SUPERSEDED` markeren in plaats van stilzwijgend te laten voortbestaan.

Dit voorkomt dat oude chatbesluiten, rapportteksten en actuele productiecode door elkaar als gelijktijdig waar worden behandeld.
