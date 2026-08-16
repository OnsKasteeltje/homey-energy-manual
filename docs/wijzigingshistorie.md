# Wijzigingshistorie

## v2.7 — 16 augustus 2026

- Homepage conceptueel vereenvoudigd: het dashboard toont voortaan **functionele capabilities/systemen** in plaats van iedere afzonderlijke Homey-flow.
- Per capability wordt slechts één actuele implementatie getoond, inclusief de echte Homey-flownaam, enabled-status en broken-status.
- Oude, uitgeschakelde en experimentele flowversies verdwijnen daarmee van het operationele homepage-dashboard; deze blijven onderdeel van de technische flowdocumentatie.
- Eerste capabilities: **Warmwateroptimalisatie**, **Energie Manager**, **Tesla-regeling**, **M7 Opportunity**, **Prijs- en PV-forecast** en **Website-statuspublicatie**.
- De homepage maakt daarmee expliciet onderscheid tussen *wat de woning/Homey functioneel doet* en *welke concrete flowversie dit technisch implementeert*.
- Dit sluit aan op de projectfocus **woning + Homey klaar voor Victron**: de homepage fungeert als operationeel architectuurdashboard, terwijl detailpagina's de technische flowimplementatie en versiehistorie tonen.

## v2.6 — 16 augustus 2026

- Homepage-statusprobleem structureel bij de bron opgelost: de algemene Homey-statuspublisher selecteert voor geversioneerde flowfamilies voortaan de **actieve, niet-broken versie** in plaats van één oude exact vastgelegde flownaam.
- Nieuwe actieve systeemflow **`GitHub status sync - Homey lokaal v1.2`** aangemaakt en gevalideerd; de oude ongenummerde statuspublisher is daarna uitgeschakeld.
- De nieuwe publisher publiceerde succesvol **`Warm water optimalisatie - PV boiler + CV advies v1.2 nacht-test`** als actief en **`Energie Manager PV - Shadow Mode v1.6.6`** als actieve shadowversie.
- Ook **`M7 - Opportunity Score - Shadow v1.3`** wordt nu automatisch als actuele actieve versie van die flowfamilie herkend.
- Homepage-links zijn family-aware gemaakt, zodat geversioneerde warmwater-, Energy Manager-, M7- en status-syncflows naar de juiste documentatie blijven linken.
- Hiermee is de statusweergave niet meer afhankelijk van handmatige aanpassing van de homepage wanneer een hoofdflow een nieuwe subversie krijgt.

## v2.5 — 16 augustus 2026

- Homepage-status van de **Energie Manager PV** gecorrigeerd zodat niet langer de oude ongenummerde, uitgeschakelde flow als hoofdstatus wordt getoond.
- De homepage gebruikt voor de actuele Energy Manager-versie en enabled-status aanvullend `shadow-baseline-v01.json` als operationele bron.
- Daardoor wordt de daadwerkelijk publicerende nieuwste flowversie — momenteel **`Energie Manager PV - Shadow Mode v1.6.6`** — op de homepage als **Actief** weergegeven.

## v2.4 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Energie Manager PV - Shadow Mode v1.6.6`** gedocumenteerd; v1.6.5 is uitgeschakeld zodat binnen deze flowfamilie slechts één versie actief is.
- v1.6.6 blijft volledig **shadow/read-only** en voegt geen fysieke apparaatsturing toe.
- De bestaande baseline-publicatie is uitgebreid met `washerActive` en `dryerActive`.

## v2.3 — 16 augustus 2026

- **Live energiestroom** uitgebreid met een uitsplitsing onder **Huishouden** voor **Wasmachine**, **Droger**, **Vaatwasser** en **Overig huishouden**.
- Er wordt bewust geen extra Homey-polling of nieuwe meetflow toegevoegd.

## v2.2 — 16 augustus 2026

- Nieuwe actieve Homey-flow **`Energie Manager PV - Shadow Mode v1.6.5`** toegevoegd; v1.6.4 is uitgeschakeld.
- Energy Manager-observatie uitgebreid met P1 L1/L2/L3 en Easee/Equalizer-context.

## v2.1 — 16 augustus 2026

- **Easee Equalizer** expliciet vastgelegd als harde lokale load-balancing-/veiligheidslaag.
- Regelhiërarchie toegevoegd: **installatieveiligheid / 3×25 A → Easee Equalizer → Victron grid/batterijregeling (later) → Homey Energy Manager → flexibele verbruikers**.

## v2.0 — 16 augustus 2026

- Nieuwe hoofdtab **Live energiestroom** toegevoegd.
- Energy Manager expliciet als besturings-/orchestratie-laag buiten het elektrische stroompad weergegeven.
- Nieuwe 24-uurs fasevisualisatie toegevoegd voor L1, L2 en L3.

## v1.9 — 15 augustus 2026

- Opmaak van de volledige wijzigingshistorie geüniformeerd; nieuwste versie staat voortaan bovenaan.

## v1.8 — 15 augustus 2026

- De drie PV-omvormers als afzonderlijke apparaten aan **Groepen & fasen** toegevoegd.

## v1.7 — 15 augustus 2026

- **Groepen & fasen** bijgewerkt met bevestigde fasekoppelingen en versiebeheerregel aangescherpt.

## v1.6 — 15 augustus 2026

- Nieuwe hoofdtab **Groepen & fasen** toegevoegd.

## v1.5 — 15 augustus 2026

- Architectuuroverzicht uitgebreid met energieprioriteit, constraints en toekomstige Victron-laag.

## v1.4 — 15 augustus 2026

- Warmwaterpagina uitgebreid tot volledige functionele handleiding.

## v1.3 — 14 augustus 2026

- Huidig en gepland boilervenster verduidelijkt.

## v1.2 — 14 augustus 2026

- Warmwaterhoofdstuk bijgewerkt.

## v1.1 — 14 augustus 2026

- Energie Manager PV - Shadow Mode toegevoegd.

## v1.0 — 14 augustus 2026

- Eerste versie van de Homey Flow Manual gepubliceerd.
