# Wijzigingshistorie

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
