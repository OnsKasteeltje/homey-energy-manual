# Codekwaliteit & repository-governance

Deze pagina beschrijft de actuele software-engineeringbaseline van de Homey Energy Manual / Energy Core v2-repository. De regels hieronder gelden naast de functionele architectuurregels in **Architectuur** en veranderen niets aan de fysieke Homey-Control-policy.

## Actuele kwaliteitsbaseline — 20 augustus 2026

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
- Onbekend apparaatvermogen wordt niet geschat. Een apparaat kan statusmatig actief zijn terwijl het afzonderlijke vermogen onbekend blijft.
- `Overig` is een residuele meetcategorie na aftrek van bekende/gemeten belastingen en wordt nooit negatief weergegeven.
- P1/netmeting blijft leidend voor de elektrische woningbalans.

### Frontendbundling

De browser laadt één versieerbare JavaScript-bundle en één CSS-bundle. De afzonderlijke bronmodules blijven in Git leesbaar en rollbackbaar.

`frontend-version.txt` is de enige handmatig beheerde frontend-bundleversie. De bundler en CI leiden de gegenereerde assetnaam daaruit af.

Historische bronversies mogen voor rollback in Git blijven, maar alleen de expliciet opgenomen bronlijst in `scripts/build_frontend_bundles.py` vormt de actieve frontend.

## Energy State-contract

De actuele websiteadapter en repositoryvalidator accepteren expliciet:

```text
schema_version = 2.10
```

Een snapshot wordt alleen als geldig behandeld wanneer de verplichte secties aanwezig zijn en:

```text
state_revision = decision_revision = shadow_revision
```

Een onbekende toekomstige `2.x`-versie wordt dus niet automatisch als compatibel beschouwd.

Bij een fetch-, HTTP-, parsing- of contractfout blijft de laatste geldige snapshot beschikbaar als fallback. De frontend publiceert afzonderlijke state-, error- en stale-signalen zodat consumers geen fouttoestand uit impliciete globale state hoeven af te leiden.

## Status-sync

De lokale statusbuilder behandelt ontbrekende of ongeldige Homey-bronnen fail-safe:

- `sync_ok` wordt uit de werkelijke bronstatus berekend en staat niet standaard op `true`;
- ontbrekende brondata leidt tot `unknown` waar geen betrouwbare conclusie mogelijk is;
- booleans worden expliciet genormaliseerd en niet via een generieke truthy/falsy-conversie geïnterpreteerd;
- website/statusverwerking voegt geen extra Homey-devicepolling toe.

## Automatische tests

De repository bevat Python- en JavaScript-tests die vóór een Pages-deployment worden uitgevoerd.

De huidige kernset controleert onder meer:

- 20 W standby-/actiefgrens;
- netimport versus netexport;
- batterij laden versus ontladen;
- prioriteit van gemeten/afgeleide huislastbronnen;
- `Overig` als niet-negatief residu;
- onbekend versus gemeten wasmachine-/drogervermogen;
- Quatt + CV hybride classificatie;
- `EnergyStore` state/error-publicatie en unsubscribe;
- repository- en Energy State-contractvalidatie.

### Nog gewenste testuitbreiding

De volgende uitbreiding heeft prioriteit:

1. adaptertests voor schemaacceptatie en schema-afwijzing;
2. revision-mismatch;
3. stale state en stale heartbeat;
4. fetch/HTTP failure met behoud van laatste geldige snapshot;
5. compatibility facade;
6. minimaal één DOM-level smoke/integratietest van State → Store → Model → Renderer.

## CI/CD quality gates

De Pages-pipeline voert vóór deployment uit:

```text
locked dependencies installeren
        ↓
Python tests
        ↓
JavaScript tests
        ↓
repository-/Energy State-validatie
        ↓
Ruff correctness checks
        ↓
JavaScript syntaxcontrole
        ↓
frontendbundling
        ↓
bundle syntaxcontrole
        ↓
mkdocs build --strict
        ↓
Pages artifact/deploy
```

Wijzigingen uitsluitend aan runtime-energiedata gebruiken een aparte lichte workflow. Daarmee worden `homey-status.json`, `shadow-status.json` en `energy-state-v2.json` gevalideerd zonder onnodige volledige Pages-build.

Externe GitHub Actions zijn op immutable commit-SHA's gepind.

## Dependencies en reproduceerbaarheid

De build gebruikt expliciet vastgelegde Python- en Node-versies. Directe én transitieve Python-dependencies zijn exact vastgelegd in `requirements.lock`; CI voert na installatie `pip check` uit.

Bekende resterende hardening:

- dependency-hashes toevoegen en installeren met `pip --require-hashes`;
- ook de gebruikte `pip`-versie deterministisch maken in plaats van ongepinnd te upgraden.

`pymdownx.snippets` is bewust geblokkeerd zolang de gebruikte dependencylijn daarvoor niet als veilig is vrijgegeven. De repositoryvalidator faalt wanneer deze extensie toch in `mkdocs.yml` wordt geactiveerd.

## Repository-governance

### Actuele tekortkoming

`main` is op 20 augustus 2026 nog **niet beschermd**. De CI-controles zijn daardoor wel sterke post-push gates, maar nog geen verplichte pre-merge poort.

### Gewenste doeltoestand

```text
feature/change
      ↓
Pull Request
      ↓
verplichte tests + validator + build
      ↓
alle required checks groen
      ↓
merge naar main
      ↓
Pages deployment
```

Daarvoor zijn nog nodig:

1. branch protection/ruleset voor `main`;
2. kwaliteitsworkflow ook op `pull_request` laten draaien;
3. relevante checks als required status checks instellen;
4. directe pushes naar `main` waar praktisch mogelijk beperken.

Dit is de hoogste resterende repository-governanceprioriteit.

## Build hygiene

De frontendversie heeft één source of truth, maar de huidige bundler synchroniseert de placeholder in de tracked `mkdocs.yml` tijdens de build. Functioneel werkt dit, maar een lokale build kan daardoor de working tree wijzigen.

Gewenste vervolgstap is een tijdelijke gegenereerde MkDocs-config te gebruiken, bijvoorbeeld:

```text
mkdocs.yml
   ↓
build/mkdocs.generated.yml
   ↓
mkdocs build -f build/mkdocs.generated.yml
```

De bronconfig blijft dan immutable tijdens een build.

## Reviewregels voor nieuwe code

Bij iedere relevante codewijziging wordt naast de energiearchitectuur minimaal gecontroleerd:

- is businesslogica testbaar en buiten DOM/rendering gehouden?
- wordt centrale state hergebruikt in plaats van nieuwe globale state toegevoegd?
- worden onbekende meetwaarden niet als `0` of als schatting behandeld?
- blijven schema- en revision-invarianten intact?
- bestaat voor nieuwe kritieke logica minimaal één regressietest?
- voegt de wijziging geen nieuwe Homey-polling of dubbele publisher/writer toe?
- blijft de build reproduceerbaar en CI fail-fast?
- kan de wijziging veilig worden teruggedraaid?

## Resterende verbeterprioriteiten

1. branch protection + PR quality gate;
2. adapter- en frontend-integratietests;
3. dependency-hashes + gepinde pip;
4. build zonder mutatie van tracked `mkdocs.yml`;
5. resterende Live Energy-postprocessors geleidelijk naar model- of expliciete UI-modules verplaatsen;
6. Energy State-contract later formaliseren als JSON Schema;
7. optioneel commit signing invoeren.

> Deze software-engineeringbaseline verandert geen Homey-Controlstatus. Fysieke actuatorroutes blijven onder de afzonderlijke Shadow-, writer- en cut-overregels van Energy Core v2 vallen.
