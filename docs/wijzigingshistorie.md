# Wijzigingshistorie

## v2.8.7 — 16 augustus 2026

- Nieuwe hoofdtab **Energiehistorie** toegevoegd op basis van het goedgekeurde lijn-diagramconcept.
- Bovenaan keuze tussen **Dag**, **Week** en **Maand**; dezelfde dashboardstructuur wordt per periode hergebruikt.
- **Dag** gebruikt de bestaande 24-uurs fasepublicatie en toont als lijnreeksen: **PV-productie**, **woningverbruik**, **netimport**, **netexport** en voorbereide **accu**-reeksen.
- Dagkengetallen worden uit de meetreeks naar kWh geïntegreerd; direct eigen PV-verbruik wordt boekhoudkundig afgeleid uit PV-productie en woningverbruik.
- **Week** en **Maand** gebruiken de bestaande compacte `energy-daily-history.json`; historische dekking wordt expliciet als gedeeltelijk getoond zolang nog maar weinig dagen zijn opgebouwd.
- Accu geladen/ontladen is vanaf nu onderdeel van het UI-datamodel, maar blijft bewust **0 / nog geen opslagmeting** totdat Victron-data beschikbaar is.
- Nieuwe **Energiebalans**-sectie toegevoegd onder de grafiek.
- Nieuwe **Activiteitstijdlijn** toegevoegd die waar mogelijk wasmachine-, droger- en boilerstatusovergangen uit de bestaande baseline toont zonder individueel vermogen te verzinnen.
- Geen extra Homey-polling toegevoegd; de pagina gebruikt uitsluitend reeds gepubliceerde GitHub-data.
- Responsive styling toegevoegd zodat de hoofdkengetallen en onderste panelen op mobiel onder elkaar schalen.

## v2.8.6 — 16 augustus 2026

- Pijlen in **Live energiestroom** visueel rustiger gemaakt: lijndikte blijft afhankelijk van de grootte van de vermogensstroom, maar de variatie is bewust begrensd.
- Pijlpunten zijn iets kleiner gemaakt voor betere leesbaarheid op mobiel.
- Wanneer **Wasmachine** of **Droger** alleen via Homey-status als **ACTIEF** bekend is, krijgt de betreffende connector dezelfde visuele dikte als **Overig verbruik**; er wordt nog steeds geen fictief wattage toegekend.
- De afzonderlijke, horizontaal uitgelijnde connectoren vanaf **Huis** blijven behouden; er is geen gedeelde vermogensbus geïntroduceerd.

## v2.8.5 — 16 augustus 2026

- **Tesla laadregeling** toegevoegd onder de live energiestroom als compacte keten **Homey vraagt → Easee Equalizer → werkelijk naar Tesla**.
- De logica gebruikt het actuele Homey-laadverzoek (`targetA`) en de werkelijk geschatte Tesla-laadstroom (`teslaActualAEst`).
- Als er geen actief laadverzoek is, wordt expliciet **begrenzing niet actief** getoond; de Equalizer meet de hoofdaansluiting dan wel continu, maar grijpt niet in op een stilstaande lader.
- Alleen wanneer er daadwerkelijk wordt geladen en de werkelijke laadstroom lager is dan gevraagd, wordt dit als **mogelijk begrensd** gemarkeerd.
- De Easee-waarde **Beschikbaar** wordt nog niet door de huidige Homey/GitHub-dataset gepubliceerd en wordt daarom niet geschat of als feit weergegeven.
- Voor deze versie wordt opnieuw een uniek JavaScript-bestand geladen om mobiele browsercache te omzeilen.

## v2.8.4 — 16 augustus 2026

- Voor **wasmachine** en **droger** wordt de connector nu ook duidelijk dik weergegeven wanneer Homey alleen de status **ACTIEF** kent en nog geen afzonderlijk wattage beschikbaar is.
- In dat geval betekent de lijndikte uitsluitend *apparaat actief*; er wordt geen fictief vermogen aan de energiebalans toegevoegd.

## v2.8.3 — 16 augustus 2026

- **Live energiestroom** gebruikt een nieuw versienummer voor het JavaScript-bestand zodat mobiele browsers, met name Safari, niet de eerder gecachte visualisatie blijven tonen.
- De afgesproken uitlijning uit v2.8.2 wordt daardoor betrouwbaar geladen: de horizontale segmenten tussen **Huis** en de vijf onderliggende verbruikers liggen op één gelijke hoogte.
- De vijf connectoren blijven afzonderlijke paden met een eigen lijnsterkte per belasting; er is dus geen gedeelde vermogensbus geïntroduceerd.

## v2.8.2 — 16 augustus 2026

- De afzonderlijke verbindingen van **Huis** naar Tesla, boiler, wasmachine, droger en overig verbruik zijn visueel verder uitgelijnd.
- Alle horizontale delen van deze vijf connectoren liggen nu op exact dezelfde hoogte, overeenkomstig de uitlijning van de PV-connectoren boven het huis.
- Iedere verbinding blijft technisch en visueel een individueel pad, zodat de lijnsterkte uitsluitend het vermogen van die specifieke belasting weergeeft.

## v2.8.1 — 16 augustus 2026

- **Live energiestroom** aangepast zodat de verbinding van **Huis** naar iedere onderliggende verbruiker afzonderlijk wordt getekend.
- De gedeelde horizontale vermogensbus tussen Huis en de verbruikers is verwijderd.
- Lijnsterkte wordt nu per individuele belasting bepaald; daardoor wordt alleen de connector naar een werkelijk verbruikende component dik weergegeven.
- Inactieve of niet-gemeten verbruikers behouden een dunne/lichte eigen verbinding en beïnvloeden de andere connectoren niet.
- Dit is de eerste websitewijziging volgens de nieuwe patch-/subversieregel: normale websiteaanpassingen verhogen voortaan het derde versienummer.

## v2.8 — 16 augustus 2026

- **Live energiestroom** visueel herontworpen volgens het goedgekeurde dashboardbeeld.
- De drie PV-omvormers staan bovenaan als afzonderlijke productiebronnen.
- **Grid/P1** staat links, **Huis** centraal en de toekomstige **Victron-batterij** rechts.
- Schuine energielijnen zijn vervangen door duidelijke **orthogonale verbindingen met 90° hoeken** en korte verticale aansluitingen op componenten.
- Productie, net/verbruik en de toekomstige batterij hebben afzonderlijke visuele lijnstijlen.
- De bestaande live Homey/GitHub-databronnen en het verversingsritme van 5 minuten zijn ongewijzigd gebleven; dit is uitsluitend een presentatieverbetering.

## v2.7 — 16 augustus 2026

- Homepage conceptueel vereenvoudigd: het dashboard toont voortaan **functionele capabilities/systemen** in plaats van iedere afzonderlijke Homey-flow.
- Per capability wordt slechts één actuele implementatie getoond, inclusief de echte Homey-flownaam, enabled-status en broken-status.
- Oude, uitgeschakelde en experimentele flowversies verdwijnen daarmee van het operationele homepage-dashboard; deze blijven onderdeel van de technische flowdocumentatie.
- Eerste capabilities: **Warmwateroptimalisatie**, **Energie Manager**, **Tesla-regeling**, **M7 Opportunity**, **Prijs- en PV-forecast** en **Website-statuspublicatie**.
- De homepage maakt daarmee expliciet onderscheid tussen *wat de woning/Homey functioneel doet* en *welke concrete flowversie dit technisch implementeert*.
- Dit sluit aan op de projectfocus **woning + Homey klaar voor Victron**: de homepage fungeert als operationeel architectuurdashboard, terwijl detailpagina's de technische flowimplementatie en versiehistorie tonen.

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

## v2.4 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Energie Manager PV - Shadow Mode v1.6.6`** gedocumenteerd; v1.6.5 is uitgeschakeld zodat binnen deze flowfamilie slechts één versie actief is.
- v1.6.6 blijft volledig **shadow/read-only** en voegt geen fysieke apparaatsturing toe.
- De bestaande baseline-publicatie is uitgebreid met `washerActive` en `dryerActive`.

## v2.3 — 16 augustus 2026

- **Live energiestroom** uitgebreid met een uitsplitsing onder **Huishouden** voor **Wasmachine**, **Droger**, **Vaatwasser** en **Overig huishouden**.
- Er wordt bewust geen extra Homey-polling of nieuwe meetflow toegevoegd.

## v2.2 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Energie Manager PV - Shadow Mode v1.6.5`** toegevoegd; v1.6.4 is uitgeschakeld.
- Energy Manager-observatie uitgebreid met P1 L1/L2/L3 en Easee/Equalizer-context.

## v2.1 — 16 augustus 2026

- **Easee Equalizer** expliciet vastgelegd als harde lokale load-balancing-/veiligheidslaag.
- Regelhiërarchie toegevoegd: **installatieveiligheid / 3×25 A → Easee Equalizer → Victron grid/batterijregeling (later) → Homey Energy Manager → flexibele verbruikers**.

## v2.0 — 16 augustus 2026

- Nieuwe hoofdtab **Live energiestroom** toegevoegd.
- Energy Manager expliciet als besturings-/orchestratie-laag buiten het elektrische stroompad weergegeven.
- Nieuwe 24-uurs fasevisualisatie toegevoegd voor L1, L2 en L3.

## v1.9 — 15 augustus 2026

- Opmaak van de volledige wijzigingshistorie geüniformeerd; nieuwste versie staat voortaan bovenaan.

## v1.8 — 15 augustus 2026

- De drie PV-omvormers als afzonderlijke apparaten aan **Groepen & fasen** toegevoegd.

## v1.7 — 15 augustus 2026

- **Groepen & fasen** bijgewerkt met bevestigde fasekoppelingen en versiebeheerregel aangescherpt.

## v1.6 — 15 augustus 2026

- Nieuwe hoofdtab **Groepen & fasen** toegevoegd.

## v1.5 — 15 augustus 2026

- Architectuuroverzicht uitgebreid met energieprioriteit, constraints en toekomstige Victron-laag.

## v1.4 — 15 augustus 2026

- Warmwaterpagina uitgebreid tot volledige functionele handleiding.

## v1.3 — 14 augustus 2026

- Huidig en gepland boilervenster verduidelijkt.

## v1.2 — 14 augustus 2026

- Warmwaterhoofdstuk bijgewerkt.

## v1.1 — 14 augustus 2026

- Energie Manager PV - Shadow Mode toegevoegd.

## v1.0 — 14 augustus 2026

- Eerste versie van de Homey Flow Manual gepubliceerd.
