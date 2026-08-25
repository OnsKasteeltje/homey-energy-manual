---
component: architecture
 title: Architectuurprincipes
version: 0.1.0
status: active
architecture_status: implemented
last_verified: 2026-08-25
source:
  - docs/architectuur-guardrails.md
  - docs/architectuur.md
  - docs/codekwaliteit.md
---

# Architectuurprincipes

## Code/configuratie is leidend

De actuele software-implementatie, Homey-flowconfiguratie en gedeployde configuratie zijn leidend voor de beschrijving van het systeem. Documentatie mag geen gewenst gedrag presenteren alsof het reeds actief is.

## Procesflows volgen de actuele implementatie

Procesflowdiagrammen beschrijven altijd de actuele gecodeerde situatie. Bij iedere relevante wijziging aan beslislogica, state-transities, guards of fysieke acties wordt het bijbehorende diagram opnieuw gecontroleerd tegen de implementatie.

## SHADOW en ACTIVE zijn expliciet gescheiden

Logica die alleen rekent, observeert of valideert wordt als `shadow` gemarkeerd. Alleen aantoonbaar geactiveerde logica die fysieke acties kan uitvoeren wordt als `active` beschreven.

## Gelaagde architectuur

Beslislogica, device-adapters, runtime-state, telemetrie en presentatie worden als afzonderlijke verantwoordelijkheden behandeld. Device-specifieke writes worden zo veel mogelijk achter adapters of duidelijk afgebakende controllerlagen geplaatst.

## Idempotency is een architectuureis

Herhaalde Core-ticks, dubbele triggers of retries mogen niet leiden tot dubbele fysieke acties, dubbele notificaties of dubbele historie-records. Componentdocumentatie beschrijft daarom expliciet welke lease-, deduplicatie- of write-suppressionmaatregelen gelden.

## Fail-safe bij onbetrouwbare input

Stale, ontbrekende of inconsistente input mag niet zonder expliciete guard naar een fysieke write leiden. De documentatie beschrijft per component fallback- en suppressiegedrag.

## Documentatie is modulair en reproduceerbaar

De technische broninformatie wordt in afzonderlijke Markdown-modules onderhouden. Het masterdocument is een afgeleid artefact dat via `manifest.yaml` in vaste volgorde wordt samengesteld en niet handmatig wordt aangepast.

## Traceerbaarheid

Iedere architectuurmodule bevat `source`-verwijzingen en `last_verified`. Daarmee is zichtbaar waar de beschreven logica vandaan komt en wanneer deze voor het laatst tegen de implementatie is gecontroleerd.
