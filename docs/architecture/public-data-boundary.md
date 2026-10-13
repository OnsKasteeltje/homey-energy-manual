# Publieke-data-grens — docs/data

**Status 2026-10-13 — broncodebeleid, geen nieuwe runtime-transportlaag.**

De repository `OnsKasteeltje/homey-energy-manual` is publiek. GitHub Pages publiceert alleen een neutrale `index.html`; de private Pi-site gebruikt `/web/*` en lokale runtimebestanden. Daardoor horen gebruikersmetingen, realtime status, Honeywell-ruimteschema's, Tesla-sessies en huishouddiagnostiek **niet** als statische `docs/data/*.json` op `main`.

## Expliciet behouden — 7 JSON-bestanden

| Bestand in `docs/data/` | Rol / reden om voorlopig te behouden |
| --- | --- |
| `energy-state-v2.schema.json` | Broncontract voor validator en frontend-bundlebuild |
| `ems-settings-command.json` | **Legacy GitHub-ingress nog gebruikt:** Web Data API leest dit artefact; Cloudflare Worker kan het schrijven |
| `tesla-control-config.json` | Nog door `deploy/install/install_private_frontend_v2.sh` in de frontend geplaatst; geen actieve Tesla-commandroute |
| `tesla-deadline-command.json` | **Niet langer Pi-commandbron**, maar de oude Cloudflare Worker bevat nog een GitHub-writepad; apart uitschakelen vóór verwijderen |
| `business-case-calibration-v1.json` | Bewaarde, niet-operationele Victron-calibratieaannames |
| `business-case-capex-v1.json` | Bewaarde CAPEX/marktprijsreferenties voor businesscase-analyse |
| `business-case-scenarios-v2.json` | Bewaarde businesscase-scenarioaannames |

De drie businesscase-JSON's zijn **modelgegevens**, geen actieve EMS-runtime en geen bewijs voor actuele aanschafprijzen. De twee commandartefacten zijn expliciete tijdelijke uitzonderingen en zijn **niet privé** zolang de repository publiek is.

## Uit de actuele tree verwijderd — 18 JSON-bestanden

| Categorie | Verwijderde bestandsnamen (alle onder `docs/data/`) |
| --- | --- |
| Historische P1/PV/Huis/WW/EV-snapshots | `energy-daily-history.json`, `energy-day-series-7d.json`, `energy-live.json`, `boiler-cycles.json`, `pv-phase-24h.json`, `m7-opportunity.json`, `shadow-baseline-v01.json` |
| Oude publieke toestand en diagnosestatus | `energy-manager-shadow-state.json`, `ev-control-status.json`, `homey-status.json`, `shadow-status.json`, `tesla-runtime.json` |
| Ruimteschema en toestel-/huishoudobservaties | `honeywell-schedule.json`, `laundry-analysis.json`, `bertazzoni-dishwasher-reference-events.json`, `oven-reference-events.json`, `tesla-charge-calibration.json`, `ems-phase-topology.json` |

De oude `scripts/recover_energy_history.py` las de twee daghistorie-JSON's maar vereiste tevens het reeds verwijderde `energy-day-v2.json`. Deze herstelroute hoorde bij de retired Homey→GitHub day-series publisher en is geen bruikbare Pi-history recovery. `scripts/build_status.py` hoorde bij de oude publieke Homey-statuspublicatie; ook die is uitgefaseerd. De eerdere Pages-`docs/javascripts/` kunnen nog historische verwijzingen naar verwijderde JSON bevatten, maar behoren niet tot het gepubliceerde Pages-artefact of het actuele private frontend.

## Guardrails

1. Nieuwe `docs/data/*.json` zijn standaard verboden door `.gitignore` en een allowlist in `scripts/ems_architecture_gate.sh`. Nieuwe uitzonderingen vereisen een bewust ontwerp en een gelijktijdige wijziging van deze inventaris.
2. Geen automatische Homey-/Pi-telemetrie, CV-schema's, P1-data, Tesla-SoC, fysieke toestelmetingen of historie publiceren naar de publieke GitHub-repository.
3. De Pi-lokale SQLite-archieven en `/home/jeroen/ems/data/` blijven de operationele waarheid. GitHub `main` blijft uitsluitend software-/documentatiebron plus de hierboven beschreven compatibiliteitsuitzonderingen.
4. Uitfaseren van de twee GitHub-commandbestanden kan **niet** alleen met `git rm`: eerst de bijbehorende Cloudflare/website/Web Data API-consumers en eventueel nog actieve writers expliciet controleren.
5. Verwijderen uit de huidige tree verwijdert geen gevoelige gegevens uit Git-historie, clones, forks of caches. Hiervoor is een afzonderlijke privacy-/geschiedenisaanpak nodig.

## Buiten scope

Geen verandering aan Pi-runtime, Homey-flowconfiguratie, Honeywell-setpoints, Easee- of warmwateractuatoren, of de SwiftUI-ontwikkelbranch.
