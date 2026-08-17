# Wijzigingshistorie

De versiehistorie van deze site volgt vanaf 17 augustus 2026 de **architectuurversie** en niet langer iedere afzonderlijke flow-, script- of UI-versie.

De hoofdindeling is daarom:

- **Architectuur v1** — oorspronkelijke, meer gedistribueerde Homey-opzet met meerdere zelfstandige flows, readers, writers en publicatiepaden.
- **Architectuur v2** — centrale Energy Core met één gedeelde state-sample per cyclus, atomische beslis-/shadowketen en expliciete scheiding tussen observatie, beslissing, publicatie en fysieke Control.
- Nieuwe wijzigingen binnen de huidige architectuur krijgen voortaan uitsluitend een **v2-subversie**.

De oude fijnmazige versiereeks is niet meer onderdeel van deze pagina. De technische Git-historie blijft uiteraard beschikbaar voor rollback en detailonderzoek.

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
