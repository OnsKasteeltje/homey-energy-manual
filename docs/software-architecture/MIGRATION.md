# Migratieplan naar modulaire softwarearchitectuur

De bestaande `docs/`-pagina's blijven tijdens de migratie beschikbaar. Nieuwe architectuurmodules worden pas leidend nadat ze inhoudelijk tegen de actuele implementatie zijn gevalideerd.

## Fase 1 — Framework

- [x] Structuur en bron-van-waarheid-regels vastleggen.
- [x] Componenttemplate vastleggen.
- [x] ADR-template vastleggen.
- [x] Assembly manifest toevoegen.
- [x] Architectuurprincipes vastleggen.

## Fase 2 — Kerncomponenten migreren

Voorgestelde bronmapping:

| Nieuwe module | Bestaande bron(nen) | Validatie tegen code vereist |
| --- | --- | --- |
| `components/core.md` | `docs/energy-core-v2.md`, `docs/architectuur.md` | ja |
| `components/tesla.md` | bestaande Tesla-documentatie en flows | ja |
| `components/boiler.md` | warmwater-/boilerdocumentatie | ja |
| `components/quooker.md` | Quooker-documentatie/detector | ja |
| `components/opportunity-engine.md` | `docs/energie-manager.md` en M7-/opportunity-logica | ja |
| `components/price-adapter.md` | `docs/contract-types.md` en PBTH/contract-aware code | ja |
| `components/fingerprint-engine.md` | fingerprint-/telemetriedocumentatie | ja |
| `components/victron-adapter.md` | huidige SHADOW-/adapterdocumentatie | ja |

## Fase 3 — Procesflows

Voor iedere kerncomponent wordt de actuele flow rechtstreeks uit de huidige code/configuratie gereconstrueerd. De bestaande diagrammen worden alleen hergebruikt als ze aantoonbaar overeenkomen met de implementatie.

## Fase 4 — Validatiehoofdstukken

RC-hardening, idempotency, reboot recovery, runtime smoke-tests en bekende beperkingen worden onder `validation/` samengebracht.

## Fase 5 — Generator

Een buildscript leest `manifest.yaml`, valideert frontmatter en bronpaden en maakt:

1. `generated/software-architecture.md`;
2. DOCX-release;
3. PDF-release.

De generator moet falen bij ontbrekende verplichte metadata of ontbrekende manifestbestanden.

## Fase 6 — CI

GitHub Actions controleert bij relevante wijzigingen minimaal:

- geldige YAML-frontmatter;
- alle `manifest.yaml`-bestanden bestaan;
- bronpaden bestaan;
- geen handmatige wijziging aan `generated/` zonder generator-update;
- optioneel: stale-documentatiecontrole op basis van `last_verified` en gewijzigde bronbestanden.
