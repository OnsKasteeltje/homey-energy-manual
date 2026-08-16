# Wijzigingshistorie

## v2.6 — 16 augustus 2026

- Homepage-statusprobleem structureel bij de bron opgelost: de algemene Homey-statuspublisher selecteert voor geversioneerde flowfamilies voortaan de **actieve, niet-broken versie** in plaats van één oude exact vastgelegde flownaam.
- Nieuwe actieve systeemflow **`GitHub status sync - Homey lokaal v1.2`** aangemaakt en gevalideerd; de oude ongenummerde statuspublisher is daarna uitgeschakeld.
- De nieuwe publisher publiceerde succesvol **`Warm water optimalisatie - PV boiler + CV advies v1.2 nacht-test`** als actief en **`Energie Manager PV - Shadow Mode v1.6.6`** als actieve shadowversie.
- Ook **`M7 - Opportunity Score - Shadow v1.3`** wordt nu automatisch als actuele actieve versie van die flowfamilie herkend.
- Homepage-links zijn family-aware gemaakt, zodat geversioneerde warmwater-, Energy Manager-, M7- en status-syncflows naar de juiste documentatie blijven linken.
- Hiermee is de statusweergave niet meer afhankelijk van handmatige aanpassing van de homepage wanneer een hoofdflow een nieuwe subversie krijgt.

## v2.5 — 16 augustus 2026

- Homepage-status van de **Energie Manager PV** gecorrigeerd zodat niet langer de oude ongenummerde, uitgeschakelde flow als hoofdstatus wordt getoond.
- De homepage gebruikt voor de actuele Energy Manager-versie en enabled-status aanvullend `shadow-baseline-v01.json` als operationele bron.
- Daardoor wordt de daadwerkelijk publicerende nieuwste flowversie — momenteel **`Energie Manager PV - Shadow Mode v1.6.6`** — op de homepage als **Actief** weergegeven.
- De algemene Homey-status blijft uit `homey-status.json` komen; alleen de logische hoofdstatus van deze geversioneerde flowfamilie wordt tegen de actuele baseline gereconcilieerd.
- Bij tijdelijke onbeschikbaarheid van de baseline valt de homepage veilig terug op de reguliere Homey-statusweergave.

## v2.4 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Energie Manager PV - Shadow Mode v1.6.6`** gedocumenteerd; v1.6.5 is uitgeschakeld zodat binnen deze flowfamilie slechts één versie actief is.
- v1.6.6 blijft volledig **shadow/read-only** en voegt geen fysieke apparaatsturing toe.
- De bestaande baseline-publicatie is uitgebreid met `washerActive` en `dryerActive`.
- `washerActive` en `dryerActive` worden uitsluitend `true` wanneer Homey `measure_applianceState = RUNNING` rapporteert.
- De bestaande runtime-state **`EM Shadow Runtime State v1.6.5`** wordt bewust hergebruikt om de boiler-state-machine en een eventueel lopende cyclus niet te onderbreken bij de versieovergang.
- De Live energiestroom-documentatie is bijgewerkt: **Wasmachine (L2)** en **Droger (L3)** kunnen nu als `ACTIEF`/`idle` worden weergegeven zonder extra Homey-polling.
- Omdat de Homey-apparaten van wasmachine en droger geen individueel live vermogen leveren, wordt bewust geen wattage afgeleid of verzonnen; hun verbruik blijft onderdeel van de huishoudelijke sluitpost.
- **Vaatwasser** blijft in de visualisatie voorbereid en krijgt een live status zodra een betrouwbare statusbron in de bestaande publicatie wordt opgenomen.

## v2.3 — 16 augustus 2026

- **Live energiestroom** uitgebreid met een uitsplitsing onder **Huishouden** voor **Wasmachine**, **Droger**, **Vaatwasser** en **Overig huishouden**.
- Er wordt bewust geen extra Homey-polling of nieuwe meetflow toegevoegd; de visualisatie gebruikt uitsluitend reeds gepubliceerde data.
- Een grootverbruiker krijgt alleen een eigen live wattage zodra dat vermogen daadwerkelijk in de bestaande publicatiedata beschikbaar is.
- Zolang een afzonderlijk vermogen ontbreekt, toont de kaart expliciet **niet afzonderlijk gemeten** in plaats van een waarde af te leiden of te verzinnen.
- **Overig huishouden** blijft de sluitpost, zodat de totale huishoudelijke energiebalans intact blijft.

## v2.2 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Energie Manager PV - Shadow Mode v1.6.5`** toegevoegd; v1.6.4 is uitgeschakeld zodat slechts één versie van deze flowfamilie actief is.
- v1.6.5 blijft volledig **shadow/read-only** en stuurt geen apparaten aan.
- Energy Manager-observatie uitgebreid met **P1 L1/L2/L3**, Easee `target_charger_current`, werkelijk Tesla-laadvermogen, geschatte werkelijke laadstroom en geleverd/gevraagd-verhouding.
- Nieuwe afgeleide `equalizerState` toegevoegd met conservatieve statussen `NOT_APPLICABLE`, `NOT_LIMITED`, `LIMITED` en `PAUSED_OR_BLOCKED`.
- `LIMITED` wordt alleen gebruikt wanneer Tesla werkelijk laadt, minimaal 6 A target zichtbaar is en minder dan 82% van het bijbehorende 3-fase vermogen wordt geleverd.
- Een gepauzeerde Tesla wordt bewust **niet automatisch** als Equalizer-begrenzing geïnterpreteerd.
- Nieuwe Flow-tags toegevoegd: `EM Shadow Tesla gevraagd A`, `EM Shadow Tesla werkelijk A est` en `EM Shadow Equalizer status`.
- De eerste v1.6.5-run is succesvol gepubliceerd in `shadow-baseline-v01.json`; de praktijktest van een echte Equalizer-terugregeling staat nog open voor een volgende Tesla-laadsessie met extra huishoudelijke belasting.

## v2.1 — 16 augustus 2026

- **Easee Equalizer** expliciet vastgelegd als harde lokale load-balancing-/veiligheidslaag die altijd voorrang heeft boven Homey-orchestratie.
- Regelhiërarchie toegevoegd: **installatieveiligheid / 3×25 A → Easee Equalizer → Victron grid/batterijregeling (later) → Homey Energy Manager → flexibele verbruikers**.
- Vastgelegd dat de Energy Manager onderscheid moet maken tussen **gevraagde Tesla-laadstroom** en **werkelijk door Easee geleverd vermogen**.
- Vervolgbeslissingen moeten worden gebaseerd op werkelijke Tesla-belasting en actuele **P1/L1/L2/L3**-waarden, niet alleen op het Homey-setpoint.
- Regel toegevoegd dat een Equalizer-ingreep niet automatisch mag leiden tot directe herverdeling van vermogen naar de boiler.
- Ontwerpregel toegevoegd voor **1–2 minuten stabilisatie/hysterese** na onverwacht terugregelen of pauzeren van Tesla; definitieve waarde wordt vóór actieve orchestratie in shadow mode gevalideerd.
- De actieve `Energie Manager PV - Shadow Mode v1.6.4` is hiervoor **niet functioneel gewijzigd**; dit is vastgelegd als doelarchitectuur en constraint voor de toekomstige actieve regeling.

## v2.0 — 16 augustus 2026

- Nieuwe hoofdtab **Live energiestroom** toegevoegd.
- Visualisatie architectonisch gecorrigeerd: de **Energy Manager** is een besturings-/orchestratie-laag en ligt nadrukkelijk **niet in het elektrische stroompad**.
- De live plaat bestaat nu uit twee gescheiden lagen: **Besturing / orchestratie** en **Fysieke / boekhoudkundige energiestroom**.
- Fysieke energielaag opgebouwd rond **PV-bronnen → huisbus ↔ Grid/P1 → huishouden / Tesla / boiler**.
- Dunne stuurlijnen vanuit de Energy Manager worden visueel onderscheiden van de dikkere energiestroomlijnen.
- Lijndikte van energiestromen schaalt mee met het actuele vermogen; import en export worden richtinggevoelig weergegeven.
- De bestaande prioriteitslogica **huishouden → Tesla → boiler → net** blijft zichtbaar, met expliciete vermelding dat de individuele PV-toewijzing boekhoudkundig wordt afgeleid.
- Nieuwe 24-uurs fasevisualisatie toegevoegd voor **L1, L2 en L3** op de pagina **Groepen & fasen**.
- Fase-monitor en fasepublisher geversioneerd naar **v1.1**; oudere v1.0-versies uitgeschakeld zodat per functie slechts één versie actief is.
- Architectuurprincipe aangescherpt: **Homey zo licht mogelijk houden**; historische analyse, correlatie en visualisatie zoveel mogelijk uitvoeren vanuit reeds gepubliceerde data op GitHub/de website.
- Nachtelijke boileracceptatietest als **GESLAAGD** gedocumenteerd, inclusief de gevalideerde keten `VERWARMEN → AFKOELEN_WACHT → OP_TEMPERATUUR → boiler-cycles.json`.

## v1.9 — 15 augustus 2026

- Opmaak van de volledige wijzigingshistorie geüniformeerd.
- Alle versies gebruiken voortaan hetzelfde sectieformaat als v1.4 en hoger.
- De volgorde is gewijzigd naar **nieuwste versie eerst**, daarna aflopend.
- De voormalige compacte tabel voor v1.0 t/m v1.3 is vervangen door afzonderlijke versieblokken.

## v1.8 — 15 augustus 2026

- De drie bestaande PV-omvormers zijn als afzonderlijke apparaten aan **Groepen & fasen** toegevoegd: **SolarEdge SE3680H**, **GoodWe GW4200D-NS** en **GoodWe GW2000-XS**.
- Per omvormer worden voortaan afzonderlijk fase, groep/automaat en betrouwbaarheidsstatus bijgehouden.
- Vastgelegd dat de SolarEdge SE3680H en GoodWe GW4200D-NS in de schuuropstelling zitten en de GoodWe GW2000-XS op een andere locatie in de woning staat.
- De huidige fase- en groepkoppeling van de drie omvormers blijft **Open** totdat deze met een gerichte fase- of uitschakeltest is bevestigd.
- Meetmethode uitgebreid met de werkwijze voor fase-identificatie van PV-omvormers.

## v1.7 — 15 augustus 2026

- **Groepen & fasen** bijgewerkt met de inmiddels bevestigde fasekoppelingen van de elektrische boiler (**L2**) en waterkoker (**L2**), naast wasmachine (**L2**) en droger (**L3**).
- Tesla/Easee expliciet als 3-fase verbruiker (**L1 + L2 + L3**) opgenomen.
- Schuurvoeding toegevoegd als **waarschijnlijk groep 14, 3-polig B16**, met expliciete vermelding dat dit nog fysiek moet worden bevestigd.
- Statusweergave aangescherpt zodat duidelijk onderscheid wordt gemaakt tussen een **bevestigde fase** en een nog **open groep/automaat**.
- Beheerregel vastgelegd: nieuwe betrouwbare inzichten over fase- of groepindeling worden voortaan direct op de website verwerkt.
- Versiebeheerregel aangescherpt: iedere inhoudelijke websitewijziging krijgt voortaan direct een nieuwe website-subversie; automatische JSON-/status-/sample-updates verhogen het websiteversienummer niet.

## v1.6 — 15 augustus 2026

- Nieuwe hoofdtab **Groepen & fasen** toegevoegd.
- Wasmachine op **L2** en droger op **L3** vastgelegd op basis van praktijktests met P1-fasemeting.
- Overzicht toegevoegd voor waarschijnlijke, bevestigde en nog open fase-/groepkoppelingen van belangrijke apparaten.
- Meetmethode en vervolgstappen voor het bepalen van exacte installatieautomaten gedocumenteerd.

## v1.5 — 15 augustus 2026

- Architectuuroverzicht uitgebreid met volledige energieprioriteit, constraints, Quooker-vensters, warmwaterbronselectie, Tesla-laadmonitoring, shadow/actief onderscheid, fail-safe regels en toekomstige Victron-laag.

## v1.4 — 15 augustus 2026

- Warmwaterpagina uitgebreid tot volledige functionele handleiding.
- Dagelijkse beslislogica, Tesla-prioriteit, seizoensadvies, 2027-regels, fail-safe gedrag en huidig versus gepland tijdvenster expliciet beschreven.

## v1.3 — 14 augustus 2026

- Huidig en gepland boilervenster verduidelijkt.

## v1.2 — 14 augustus 2026

- Warmwaterhoofdstuk bijgewerkt.

## v1.1 — 14 augustus 2026

- Energie Manager PV - Shadow Mode toegevoegd.

## v1.0 — 14 augustus 2026

- Eerste versie van de Homey Flow Manual gepubliceerd.
