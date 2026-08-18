# Wijzigingshistorie

De versiehistorie van deze site volgt vanaf 17 augustus 2026 de **architectuurversie** en niet langer iedere afzonderlijke flow-, script- of UI-versie.

De hoofdindeling is daarom:

- **Architectuur v1** — oorspronkelijke, meer gedistribueerde Homey-opzet met meerdere zelfstandige flows, readers, writers en publicatiepaden.
- **Architectuur v2** — centrale Energy Core met één gedeelde state-sample per cyclus, atomische beslis-/shadowketen en expliciete scheiding tussen observatie, beslissing, publicatie en fysieke Control.
- Nieuwe wijzigingen binnen de huidige architectuur krijgen voortaan uitsluitend een **v2-subversie**.

De oude fijnmazige versiereeks is niet meer onderdeel van deze pagina. De technische Git-historie blijft beschikbaar voor rollback en detailonderzoek.

## v2.0.5 — 18 augustus 2026

### Warmwater opportunity planner

- Energy Core verhoogd naar `EM v2 | 00 Core Tick | v0.9.3`.
- Nieuwe lichte contextlaag `EM v2 | 30 Context | Price + PV v0.1` vernieuwt iedere 15 minuten prijs- en PV-forecastsignalen zonder device-scan.
- Context krijgt een freshness-tijdstip; Core gebruikt prijs/forecast alleen wanneer die maximaal 35 minuten oud zijn.
- Ochtendherverwarming vóór 09:30 wordt niet meer als gewenst gedrag beschouwd: Shadow adviseert het boilerrelais uit te zetten en te wachten op een gunstiger energiemoment.
- WW kan vanaf 09:30 als SHOULD-opportunity starten op sterke actuele export, negatieve prijs, relatief goedkoop prijsvenster of een top-4 PV-forecastuur met voldoende actuele export.
- Deadline/catch-up vóór 19:00 blijft boven opportunity-optimalisatie staan.
- Lopende runs krijgen een minimale looptijd van 30 minuten voordat een ongunstige prijs/import reden kan zijn om te stoppen.
- De ochtendobservatie bevestigde dat geen actieve legacy-boilerstartflow de boiler had gestart; het relais stond nog aan en de interne thermostaat hervatte na warmwatergebruik vanzelf het element.
- Eerste v0.9.3-publicatie gaf voor deze ochtendtoestand `BOILER_OFF / SHOULD / WAIT_MORNING`.
- Fysieke Control blijft uitgeschakeld. Er zijn geen v2-device-writes toegevoegd.
- Bekend validatiepunt vóór fysieke WW-Control: de 240-minuten fallback moet nog van relais-aan-tijd naar werkelijk/bevestigd verwarmen worden omgezet.

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
- Geen Homey-flow, laadregeling of fysieke Control is gewijzigd; dit is uitsluitend een veilige scheiding van websiteverantwoordelijkheden.

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
