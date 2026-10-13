# Homey Energy Manual — private EMS

Bronrepository voor het Home Energy Management System (EMS). **GitHub is publiek voor broncode en architectuur; de productie-EMS en alle actuele meet- en planningsdata blijven op de private Raspberry Pi.** Deze repository is geen live dashboard of telemetriearchief.

## Actuele productiearchitectuur

| Laag | Verantwoordelijkheid | Bron |
| --- | --- | --- |
| Homey | Canonieke apparaatobservaties en bewaakte fysieke uitvoering (EV, WW, Quooker); geen tweede planner | `apps/homey/`, `src/homey/` |
| Raspberry Pi | Planning, deadline lifecycle, forecast, history, shadow-evaluatie, API's | `services/pi/`, `src/pi/ems-runtime/` |
| Private frontend | Live, Invoer, Historie, Verwarming, Planner en PV Flex via de Pi en Tailscale | `frontend/`, `deploy/caddy/` |
| Heating / Honeywell | Honeywell blijft comfortautoriteit; EMS-preheat, grant en control-gate zijn **SHADOW / no physical writes** | `services/pi/planner/heating/` |
| GitHub Pages | Alleen een neutrale landingspagina, **geen** runtime-JSON of EMS-bediening | `.github/workflows/pages.yml` |

Tesla-deadlines gaan **lokaal**: private Invoer V2 → Caddy / Tailscale → Pi `POST /commands/tesla` → Pi deadline-state → `GET /control/current` → Homey Bridge / Adapter / Gate / enige Easee-writer. De voormalige GitHub-fetcher is uitgefaseerd. Het historische Cloudflare/GitHub-kanaal voor **EMS-instellingen** is een aparte, nog bestaande uitzondering; activeer de oude Tesla-fetcher niet opnieuw.

## Begin hier: normatieve documenten

- [Actuele EMS-architectuur en productiestatus](docs/architecture/CURRENT-EMS-STATE.md)
- [Homey ↔ Pi dataflow](docs/architecture/homey-pi-runtime-dataflow.md)
- [Tesla-deadline end-to-end](docs/architecture/tesla-deadline-end-to-end.md)
- [Diagnostische bronhiërarchie](docs/architecture/diagnostic-source-of-truth.md)
- [Actuele bron- en rollbackpolicy](docs/architecture/current-runtime-source-policy.md)
- [Repositorystructuur en touch-it-place-it](docs/architecture/repository-structure.md)
- [Publieke-data-inventaris en uitzonderingen](docs/architecture/public-data-boundary.md)

Historische baselines, cutover-verslagen en oude `docs/javascripts/` zijn geen bewijs van de huidige Homey- of Pi-runtime. Vergelijk bij productievragen altijd de live Homey-flow, de Pi-runtime en de actuele `main`.

## Aanpak en verificatie

```bash
git status -sb
python3 scripts/validate_repository.py
bash scripts/ems_architecture_gate.sh
bash tools/validation/repository_structure_gate.sh
```

Gebruik voor gewijzigde code daarnaast de **gerichte** standalone tests in `tests/`. Deze controles schrijven geen fysieke actuatorcommando's. Een Git-pull is niet automatisch een Pi-runtime-deployment: bron, runtime en services moeten waar nodig apart en gecontroleerd worden gevalideerd.

`main` is de software source-of-truth. Productie-promotie vereist passende backup, regressies, driftcontrole en expliciete uitvoering; geen impliciete Homey-updates, Honeywell-writes of extra runtime-publishers.

## Publieke data en beveiliging

`docs/data/` is **default-deny** voor nieuwe JSON. Alleen expliciet toegestane contracten, modelaannames en tijdelijke command/config-compatibiliteit blijven op `main`. Historische huishoudelijke snapshots zijn in oktober 2026 uit de actuele tree verwijderd. Lees nooit publiek GitHub-JSON als actuele P1-, Honeywell-, Tesla- of EV-toestand. Canonieke runtimebestanden en SQLite-historie staan privé op de Pi.

**Let op:** verwijderde gegevens kunnen nog in publieke Git-geschiedenis, forks of caches staan. De twee overgebleven GitHub-commandartefacten (`ems-settings-command.json` en het oude `tesla-deadline-command.json`) blijven bovendien publiek tot hun afzonderlijke uitfasering. Bewaar geen secrets in deze repository.
