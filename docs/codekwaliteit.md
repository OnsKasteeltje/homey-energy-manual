# Codekwaliteit & repository-governance

Deze pagina beschrijft de actuele software-engineeringbaseline van de Homey Energy Manual / Energy Core v2-repository. De regels hieronder gelden naast de functionele architectuurregels in **Architectuur** en veranderen niets aan de fysieke Homey-Control-policy.

## Actuele kwaliteitsbaseline — 21 augustus 2026

De repository is stapsgewijs gehard op onderhoudbaarheid, testbaarheid, reproduceerbaarheid en fail-safe gedrag.

### Frontendarchitectuur

De frontend gebruikt een centrale stateketen:

```text
energy-state-v2.json
        ↓
Energy Core adapter
        ↓
EnergyStore
        ↓
LiveEnergyModel
        ↓
renderer / UI-modules
```

Belangrijke regels:

- `EnergyStore` is de canonieke browserstate; `window.EnergyCoreV2` bestaat alleen als backwards-compatible facade.
- Business-/energielogica hoort in het model of de normalisatielaag, niet als DOM-correctie achteraf.
- De Live Energy-renderer tekent het voorberekende view-model en hoort geen nieuwe energiebalansregels te introduceren.
- De actieve vermogensdrempel is **>20 W**; 20 W of lager wordt niet als actieve energiestroom weergegeven.
- Onbekend apparaatvermogen wordt niet geschat.
- `Overig` is een residuele meetcategorie na aftrek van bekende/gemeten belastingen en wordt nooit negatief weergegeven.
- P1/netmeting blijft leidend voor de elektrische woningbalans.
- Quooker is een first-class Live View-load: switchstatus bepaalt OFF/ON_IDLE; P1/L3 bepaalt alleen HEATING en het gemeten vermogen.

### Frontend lifecycle, ownership en interactieve componenten

Voor interactieve frontendcomponenten gelden aanvullend de volgende harde coding standards:

- **Eén feature heeft één duidelijke eigenaar.** Een interactieve UI-feature heeft in beginsel één renderer, één controller en één actieve stylesheet. Aanvullende migration-, status-, postsave- of DOM-patchmodules mogen alleen actief zijn wanneer daar een aantoonbare tijdelijke noodzaak voor bestaat.
- **Vervangen implementaties worden ook uit de actieve bundle verwijderd.** Het toevoegen van een nieuwe route is niet voldoende; obsolete selectors, listeners, runtime-modules en CSS mogen niet actief mee blijven draaien.
- **DOM-contracten zijn expliciet.** Renderer, controller, CSS en tests koppelen via één canonieke selector/interface. Versiegenummerde CSS-classes mogen niet de enige functionele koppeling tussen componenten vormen.
- **Renderer en controller hebben een expliciet lifecycle-contract.** Als een renderer met `innerHTML`, node replacement of vergelijkbare techniek interactieve DOM vervangt, moet hij na iedere succesvolle render een deterministisch `...rendered`/`...ready`-event publiceren. De bijbehorende controller hydrateert op dat event opnieuw. Een toevallige timer, tab-focus of browser-visibility-event mag nooit nodig zijn om een component correct te initialiseren.
- **Lokale gebruikersinvoer mag niet door live refresh worden vernietigd.** Zolang een gebruiker een formulier bewerkt, wordt de lokale draft-state behouden over render- en datarefreshcycli. Alleen een expliciete save/cancel of aantoonbaar nieuwe authoritatieve configuratie mag deze toestand vervangen.
- **Editable config en runtime telemetry hebben een vastgelegde bronprioriteit.** Voor configuratieformulieren is de laatst opgeslagen configuratie/command de primaire source of truth; asynchrone runtime-snapshots mogen een formulier niet tijdelijk terugrollen wanneer zij aantoonbaar achterlopen.
- **Geen MutationObserver- of timerketens als structurele componentbinding.** Zulke mechanismen zijn alleen toegestaan als expliciet gedocumenteerde compatibility fallback. De normale route moet event-driven en deterministisch zijn.
- **Debug eerst de laag, wijzig daarna pas code.** Bij frontendproblemen wordt eerst vastgesteld of het defect in data, rendering, controller/binding, bundling, deployment/cache of responsive layout zit. In beginsel wordt alleen de aangetoonde foutlaag gewijzigd.
- **Responsive layout volgt componentbreedte, niet alleen viewportbreedte.** Een component in een smalle grid-card kan ook op een brede desktop weinig ruimte hebben. Formulieren worden daarom ontworpen met intrinsiek robuuste grids/flex-layouts en `min-width: 0`; viewport media queries zijn aanvullend, niet de enige bescherming tegen overflow.
- **Een functionele fix is niet klaar als de UI visueel stuk is.** Leesbaarheid, overflow, label-wrapping, bediening en relevante desktop/mobile toestanden maken onderdeel uit van dezelfde wijziging en dezelfde DoD.

### Frontend Definition of Done

Iedere frontendwijziging wordt vóór afronding expliciet tegen deze DoD geverifieerd:

1. de gewenste functie werkt end-to-end in de relevante gebruikersflow;
2. er is één aantoonbare actieve implementatieroute;
3. obsolete JS/CSS/selectors worden niet actief meegebundeld;
4. renderer/controller lifecycle is deterministisch en niet afhankelijk van tabwissel, focus of toevallige timing;
5. lokale edit-state blijft intact over live refresh/rendercycli waar dat functioneel vereist is;
6. source-of-truth en bronprioriteit zijn expliciet en consistent;
7. selectors, componentcontracten en versies zijn consistent;
8. relevante automatische regressietests en CI-invarianten zijn groen;
9. de gebouwde en gedeployde frontend bevat aantoonbaar de geteste implementatie;
10. visuele leesbaarheid en responsiveness zijn gecontroleerd op de relevante componentbreedtes;
11. relevante documentatie/coding standards zijn bijgewerkt wanneer de wijziging een nieuw structureel patroon introduceert.

Een frontendwijziging wordt niet als **DoD VERIFIED** gerapporteerd zolang één van deze toepasselijke controles nog open staat.

### Frontendbundling

De browser laadt één versieerbare JavaScript-bundle en één CSS-bundle. De afzonderlijke bronmodules blijven in Git leesbaar en rollbackbaar.

`frontend-version.txt` is de enige handmatig beheerde frontend-bundleversie. De bundler en CI leiden de gegenereerde assetnaam daaruit af.

Historische bronversies mogen voor rollback in Git blijven, maar alleen de expliciet opgenomen bronlijst in `scripts/build_frontend_bundles.py` vormt de actieve frontend.

## Energy State-contract

De actuele websiteadapter en repositoryvalidator accepteren expliciet:

```text
schema_version = 2.11
```

Voor `loads.quooker` zijn minimaal `active`, `switch_on`, `power_w`, `status`, `source` en `fresh` verplicht. De actuele bron is:

```text
source = HOMEY_SWITCH_PLUS_P1_L3
```

Een snapshot wordt alleen als geldig behandeld wanneer de verplichte secties aanwezig zijn en:

```text
state_revision = decision_revision = shadow_revision
```

Een onbekende toekomstige `2.x`-versie wordt niet automatisch als compatibel beschouwd. Een schemawijziging in Core moet daarom **atomair** worden doorgevoerd in publisher, adapter, fixtures/tests, repositoryvalidator en documentatie.

Bij een fetch-, HTTP-, parsing- of contractfout blijft de laatste geldige snapshot beschikbaar als fallback.

## Automatische tests

De repository bevat Python- en JavaScript-tests die vóór een Pages-deployment worden uitgevoerd. De kernset controleert onder meer:

- 20 W standby-/actiefgrens;
- netimport versus netexport;
- batterij laden versus ontladen;
- `Overig` als niet-negatief residu;
- Quatt + CV hybride classificatie;
- Quooker als zevende Live View-consument;
- Quooker `ON_IDLE` zonder actieve energiestroom;
- Quooker `HEATING` met gemeten vermogen en correcte aftrek uit `Overig`;
- `EnergyStore` state/error-publicatie;
- repository- en Energy State-contractvalidatie.

## CI/CD quality gates

De Pages-pipeline voert vóór deployment uit:

```text
locked dependencies installeren
        ↓
Python + JavaScript tests
        ↓
repository-/Energy State-validatie
        ↓
Ruff + JavaScript syntaxcontrole
        ↓
frontendbundling
        ↓
GENERATED BUNDLE INVARIANT
        ↓
mkdocs build --strict
        ↓
DEPLOYED ARTIFACT INVARIANT
        ↓
Pages artifact/deploy
```

### Bundle- en artifact-invariant

Sinds 21 augustus 2026 geldt een harde extra gate. CI bewijst na bundling dat:

1. `frontend-version.txt` overeenkomt met de actieve versiegebonden bundle;
2. `mkdocs.yml` naar exact die bundle verwijst;
3. alle geconfigureerde frontendbronnen daadwerkelijk in de gegenereerde bundle aanwezig zijn;
4. kritieke Live View-contractmarkers, waaronder Quooker/`switch_on`/`HEATING`, in de bundle zitten;
5. na `mkdocs build` het uiteindelijke `site/`-artifact dezelfde versie en markers bevat.

Hierdoor kan de toestand **“broncode op main is nieuw, productie serveert stilzwijgend een oude bundle”** niet meer als succesvolle build passeren.

### Incident 21 augustus 2026

Bij de introductie van Quooker in Live View bleef productie op een oude zes-blokkenbundle staan. De directe oorzaak was dat `validate_repository.py` nog uitsluitend Energy State-schema **2.10** accepteerde terwijl Core al schema **2.11** publiceerde. Iedere Pages-build faalde daardoor vóór bundling/deploy.

De correctie bestaat uit:

- validator bijgewerkt naar schema 2.11;
- Quooker-contract expliciet gevalideerd;
- regressietests voor de zevende Live View-load;
- bundle- en deployed-artifact-invarianten toegevoegd;
- documentatie van schemawijzigingen aangescherpt.

De productie-Live View publiceerde daarna opnieuw actueel en toont Quooker als afzonderlijke load.

## Repository-governance

`main` is nog niet volledig beschermd. Gewenste doeltoestand blijft:

```text
feature/change → Pull Request → required checks groen → merge main → Pages deployment
```

Prioriteiten:

1. branch protection/ruleset voor `main`;
2. kwaliteitsworkflow ook op `pull_request`;
3. relevante checks required maken;
4. directe pushes naar `main` waar praktisch mogelijk beperken.

## Reviewregels voor nieuwe code

Bij iedere relevante wijziging wordt minimaal gecontroleerd:

- businesslogica buiten DOM/rendering;
- centrale state hergebruiken;
- onbekende meetwaarden niet als `0` schatten;
- schema- en revision-invarianten intact;
- schemawijziging atomair door alle consumers/validators/tests;
- regressietest voor kritieke nieuwe logica;
- geen nieuwe onnodige Homey-polling of dubbele writer;
- voor interactieve frontend: expliciet lifecycle-/ownershipcontract en behoud van lokale edit-state;
- geen afhankelijkheid van focus/tabwissel/timing om een component correct te initialiseren;
- responsive layout controleren op daadwerkelijke componentbreedte;
- frontend-DoD expliciet verifiëren vóór afronding;
- gegenereerde bundle én Pages-artifact aantoonbaar synchroon met de bron;
- veilige rollback mogelijk.

> Deze software-engineeringbaseline verandert geen Homey-Controlstatus. Fysieke actuatorroutes blijven onder de afzonderlijke Shadow-, writer- en cut-overregels van Energy Core v2 vallen.
