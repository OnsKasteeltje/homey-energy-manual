# Wijzigingshistorie

## v2.8.23 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Tesla laden v2.5`**; v2.4 is uitgeschakeld zodat slechts één automatische Easee-writer actief blijft.
- Iedere nieuwe website-`requestId` krijgt voortaan exact één immutable Easee `meter_power`-baseline, samen met huidige SOC, doel-SOC, SOC-tijdstip, kalibratiefactor en exact vastlegtijdstip.
- Reboot, flow-upgrade, M7-wijziging of Equalizerstatus kan de baseline niet meer resetten; alleen een nieuwe SOC/deadline-opdracht maakt een nieuwe baseline.
- Nieuwe fail-safe status **`BASELINE_FOUT`** stopt de automatische laadopdracht wanneer bij een actieve deadline geen geldige meterbasis beschikbaar is.
- Nieuwe sanity-check markeert **`KALIBRATIE_AFWIJKING`** wanneer de gemeten Easee-delta groter wordt dan 1,5× het berekende doel plus 0,25 kWh; de factor 0,59 kWh/% wordt nooit automatisch aangepast.
- Bestaande v2.4-sessies worden niet opnieuw gebaselineerd maar alleen als **`legacy-unverified`** overgenomen.
- Nieuwe **`Tesla runtime publicatie v1.2`** publiceert de volledige baseline-audit; v1.1 is uitgeschakeld.
- Live energiestroom toont vanaf v2.8.23 een **Laadmeting controle** met SOC-moment, Easee-baseline, actuele meterstand en werkelijk geladen kWh sinds de baseline.
- De huidige 84% → 90%-sessie is gereconstrueerd als **7745,87 → 7752,36 kWh = 6,49 kWh** en terecht als legacy/afwijkend gemarkeerd; deze sessie wordt niet gebruikt om de kalibratiefactor te wijzigen.
- Homepage-runtime bijgewerkt naar `home-tesla-runtime-v1.13.js` en functionele documentatie van Live energiestroom en de beveiligde Tesla write-route tegelijk bijgewerkt.

## v2.8.22 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Tesla laden v2.4`**; v2.3 is uitgeschakeld zodat slechts één automatische Easee-writer actief is.
- Equalizer-gedrag uitgebreid van alleen gedeeltelijk begrenzen naar vier expliciete runtime-modi: `normal`, `limited`, `blocked_pending` en `blocked`.
- Een volledige blokkade wordt pas na circa 4 minuten bevestigd wanneer Homey minimaal 6 A vraagt, de Tesla aangesloten is en het werkelijke laadvermogen vrijwel 0 W blijft.
- Homey houdt tijdens een Equalizer-blokkade het laadverzoek bewust actief zodat Easee automatisch kan hervatten zodra andere grootverbruikers wegvallen.
- Deadline-statussen toegevoegd voor **Equalizer blokkeert**, **Deadline onder druk** en **Deadline niet haalbaar**; alleen werkelijk geleverde Easee-kWh telt als voortgang.
- Nieuwe **`Tesla runtime publicatie v1.1`** publiceert de Equalizer-modus naar de website; v1.0 is uitgeschakeld.
- Homepage-runtime bijgewerkt naar `home-tesla-runtime-v1.12.js`, inclusief gevraagd → werkelijk laadniveau en volledige blokkade.
- Functionele documentatie op homepage, Live energiestroom en de Tesla write-route tegelijk bijgewerkt.

## v2.8.21 — 16 augustus 2026

- Tesla-regeling uitgebreid naar **`Tesla laden v2.3`** met deadline + M7 prijs/PV-context.
- Betekenis van `M7_PV_Top4h` gecorrigeerd: het huidige uur behoort tot de vier beste PV-forecasturen; het signaal voorspelt niet dat later meer PV komt.
- Iedere nieuwe website-`requestId` reset de laadvoortgang vanaf de actuele Easee-meterstand zodat een nieuwe handmatige SOC-invoer een schoon vertrekpunt heeft.
- `Latest start` blijft een harde deadlinegrens; prijs en forecast mogen alleen vóór dat moment optimaliseren.

## v2.8.20 — 16 augustus 2026

- Runtime-publicatie voor de Tesla-deadline toegevoegd zodat de website operationele Homey-status, resterende energie, requested current en M7-context kan tonen.
- Homepage en Live energiestroom kunnen hierdoor onderscheid maken tussen wachten, opportunistisch laden en deadline catch-up.

## v2.8.19 — 16 augustus 2026

- Deadline-statusweergave op Live energiestroom gekoppeld aan de gepubliceerde Homey-runtime in plaats van alleen aan de opgeslagen website-opdracht.
- De website maakt hierdoor onderscheid tussen ingestelde deadline en operationele laadbeslissing.

## v2.8.18 — 16 augustus 2026

- Na succesvolle SOC-gebaseerde deadline-opslag verdwijnt de overgangsmelding **Deadline-instelling verouderd** direct.
- Na refresh wordt de waarschuwing alleen nog getoond wanneer het command-bestand daadwerkelijk nog het oude kWh-formaat gebruikt.

## v2.8.17 — 16 augustus 2026

- Oude kWh-gebaseerde Tesla-deadlines krijgen één duidelijke migratiemelding in plaats van meerdere onduidelijke statusvakken.
- De melding vraagt éénmalig om huidige SOC en doel-SOC opnieuw in te voeren; daarna wordt de normale operationele status weergegeven.

## v2.8.16 — 16 augustus 2026

- Tesla-deadlinebediening gewijzigd van een handmatig **kWh-doel** naar **Huidige SOC → Doel-SOC**.
- De gebruiker voert bij een actieve deadline nu datum/tijd, actuele SOC, gewenste SOC en maximale laadstroom in.
- De Cloudflare Worker valideert SOC en rekent het SOC-verschil intern om naar `goalKWh`, zodat `Tesla laden v2.1` en de bestaande catch-up-logica compatibel blijven.
- Eerste kalibratiefactor vastgelegd op circa **0,59 kWh per procentpunt**, gebaseerd op praktijkmeting 71% → 90%, 3×10 A, circa 7,1 kW en Tesla-ETA 1u35.
- Het command-JSON is uitgebreid met `currentSoc`, `targetSoc`, `socEnteredAt` en `calibrationKWhPerPercent`; `goalKWh` blijft uitsluitend intern/technisch aanwezig.
- Homepage toont bij een nieuwe SOC-gebaseerde deadline voortaan de percentages in plaats van het afgeleide kWh-doel.
- Functionele documentatie van Live energiestroom en de beveiligde write-route is tegelijk bijgewerkt.

## v2.8.11 — 16 augustus 2026

- Tesla deadline-interface gekoppeld aan een beveiligde write-route via Cloudflare Worker.
- De publieke website bevat geen Homey- of GitHub-token; bij opslaan wordt een persoonlijke control-PIN gevraagd.
- De Worker valideert deadline, kWh-doel en maximale laadstroom en schrijft uitsluitend `docs/data/tesla-deadline-command.json`.
- Nieuwe Homey-flow **`Tesla laden v2.1`** leest dit command-JSON iedere 2 minuten, verwerkt alleen een nieuwe `requestId` en zet daarna de bestaande EV Deadline Logic-variabelen.
- Fouten bij het ophalen of valideren van een command laten de bestaande Homey-instelling ongemoeid.
- De bestaande automatische Tesla-writers `Tesla laden`, `Tesla laden v2.0` en de vaste `Lader uit`-flow worden bij omschakeling uitgeschakeld zodat v2.1 de enige automatische Easee-writer blijft.
- `docs/data/tesla-control-config.json` bevat de publieke Worker-URL; zolang die nog leeg is blijft de knop op de website veilig uitgeschakeld.
- Nieuwe systeempagina **Tesla deadline write-route** documenteert de beveiligings- en activatiestappen.

## v2.8.10 — 16 augustus 2026

- Op **Live energiestroom** is in het Tesla/Easee-deel een compacte **Tesla deadline-interface** toegevoegd.
- De keuze **Geen deadline / Deadline actief** staat bovenaan; bij **Geen deadline** worden datum/tijd, kWh-doel, maximale laadstroom en deadline-resultaten verborgen.
- Bij **Deadline actief** verschijnen de SOC-loze instellingen **Gereed uiterlijk**, **Minimaal laden (kWh)** en **Max. laadstroom (A)**.
- De interface is voorbereid op publicatie van `EV Deadline status`, resterende kWh en `EV Latest start` vanuit Homey; er wordt bewust geen SOC-percentage verzonnen.
- De knop **Deadline opslaan** is voorlopig zichtbaar maar uitgeschakeld zolang de publieke GitHub Pages-site geen veilige write-route naar Homey heeft. Hierdoor kan de website niet ten onrechte suggereren dat een invoer al naar Homey is geschreven.
- Desktop en mobiel hebben afzonderlijk passende layout: horizontaal compact op desktop, onder elkaar op mobiel.
- Functionele documentatie op **Live energiestroom** is tegelijk bijgewerkt.

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
