---
component: publisher-public-state
title: Publisher and Public State Contract
version: 1.0.4
status: active
architecture_status: validated
last_verified: 2026-08-25
source:
  - Homey Advanced Flow: EM v2 | 04 Publisher | v1.0.4 (Tesla lifecycle)
  - Homey Advanced Flow: EM v2 | 20 Power Intent | P1 v0.2 SHADOW
---

# Publisher and Public State Contract

## 1. Doel

De Publisher vormt de grens tussen de interne Energy Core-state en de publiek consumeerbare JSON-state. De live implementatie publiceert `EM2_Public_State` naar `docs/data/energy-state-v2.json` in GitHub en bewaakt tegelijk revision- en heartbeatgedrag.

Belangrijk: `EM2_Public_State` is niet alleen website-output. Een succesvolle publish herschrijft dezelfde Homey Logic-variabele, waardoor downstream Power Intent opnieuw wordt getriggerd. Daarmee is deze laag ook een synchronisatie- en triggerboundary.

## 2. Scope

De live flow is `EM v2 | 04 Publisher | v1.0.4 (Tesla lifecycle)`.

De flow:

- draait elke 5 minuten met 60 seconden vertraging;
- kan handmatig gestart worden;
- leest uitsluitend Homey Logic-variabelen;
- leest geen devices;
- verrijkt de publieke Tesla-state met `EV Deadline status`;
- publiceert JSON naar GitHub `main`;
- schrijft publicatiestatus en revision-metadata terug naar Homey Logic.

## 3. Inputs

Belangrijkste inputs:

- `EM2_Public_State` — reeds door Core opgebouwde publieke state;
- `EV Deadline status` — Tesla lifecycle-verrijking;
- `GH_Status_Token` — token voor GitHub Contents API;
- `EM2_Last_Published_Revision` — laatst succesvol gepubliceerde revision;
- `EM2_Last_Publish` — timestamp van laatste succesvolle publish;
- `EM2_Publish_Due` — force/retry-vlag.

De publisher bepaalt `sourceRevision` uit `payload.meta.state_revision`.

## 4. Outputs

Bij succesvolle publicatie worden bijgewerkt:

- GitHub `docs/data/energy-state-v2.json`;
- `EM2_Public_State` met de daadwerkelijk gepubliceerde payload;
- `EM2_Last_Publish`;
- `EM2_Last_Published_Revision`;
- `EM2_Last_Publisher_Version`;
- `EM2_Publish_Due=false`;
- `EM2_Publisher_Status` met status `PUBLISHED`.

## 5. State model

De publisher kent functioneel deze uitkomsten:

- `BLOCKED_PUBLIC_STATE_MISSING`
- `BLOCKED_REVISION_MISSING`
- `BLOCKED_TOKEN_MISSING`
- `SKIP_CURRENT`
- `GITHUB_GET_ERROR`
- `GITHUB_PUT_ERROR`
- `PUBLISHED`
- `ERROR`

Bij blokkerende of technische fouten blijft `EM2_Publish_Due=true`, zodat een volgende run opnieuw probeert.

## 6. Beslislogica

Publicatie is nodig wanneer minimaal één van deze condities geldt:

1. de huidige `state_revision` wijkt af van `EM2_Last_Published_Revision`;
2. de laatste succesvolle publish is minstens 6 minuten oud;
3. `EM2_Publish_Due` staat expliciet op true.

Als geen van deze condities geldt, volgt `SKIP_CURRENT`.

De publish-reason wordt:

- `REVISION_RETRY` bij een nieuwe revision;
- `FORCED_RETRY` bij `EM2_Publish_Due=true`;
- `HEARTBEAT_RETRY` bij alleen de 6-minuten heartbeat.

## 7. Procesflow

Zie `../flows/publisher-public-state-flow.md`.

## 8. Foutafhandeling

De publisher faalt gesloten voor publicatie: bij ontbrekende state, revision, token of GitHub-fout wordt geen succesvolle publish gemarkeerd. `EM2_Publish_Due` blijft true zodat recovery zonder handmatige state-reparatie mogelijk is.

Een GET op het doelbestand mag 404 retourneren; dan wordt het bestand bij de PUT aangemaakt. Andere GET-statuscodes blokkeren de publish.

## 9. Idempotency

De primaire idempotency-key is `state_revision`.

Een onveranderde revision wordt niet opnieuw gepubliceerd zolang:

- de heartbeat jonger is dan 6 minuten; en
- geen force/retry-vlag actief is.

De publisher is dus revision-driven met heartbeat-republish voor freshness.

## 10. SHADOW/ACTIVE-status

De Publisher zelf is ACTIVE: hij schrijft daadwerkelijk naar GitHub en naar Homey Logic.

De downstream Power Intent-laag blijft SHADOW. Een succesvolle publisher-write naar `EM2_Public_State` triggert `EM v2 | 20 Power Intent | P1 v0.2 SHADOW`, maar die voert geen fysieke actuatorwrites uit.

## 11. Revision-contract met Power Intent

Power Intent wordt getriggerd door iedere wijziging van `EM2_Public_State`.

Daarna leest Power Intent vier revisions:

- `EM2_Public_State.meta.state_revision`;
- `EM2_State.revision`;
- `EM2_Decision.sourceRevision`;
- `EM2_Control_WW.sourceRevision`.

Alle vier moeten exact gelijk zijn. Alleen dan is `EM2_Power_Intent.valid=true`.

Bij mismatch publiceert Power Intent:

- `valid=false`;
- `status=REVISION_MISMATCH`;
- EV `target_W=0`.

Dit voorkomt dat een nieuwe publieke revision wordt gecombineerd met oudere Decision- of WW-Control-output.

## 12. Website-contract

Het gepubliceerde bestand is `docs/data/energy-state-v2.json` op branch `main`.

De publisher zet vóór publicatie minimaal deze metavelden:

- `generated_at`;
- `heartbeat_at`;
- `publisher_version`;
- `publish_reason`.

Daarnaast wordt `tesla.deadline_status` verrijkt vanuit `EV Deadline status`.

De website moet de gepubliceerde JSON als presentation/read-model behandelen en mag daaruit geen actuatorbeleid terug de Core in schrijven.

## 13. Bekende beperking

In de live code wordt `payload.meta.publisher_version` momenteel gevuld met `EM2_PUBLISHER_V1.0.3`, terwijl `EM2_Last_Publisher_Version` en de status-wrapper `EM2_PUBLISHER_V1.0.4` gebruiken. Dit is een metadata-inconsistentie, geen functionele revision-fout, maar moet in een volgende Publisher-versie worden gelijkgetrokken.

## 14. Safety invariants

- geen device reads in Publisher;
- geen actuatorwrites;
- publicatie alleen met geldige numerieke state revision;
- mislukte publish zet retry-vlag;
- downstream numerieke intent vereist volledige revision-alignment;
- website/public JSON is read-model, geen policy-owner.

## 15. Bronbestanden

- Homey Advanced Flow `EM v2 | 04 Publisher | v1.0.4 (Tesla lifecycle)`
- Homey Advanced Flow `EM v2 | 20 Power Intent | P1 v0.2 SHADOW`
- GitHub output `docs/data/energy-state-v2.json`
