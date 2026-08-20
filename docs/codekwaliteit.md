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
- gegenereerde bundle én Pages-artifact aantoonbaar synchroon met de bron;
- veilige rollback mogelijk.

> Deze software-engineeringbaseline verandert geen Homey-Controlstatus. Fysieke actuatorroutes blijven onder de afzonderlijke Shadow-, writer- en cut-overregels van Energy Core v2 vallen.
