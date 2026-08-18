# Wijzigingshistorie

De versiehistorie van deze site volgt vanaf 17 augustus 2026 de **architectuurversie** en niet langer iedere afzonderlijke flow-, script- of UI-versie.

De hoofdindeling is daarom:

- **Architectuur v1** — oorspronkelijke, meer gedistribueerde Homey-opzet met meerdere zelfstandige flows, readers, writers en publicatiepaden.
- **Architectuur v2** — centrale Energy Core met één gedeelde state-sample per cyclus, atomische beslis-/shadowketen en expliciete scheiding tussen observatie, beslissing, publicatie en fysieke Control.
- Nieuwe wijzigingen binnen de huidige architectuur krijgen voortaan uitsluitend een **v2-subversie**.

De oude fijnmazige versiereeks is niet meer onderdeel van deze pagina. De technische Git-historie blijft beschikbaar voor rollback en detailonderzoek.

## v2.0.10 — 18 augustus 2026

### Quatt first-class in Energy Core en Live energiestroom

- De uiteindelijke actieve kern is `EM v2 | 00 Core Tick | v0.9.7`; de tussenversies v0.9.5 en v0.9.6 zijn gedeactiveerd.
- Quatt CIC wordt binnen **dezelfde bestaande `getDevices()` snapshot** gelezen. Er is geen extra periodieke device-read of aparte Quatt-poll toegevoegd.
- De publieke state gebruikt schema `2.5` met publisher `EM2_CORE_PUBLISH_V0.9.7`.
- Quatt is first-class `COMFORT_BASELOAD` met `control_mode = OBSERVE_ONLY` en `controllable = false`.
- Het publieke `quatt`-blok bevat elektrisch vermogen, thermisch vermogen, COP/werkingsmodus, thermostaat-warmtevraag, CV-verzoek en branderstatus waar beschikbaar.
- `cv_flame = null` blijft expliciet **onbekend**; een CV-verzoek wordt niet als bewijs van een brandende ketel behandeld.
- Het nieuwe `energy_budget` houdt een Quatt-rampreserve vrij voor flexibele lasten zonder het actuele Quatt-verbruik dubbel uit de P1-balans af te trekken.
- De Live energiestroom gebruikt `quatt.power_w` als de elektrische tak **Ruimteverwarming** en trekt dit vermogen af van `Overig`.
- Tesla, Boiler, Ruimteverwarming en Overig blijven vier onafhankelijke parallelle energietakken vanuit Huis.
- Thermisch vermogen en CV/gasstatus worden alleen als context/status getoond en niet in de elektrische energiebalans opgeteld.
- De website-renderer `live-energy-v2.8.39.js` is gekoppeld aan het actuele `quatt`-blok van schema 2.5.
- Quatt krijgt geen fysieke Homey-aansturing; de wijziging blijft observe-only voor ruimteverwarming.
- De eenmalige v0.9.6- en v0.9.7-cut-overflows zijn na succesvolle overgang weer uitgeschakeld.

## v2.0.9 — 18 augustus 2026

### Live energiestroom: hybride ruimteverwarming geïntegreerd

- De live energiestroom toont voortaan **vier onafhankelijke parallelle verbruikstakken** vanuit de woning: Tesla, Boiler, Ruimteverwarming en Overig.
- Er zijn geen onderlinge pijlen tussen deze vier verbruikscategorieën; `Overig` is een vierde categorie en geen downstream-stroom van andere apparaten.
- De nieuwe tegel **Ruimteverwarming** representeert de hybride Quatt-opstelling als één functioneel systeem met Quatt als elektrische bron en CV-ketel als ondersteunende status.
- Zolang Quatt/CV-data niet in de Energy Core v2-snapshot aanwezig is, toont de site bewust `status onbekend` en geen verzonnen vermogen.
- Zolang Quatt-vermogen ontbreekt blijft `Overig = woningverbruik - TeslaW - boilerW`; pas bij betrouwbare gepubliceerde Quatt-data wordt ook `QuattW` afgetrokken.
- De Energiemanager-balk toont Tesla, Boiler en Ruimteverwarming als functionele onderdelen; Overig blijft een meet-/restcategorie.
- Deze wijziging is **uitsluitend websitepresentatie**: geen nieuwe Homey-flow, device-read, pollingcyclus, publisher-call of fysieke Control toegevoegd.

## v2.0.8 — 18 augustus 2026

### Warmwatervraag op ieder moment van de dag onderdeel van HYBRID-acceptatie

- De warmwaterregeling mag niet aannemen dat vraag alleen in de ochtend plaatsvindt.
- Warmwatergebruik wordt behandeld als gebeurtenis/context, niet automatisch als nieuwe verwarmingsopdracht.
- Vóór het bereiken van `OP_TEMPERATUUR` moet na relevante warmwatervraag opnieuw opportunity versus resterende tijd/catch-up worden beoordeeld.
- Na `goalReachedToday=true` opent latere warmwatervraag dezelfde dag geen nieuwe verplichte opwarmcyclus zolang `sameDayReheat=false` geldt.
- Voor promotie van Warm Water Control naar HYBRID moeten expliciet ochtend-, middag/namiddag-, vlak-voor-catch-up-, na-dagdoel- en meervoudige-vraagscenario's logisch en fail-safe in SHADOW zijn beoordeeld.
- Deze eis is vastgelegd in de Energy Core v2-documentatie en geldt als harde acceptatievoorwaarde vóór fysieke WW-writes.

## v2.0.7 — 18 augustus 2026

### Core Tick v0.9.5 en confirmed-heating fallback

- De actieve Energy Core is nu `EM v2 | 00 Core Tick | v0.9.5`.
- De live publisher identificeert zich als `EM2_CORE_PUBLISH_V0.9.5` met schema 2.3.
- State, Decision en Shadow blijven revision-consistent; actuele publicaties tonen dezelfde revision voor de hele keten.
- De 240-minuten warmwaterfallback telt niet langer relais-aan-tijd maar uitsluitend **bevestigde verwarmingsminuten**: boiler AAN én gemeten boilervermogen >1500 W.
- `boilerOnMinToday` blijft alleen diagnostiek; de fallback gebruikt `heatingMinToday` en publiceert `fallbackAccounting = CONFIRMED_HEATING_MINUTES`.
- Bij migratie binnen de lopende dag kan de eerder verstreken verwarmingsduur niet betrouwbaar worden gereconstrueerd; daarom wordt de accountingkwaliteit expliciet als partieel vanaf de v0.9.5-start gemarkeerd.
- Het primaire dagdoel blijft `OP_TEMPERATUUR` eenmaal per lokale kalenderdag en blijft daarna gelatcht (`sameDayReheat=false`).
- Warm Water Control blijft **PURE SHADOW**: `readOnly=true`, `deviceWrites=false`, `physicalWritePerformed=false`.
- De algemene pagina **Energie Manager PV** is bijgewerkt van de oude v1 Collector/Allocator-architectuur naar de actuele centrale Energy Core v2-opzet.

## v2.0.6 — 18 augustus 2026

### Mobiele energiehistorie leesbaarder

- Het week-/maand-/jaaroverzicht op smalle schermen krijgt extra ruimte links van de grafiek zodat Y-aswaarden niet meer worden afgesneden.
- De mobiele aslabels zijn compacter gemaakt zonder de desktopweergave te wijzigen.
- De legenda wordt op mobiel in twee kolommen gezet, zodat Netimport, Netexport, Boiler en Tesla binnen het kaartkader blijven.
- De wijziging is uitsluitend presentatielogica; Energy Core, Homey-calls, meetdata en historische berekeningen zijn ongewijzigd.

## v2.0.5 — 18 augustus 2026

### Warmwater opportunity planner

- Energy Core draait op dat moment op `EM v2 | 00 Core Tick | v0.9.4`.
- Nieuwe lichte contextlaag `EM v2 | 30 Context | Price + PV v0.1` vernieuwt iedere 15 minuten prijs- en PV-forecastsignalen zonder device-scan.
- Context krijgt een freshness-tijdstip; Core gebruikt prijs/forecast alleen wanneer die maximaal 35 minuten oud zijn.
- Ochtendherverwarming vóór 09:30 wordt bewust uitgesteld wanneer de deadline dit toelaat. Als het boilerrelais nog aan staat, kan Shadow `BOILER_OFF / SHOULD` adviseren om spontane herverwarming na warmwatergebruik te voorkomen.
- WW kan vanaf 09:30 starten op sterke actuele export, negatieve prijs, relatief goedkoop prijsvenster of een top-4 PV-forecastuur met voldoende actuele export.
- Prijsstarts zijn nu expliciet afgestemd op hun minimumlooptijd: een prijs-opportunity mag alleen starten wanneer nog minimaal **30 minuten** in het huidige tariefuur resteren.
- Een prijsstart krijgt **30 minuten run-lock**; een PV/exportstart **15 minuten**.
- `CATCHUP` krijgt geen opportunity-run-lock: zodra de deadline/comfortreserve ingrijpt, heeft het halen van het dagdoel prioriteit boven economische optimalisatie.
- Na afloop van de relevante run-lock mag de planner opnieuw optimaliseren en bij ongunstige import/prijs `BOILER_OFF / SHOULD` adviseren.
- Het dagdoel blijft `OP_TEMPERATUUR` eenmaal per lokale kalenderdag; `goalReachedToday` blijft daarna gelatcht en `sameDayReheat=false`.
- De v0.9.4-validatie publiceerde schema 2.3 met gelijke State/Decision/Shadow-revisions en `physicalWritePerformed=false`.
- Fysieke WW-Control blijft uitgeschakeld: alle boileracties zijn nog PURE SHADOW.
- Bekend validatiepunt vóór fysieke WW-Control was op dat moment dat de 240-minutenfallback nog van relais-aan-tijd naar werkelijk/bevestigd verwarmen moest worden omgezet; dit is in v2.0.7/v0.9.5 opgelost.

## v2.0.4 — 17 augustus 2026

### Compacte Energy Core healthweergave

- Het grote inline blok `EM v2: LIVE · state · heartbeat · revision · SHADOW` is verwijderd van homepage, Live energiestroom en Energy Core v2.
- De compacte health-indicator in de header blijft behouden.
- Healthmonitoring zelf is niet verwijderd; alleen de redundante detailpresentatie is opgeschoond.
- Geen Homey-regellogica of fysieke Control gewijzigd.

## v2.0.3 — 17 augustus 2026

### Homepage Tesla single-source

- De Tesla-tegel op de homepage wordt nog maar door **één renderer** aangestuurd: de actuele Energy Core v2-browserstate.
- De oude `home-tesla-runtime` homepage-overlay is uit de siteconfiguratie verwijderd en kan de v2-tegel daardoor niet meer achteraf overschrijven.
- Oude kalibratie-/baseline-auditstatussen blijven beschikbaar op **Live energiestroom**, waar de aparte Tesla runtime/deadline-interface ze technisch hoort te tonen.
- Tesla deadline-, Equalizer- en laadmetingfunctionaliteit op Live energiestroom blijft ongewijzigd.
- Geen Homey-flow, laadregeling of fysieke Control gewijzigd; dit is uitsluitend een veilige scheiding van websiteverantwoordelijkheden.

## v2.0.2 — 17 augustus 2026

### Presentatie afgestemd op actuele v2-state

- Homepage gebruikt voor warm water `goalReachedToday` als leidende dagstatus.
- Een eenmaal bereikt warmwaterdagdoel blijft op de site zichtbaar als **Dagdoel bereikt**, ook wanneer later op de avond warm water wordt gebruikt.
- Tesla-homepagestatus gebruikt de actuele Core-v2-toestand als primaire bron.
- Oude Tesla-kalibratie-/baseline-auditmeldingen mogen de actuele v2-status niet meer als hoofdstatus overschrijven.
- Technische Tesla-intentie `HOLD` wordt op de homepage gebruikersvriendelijk weergegeven als **Geen actieve laadopdracht**.
- Geen fysieke Homey-Control gewijzigd; dit betreft presentatie bovenop de bestaande v2-state.

## v2.0.1 — 17 augustus 2026

### Warmwaterdagdoel gelatcht per kalenderdag

- Energy Core aangepast naar `Core Tick v0.9.2`.
- `OP_TEMPERATUUR` hoeft per lokale kalenderdag slechts één keer betrouwbaar te worden bereikt.
- Na bereiken van het dagdoel blijft `goalReachedToday=true` tot de dagwissel.
- Avondelijk warmwatergebruik opent het dagdoel niet opnieuw.
- `sameDayReheat=false`: geen verplichte heropwarming of nieuwe catch-up meer dezelfde dag.
- Fallback van 240 minuten blijft uitsluitend een vangnet wanneer het primaire dagdoel nog niet is bereikt.
- Control blijft volledig **SHADOW/read-only**; er zijn geen fysieke boilerwrites toegevoegd.

## v2.0 — 17 augustus 2026

### Architectuur v2 operationeel

De Energy Manager is geconsolideerd naar een centrale, Homey-zuinige architectuur.

Belangrijkste kenmerken:

- `EM v2 | 00 Core Tick` vormt de operationele kern.
- Per vijf minuten maximaal **één device-read en één Logic-read** voor de centrale regelketen.
- State → Decision → Shadow → Warm Water State → Warm Water Control → Publish worden vanuit dezelfde sample en revision berekend.
- Losse Collector-, Decision/Shadow-, Warm Water Observer-, Warm Water Actuator- en Publisher-paden zijn uit de operationele kern gehaald.
- Publicatie naar GitHub is gethrottled en veroorzaakt geen extra device-scan.
- De website leest uitsluitend gepubliceerde data en veroorzaakt geen Homey-calls.
- Warmwater-Control draait in **PURE SHADOW** zonder fysieke device-writes.
- De succesvolle cut-over valideerde revision-consistentie over State, Decision, Shadow, WW State en WW Control.
- Oude flowversies zijn waar nodig tijdelijk gedeactiveerd gehouden voor rollback en daarna stapsgewijs opgeschoond.

Deze versie vormt de basis voor verdere uitbreiding met Tesla-Control en later Victron/batterij-integratie.

## v1 — tot 17 augustus 2026

### Architectuur v1

De eerste generatie Energy Manager groeide iteratief uit meerdere losse Homey-flows en aanvullende publicatie-/websitecomponenten.

Kenmerkend voor v1 waren:

- meerdere zelfstandige periodieke flows;
- verschillende readers en publicatiepaden naast elkaar;
- aparte warmwater-, Tesla-, opportunity-, fase- en statuslogica;
- verschillende tussenversies en tijdelijke cut-overflows;
- hogere Homey-load door herhaalde polling en overlappende verantwoordelijkheden;
- een werkende maar steeds moeilijker beheersbare combinatie van automatisering, shadowvalidatie en websitepublicatie.

De ervaringen met v1 hebben rechtstreeks geleid tot de ontwerpprincipes van v2: **single-reader, gedeelde state, atomische revisions, minimale Homey-load en één duidelijke Control-route per actuator**.

---

> **Versiebeleid vanaf v2:** alleen architectuurrelevante of gebruikerszichtbare wijzigingen krijgen een vermelding op deze pagina. Interne flow-, script- en testversies worden niet meer als aparte siteversie bijgehouden.
