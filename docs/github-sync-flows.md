# GitHub status- en shadow-sync

**Status:** 🟢 Reguliere status-sync actief; centrale shadow-sync uitgeschakeld  
**Flows:** `GitHub status sync - Homey lokaal` en `GitHub shadow sync - Homey lokaal`

De reguliere status-sync blijft periodiek actief. De aparte `GitHub shadow sync - Homey lokaal` staat **uit**. Shadowdata wordt rechtstreeks vanuit de betreffende analyseflow gepubliceerd. Geen van deze synchronisaties stuurt apparaten aan.

## Uitgangspunt: Homey en website blijven synchroon

De Homey-flows zijn de technische implementatie; deze website is de actuele functionele en technische documentatie daarvan. Daarom geldt voortaan:

> **Een wijziging aan een Homey-flow is pas compleet wanneer ook de bijbehorende websitebeschrijving is gecontroleerd en, waar nodig, bijgewerkt.**

Bij iedere flowwijziging controleren we minimaal:

- exacte flownaam en status: actief, shadow/test of uit;
- trigger en uitvoeringsfrequentie;
- inputs, Logic-variabelen en relevante Homey-tags;
- beslislogica, drempels, prioriteiten en tijdvensters;
- outputs en eventueel werkelijk aangestuurde apparaten;
- afhankelijkheden tussen flows;
- lokale state versus gedeelde Homey Logic-state;
- websitepublicatie: ritme, JSON-bestand en bewaartermijn;
- links vanaf de homepage en navigatie naar de juiste flowbeschrijving.

Dit voorkomt dat de website een oudere ontwerpversie beschrijft terwijl Homey al andere logica uitvoert.

## Reguliere status-sync

`GitHub status sync - Homey lokaal` publiceert de algemene flowstatus naar:

- `docs/data/homey-status.json`

Dit bestand voedt de flowkaarten en de live synchronisatietijd op de homepage. Deze status-sync staat los van de inhoudelijke shadowhistorie.

## Shadowpublicatie — huidige architectuur

HomeyScript `get()/set()`-state is kaart-lokaal en kan daarom niet als algemene opslag tussen afzonderlijke scriptkaarten worden gebruikt. De centrale shadow-sync is om die reden niet meer leidend.

| Flow | Meting/analyse | Websitepublicatie | Bestand |
| --- | --- | --- | --- |
| `Energie Manager PV - Shadow Mode` | iedere 2 minuten lokale baseline-sampling | aparte tak binnen dezelfde Advanced Flow, iedere 15 minuten; berekent zelfstandig één actueel sample | `docs/data/shadow-baseline-v01.json` |
| `Energie Manager PV - Shadow Mode v0.2 Quooker` | shadowanalyse met Quooker/warmwatergarantie | circa iedere 15 minuten wanneer deze versie actief wordt | `docs/data/shadow-v02-quooker.json` |
| `M7 - Opportunity Score - Shadow` | iedere 15 minuten | dezelfde kwartier-run voegt rechtstreeks één M7-sample toe | `docs/data/m7-opportunity.json` |

### Belangrijke nuance voor Baseline v0.1

Baseline heeft bewust **twee onafhankelijke takken binnen dezelfde Advanced Flow**:

1. **2-minuten sampler** — bouwt lokaal `EM_SHADOW_STATE` op en schrijft niet naar GitHub;
2. **15-minuten publisher** — leest de actuele P1-, Tesla- en boilerstatus opnieuw uit, berekent zelfstandig één baselinebeslissing en schrijft die naar GitHub.

De websitepublicatie is daardoor niet afhankelijk van kaart-lokale `get()/set()`-state. Deze route is op 15 augustus 2026 met een echt baseline-sample gevalideerd.

### M7 Opportunity

M7 gebruikt gedeelde Homey Logic-variabelen voor de prijs- en PV-context en schrijft zijn kwartiersample rechtstreeks naar GitHub. GitHub vormt voor M7 de persistente historie. Ook deze route is op 15 augustus 2026 met een echt M7-sample gevalideerd.

## Websitehistorie versus Homey-state

De JSON-bestanden onder `docs/data/` zijn de **persistente websitehistorie**. Ze moeten niet worden verward met tijdelijke/lokale HomeyScript-state:

- Homey lokale state ondersteunt de analyse tijdens runtime;
- Homey Logic wordt gebruikt wanneer informatie betrouwbaar tussen flows moet worden gedeeld;
- GitHub JSON bewaart de gepubliceerde historie voor analyse en weergave op de tab **Schaduw**.

De Schaduw-pagina leest deze datasets rechtstreeks. Daardoor kan de algemene homepage-status recent zijn terwijl een afzonderlijke shadowdataset een andere laatste publicatietijd heeft; dat is normaal zolang het bijbehorende publicatieritme klopt.

## Homey API-belasting

We beperken Homey-calls bewust:

- geen centrale periodieke shadow-poller;
- baseline publiceert slechts iedere 15 minuten naar GitHub, ondanks 2-minuten lokale sampling;
- M7 gebruikt per kwartier gezamenlijke uitlezingen voor de benodigde context;
- de uitgeschakelde centrale `GitHub shadow sync - Homey lokaal` veroorzaakt geen extra periodieke calls.

## Foutisolatie

Websitepublicatie en energielogica blijven conceptueel gescheiden. Een probleem met GitHub of de website mag de energiemeting of toekomstige apparaatbesturing niet blokkeren. Publicatiefouten moeten daarom zichtbaar worden gemaakt zonder de primaire flowlogica onnodig te verstoren.

## Aangestuurde apparaten

**Geen.** De hier beschreven status- en shadowpublicatie is uitsluitend telemetrie/documentatie.

## Afhankelijkheden

HomeyScript, gedeelde Homey Logic waar nodig, `GH_Status_Token` en de repository `OnsKasteeltje/homey-energy-manual`.
