---
component: architecture
title: Architectuurprincipes
version: 0.3.0
status: active
architecture_status: implemented
last_verified: 2026-08-29
source:
  - docs/architectuur-guardrails.md
  - docs/architectuur.md
  - docs/codekwaliteit.md
  - docs/software-architecture/architecture/05-homey-api-load-governance.md
  - docs/software-architecture/operations/homey-api-load-map.md
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

## Live Energy Attribution is direct-first en inference-light

Een individuele verbruiker wordt in de reguliere Live Energy View alleen afzonderlijk weergegeven wanneer ten minste één van de volgende bronnen beschikbaar is:

1. direct gemeten apparaatvermogen; of
2. betrouwbare directe apparaatstatus waarmee actief/inactief kan worden vastgesteld.

Wanneer alleen een directe status beschikbaar is, mag het apparaat als actief/inactief worden getoond, maar het vermogen blijft `null/onbekend` en wordt niet uit P1-fingerprints ingevuld.

P1-/fingerprint-inference wordt niet gebruikt voor reguliere live device-attributie. Apparaten die alleen via een afgeleid patroon herkenbaar zijn vallen qua vermogen onder `Overige`. Fingerprints blijven uitsluitend diagnostisch/analysegericht en mogen geen continue Homey-runtime-load veroorzaken wanneer zij niet voor control of expliciete validatie nodig zijn.

De residuele live last wordt daarom bepaald als totale huishoudlast minus de som van rechtstreeks gemeten afzonderlijke verbruikers. Een status-only device wordt niet met fictief vermogen van het residu afgetrokken.

## Idempotency is een architectuureis

Herhaalde Core-ticks, dubbele triggers of retries mogen niet leiden tot dubbele fysieke acties, dubbele notificaties of dubbele historie-records. Componentdocumentatie beschrijft daarom expliciet welke lease-, deduplicatie- of write-suppressionmaatregelen gelden.

## Fail-safe bij onbetrouwbare input

Stale, ontbrekende of inconsistente input mag niet zonder expliciete guard naar een fysieke write leiden. De documentatie beschrijft per component fallback- en suppressiegedrag.

## Homey API- en runtimeload is een expliciete architectuurconstraint

Een functioneel correcte flow is niet production-ready wanneer de extra Homey-load niet is gekwantificeerd. Iedere nieuwe of materieel gewijzigde flow wordt opgenomen in de versiebeheerbare **Homey API/Load Map** met triggerfrequentie, device-reads, Logic-reads/writes, flow-starts, Insights-calls, externe netwerkcalls, fysieke writes en event-/cascadefan-out.

Geen flow mag naar productie worden gepromoveerd wanneer de incrementele load onbekend is of buiten het afgesproken loadbudget valt. Wijzigingen in polling, triggerfrequentie, Logic-fan-out, netwerkpublicatie of device-access vereisen een gelijktijdige update van de Load Map.

De standaard is **single-reader first**: downstream logica consumeert canonieke runtime-state, zoals `EM2_State`, en voegt geen duplicerende device-poller toe zonder expliciet gedocumenteerde noodzaak. Sampling en externe publicatie hebben afzonderlijke cadansen en budgetten. Validatie-/evidenceflows hebben een expliciete lifecycle en mogen na afronding niet onbeperkt op volle runtimefrequentie actief blijven zonder productie-doel.

Bij throttling wordt één contributor tegelijk geïsoleerd op basis van de Load Map; safety gates en validatiecriteria worden daarbij nooit versoepeld. Zie `05-homey-api-load-governance.md` en `operations/homey-api-load-map.md`.

## Documentatie is modulair en reproduceerbaar

De technische broninformatie wordt in afzonderlijke Markdown-modules onderhouden. Het masterdocument is een afgeleid artefact dat via `manifest.yaml` in vaste volgorde wordt samengesteld en niet handmatig wordt aangepast.

## Traceerbaarheid

Iedere architectuurmodule bevat `source`-verwijzingen en `last_verified`. Daarmee is zichtbaar waar de beschreven logica vandaan komt en wanneer deze voor het laatst tegen de implementatie is gecontroleerd.
