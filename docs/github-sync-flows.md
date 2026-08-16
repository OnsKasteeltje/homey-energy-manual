# GitHub status- en shadow-sync

**Status:** 🟢 Reguliere status-sync actief; aparte centrale shadow-sync uitgeschakeld  
**Actieve statusflow:** `GitHub status sync - Homey lokaal v1.4`

De reguliere status-sync blijft periodiek actief. De aparte `GitHub shadow sync - Homey lokaal` staat **uit**. Shadowdata wordt rechtstreeks vanuit de betreffende analyseflow gepubliceerd. Geen van deze synchronisaties stuurt apparaten aan.

## Uitgangspunt: Homey en website blijven synchroon

De Homey-flows zijn de technische implementatie; deze website is de actuele functionele en technische documentatie daarvan.

> **Een wijziging aan een Homey-flow is pas compleet wanneer een nieuwe flowversie is aangemaakt én de bijbehorende websitebeschrijving is bijgewerkt.**

Bij iedere flowwijziging controleren we minimaal:

- exacte flownaam, versienummer en status;
- trigger en uitvoeringsfrequentie;
- inputs, Logic-variabelen en relevante Homey-tags;
- beslislogica, drempels, prioriteiten en tijdvensters;
- outputs en eventueel werkelijk aangestuurde apparaten;
- afhankelijkheden tussen flows;
- centrale state versus lokale state;
- websitepublicatie: ritme, JSON-bestand en bewaartermijn;
- links vanaf de homepage en navigatie naar de juiste flowbeschrijving.

## Verplichte flowversionering

Vanaf 15 augustus 2026 worden bestaande Homey-flows niet meer inhoudelijk in-place aangepast. Een inhoudelijke wijziging leidt tot een nieuwe versie.

```text
<functionele flownaam> vX.Y
```

Van dezelfde functionele flowfamilie mag maximaal **één versie actief** zijn. Oude versies blijven als rollback-/referentiepunt bestaan, maar worden gedeactiveerd zodra de opvolger is gevalideerd.

## Reguliere status-sync v1.4

`GitHub status sync - Homey lokaal v1.4` publiceert de algemene flowstatus naar:

- `docs/data/homey-status.json`;
- `docs/data/shadow-status.json`.

Vanaf v1.4 is de frequentie verlaagd van **15 naar 30 minuten**. Flowstatus verandert zelden zo snel dat een kwartierpublisher nodig is. Hiermee worden Homey-flowinventarisatie en GitHub GET/PUT-verkeer gehalveerd zonder invloed op de fysieke energieregeling.

De status-sync leest onder andere de actuele Standard en Advanced Flows en selecteert per flowfamilie de actieve, niet-broken versie.

## Centrale runtime-state

Sinds 16 augustus 2026 is de meetarchitectuur uitgebreid met:

```text
Energy Manager State Collector v1.0
        ↓
EM_Runtime_State
```

Deze collector draait iedere twee minuten en vormt één gedeelde runtime-snapshot voor consumers die geen veiligheidskritische directe device-read nodig hebben.

Actuele consumers zijn onder andere:

- `Energy Manager Allocator - Shadow v0.2.4`;
- `Live energie publicatie v1.2`.

Hiermee wordt voorkomen dat iedere flow opnieuw alle Homey-devices ophaalt.

## Shadowpublicatie — actuele architectuur

| Flow | Analyse | Websitepublicatie | Bestand |
|---|---|---|---|
| `Energie Manager PV - Shadow Mode v1.6.7` | iedere 5 minuten | intern ongeveer iedere 15 minuten | `docs/data/shadow-baseline-v01.json` |
| `Energy Manager Allocator - Shadow v0.2.4` | iedere 5 minuten uit `EM_Runtime_State` | state/decision/validation in Homey Logic | geen eigen zware GitHub-publisher |
| `M7 - Opportunity Score - Shadow v1.3` | iedere 15 minuten | dezelfde kwartier-run | `docs/data/m7-opportunity.json` |
| `M7 - Prijs en PV forecast context - read only` | iedere 15 minuten | gedeelde Homey Logic-context | geen apparaatsturing |

### Shadow v1.6.7

De vorige v1.6.6-versie had een 2-minutentrigger én een aparte 15-minutentrigger die naar hetzelfde zware HomeyScript liepen. Vanaf v1.6.7 is dat teruggebracht tot **één 5-minutentrigger**.

De flow bepaalt intern of GitHub-publicatie nodig is. Daardoor blijven shadowhistorie en boileranalyse beschikbaar, terwijl het aantal zware HomeyScript-runs aanzienlijk lager wordt.

### Allocator v0.2.4

Allocator v0.2.4 leest geen volledige devicelijst meer. De flow gebruikt de centrale `EM_Runtime_State`, aangevuld met relevante Flow Tags en warmwaterstatus. Een state ouder dan vijf minuten wordt bewust geweigerd.

De allocator blijft volledig **shadow/read-only**.

### Live energie v1.2

De live publisher blijft één website-snapshot per vijf minuten publiceren naar `docs/data/energy-live.json`, maar leest vanaf v1.2 de centrale runtime-state. Daarmee is de extra `getDevices()` uit de vorige publisher verwijderd.

## Websitehistorie versus Homey-state

De JSON-bestanden onder `docs/data/` zijn de persistente websitehistorie. Ze moeten niet worden verward met runtime-state:

- `EM_Runtime_State` is een actuele gedeelde Homey-snapshot;
- Homey Logic bewaart gedeelde regel- en shadowstatus;
- GitHub JSON bewaart gepubliceerde historie voor website en analyse.

De website kan daardoor een ander publicatieritme hebben dan de interne Homey-regelcyclus zonder dat dit een fout is.

## Homey API-belasting

Na de optimalisatie van 16 augustus 2026 gelden de volgende ontwerpregels:

- één centrale device-/Logic-read waar consumers data veilig kunnen delen;
- Tesla v2.6 blijft rechtstreeks meten vanwege veiligheidskritische laadbesturing;
- Shadow draait 5-minuten in plaats van 2-minuten plus extra 15-minutentrigger;
- live energie gebruikt centrale state;
- status-sync draait iedere 30 minuten;
- de aparte `GitHub shadow sync - Homey lokaal` blijft uit;
- analyse/historie/visualisatie blijft buiten de kritische fysieke besturingsroute.

## Actuele cadans

| Flow | Ritme |
|---|---:|
| `Energy Manager State Collector v1.0` | 2 min |
| `Tesla laden v2.6` | 2 min |
| `Energie Manager PV - Shadow Mode v1.6.7` | 5 min |
| `Energy Manager Allocator - Shadow v0.2.4` | 5 min |
| `Live energie publicatie v1.2` | 5 min |
| M7 context / opportunity | 15 min |
| `GitHub status sync - Homey lokaal v1.4` | 30 min |

## Foutisolatie

Websitepublicatie en energielogica blijven conceptueel gescheiden. Een probleem met GitHub of de website mag de energiemeting of fysieke besturing niet blokkeren. Publicatiefouten moeten zichtbaar worden zonder de primaire regelroute onnodig te verstoren.

## Aangestuurde apparaten

**Geen.** De hier beschreven status-, runtime- en shadowpublicatie is telemetrie/documentatie. Fysieke Tesla-aansturing blijft eigendom van `Tesla laden v2.6`.

## Afhankelijkheden

HomeyScript, gedeelde Homey Logic, `GH_Status_Token` en de repository `OnsKasteeltje/homey-energy-manual`.

> Laatste update: **16 augustus 2026** — centrale state collector toegevoegd, shadowcadance verlaagd, live publisher gecentraliseerd en status-sync naar 30 minuten gebracht.
