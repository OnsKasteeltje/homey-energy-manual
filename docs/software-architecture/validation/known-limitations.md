---
component: validation
title: Bekende Beperkingen
version: 0.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-25
---

# Bekende Beperkingen

## Actuele beperkingen

- **Victron/batterij** — nog niet runtime-geïntegreerd; `battery.integrated=false` en planneruitkomsten zijn simulatie, geen gerealiseerde besparing/control.
- **Generieke Power Intent/Actuator Commands** — SHADOW; geen fysieke writer-cut-over.
- **Warmwatercontrol** — slimme Core/WW-control is SHADOW; fysieke boilerwrites lopen nog via legacy tijdflows. De HYBRID-actuator is geen actieve productiewriter.
- **Opportunity Engine** — architectuurfunctie is verdeeld over Core, contract-aware decision, WW advisor en Power Intent; nog geen geconsolideerde generieke writer.
- **Fingerprint Engine** — Quooker en laundry hebben runtime-detectie; waterkoker, vaatwasser en ovens zijn niet allemaal zelfstandige control-grade Homey-detectors.
- **Derived house balance** — bij PV/source-skew kan `house_load`/`Overig` bewust ongeldig zijn terwijl P1-control geldig blijft.
- **Publisher metadata** — live Publisher-flow v1.0.4 publiceert in payload nog `meta.publisher_version=EM2_PUBLISHER_V1.0.3`; schema/frontend verwachten dit momenteel bewust. Wijziging moet atomair gebeuren.
- **Schema coverage** — live secties zoals `quatt` en `equalizer` zijn niet volledig als strict JSON Schema gemodelleerd en vallen deels onder `additionalProperties`.
- **Homey API/rate limits** — extra pollers kunnen throttling veroorzaken; daarom blijft single-reader/event-assisted architectuur bindend.
- **Runtime readback via connector** — sommige Homey Logic-uitgangen zijn niet rechtstreeks via de gebruikte connector terug te lezen; fysieke/Logic-validatie vereist dan alternatieve readback of gepubliceerde state.

## Beperkingen die geen bug zijn

SHADOW- of planned-componenten mogen bestaan naast productie zolang zij geen fysieke writes uitvoeren en duidelijk gemarkeerd zijn. Stale/asynchrone afgeleide PV/huisdata mag diagnostiek degraderen zonder de autoritatieve P1-netmeting te blokkeren.

## Exit-regel

Een beperking wordt pas verwijderd wanneer de corresponderende code/configuratie én runtime-validatie zijn afgerond en de betrokken component-/flowdocumentatie in dezelfde change is bijgewerkt.
