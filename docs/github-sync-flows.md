# GitHub status- en shadow-sync

**Status:** 🟢 Reguliere status-sync actief; centrale shadow-sync uitgeschakeld  
**Flows:** `GitHub status sync - Homey lokaal` en `GitHub shadow sync - Homey lokaal`

De reguliere status-sync blijft periodiek actief. De aparte `GitHub shadow sync - Homey lokaal` staat **uit**. Shadowdata wordt rechtstreeks vanuit de betreffende analyseflow gepubliceerd. Geen van deze synchronisaties stuurt apparaten aan.

## Uitgangspunt: Homey en website blijven synchroon

De Homey-flows zijn de technische implementatie; deze website is de actuele functionele en technische documentatie daarvan. Daarom geldt voortaan:

> **Een wijziging aan een Homey-flow is pas compleet wanneer een nieuwe flowversie is aangemaakt én de bijbehorende websitebeschrijving is bijgewerkt.**

Bij iedere flowwijziging controleren we minimaal:

- exacte flownaam, versienummer en status: actief, shadow/test of uit;
- trigger en uitvoeringsfrequentie;
- inputs, Logic-variabelen en relevante Homey-tags;
- beslislogica, drempels, prioriteiten en tijdvensters;
- outputs en eventueel werkelijk aangestuurde apparaten;
- afhankelijkheden tussen flows;
- lokale state versus gedeelde Homey Logic-state;
- websitepublicatie: ritme, JSON-bestand en bewaartermijn;
- links vanaf de homepage en navigatie naar de juiste flowbeschrijving.

Dit voorkomt dat de website een oudere ontwerpversie beschrijft terwijl Homey al andere logica uitvoert.

## Verplichte flowversionering

Vanaf 15 augustus 2026 worden bestaande Homey-flows **niet meer in-place inhoudelijk gewijzigd**. Iedere inhoudelijke wijziging leidt tot een nieuwe versie van dezelfde functionele flow.

### Naamgeving

Nieuwe versies krijgen het versienummer in de flownaam:

```text
<functionele flownaam> vX.Y
```

Voorbeelden:

```text
Energie Manager PV - Shadow Mode v1.3
Energie Manager PV - Shadow Mode v1.4
M7 - Opportunity Score - Shadow v1.2
M7 - Opportunity Score - Shadow v1.3
```

Een normale aanpassing verhoogt de **subversie** (`Y`). Een grotere functionele herziening mag het hoofdversienummer (`X`) verhogen.

### Nieuwe versie maken, oude versie bewaren

Bij een wijziging geldt standaard:

1. lees de huidige flow en bepaal de actieve versie;
2. maak een **nieuwe flow** met dezelfde functionele naam en een hoger versienummer;
3. voer de wijziging uitsluitend in de nieuwe versie door;
4. valideer de nieuwe versie;
5. activeer de nieuwe versie wanneer deze de huidige versie moet overnemen;
6. deactiveer de voorgaande versie wanneer de nieuwe versie actief wordt;
7. laat de oude versie bestaan als rollback-/referentiepunt, tenzij bewust wordt besloten deze later op te ruimen;
8. werk de website en wijzigingshistorie bij.

### Eén actieve versie per flowfamilie

**Harde regel:** van dezelfde functionele flowfamilie mag maximaal **één versie actief** zijn.

```text
Energie Manager PV - Shadow Mode v1.3   UIT
Energie Manager PV - Shadow Mode v1.4   ACTIEF
```

Er mogen dus wel meerdere historische versies in Homey aanwezig zijn, maar nooit twee actieve versies die dezelfde functionele verantwoordelijkheid uitvoeren. Dit voorkomt dubbele triggers, dubbele GitHub-writes en conflicterende apparaatbesturing.

Een tijdelijke parallelle test is alleen toegestaan wanneer die expliciet als **andere functie/shadowtest** is ontworpen en geen tweede actieve versie van dezelfde functionele verantwoordelijkheid vormt.

### Overgang voor bestaande ongenummerde flows

Flows die op het moment van invoering nog geen versienummer in hun naam hebben, hoeven niet uitsluitend voor de naamgeving opnieuw te worden aangemaakt. **Bij de eerstvolgende inhoudelijke wijziging** wordt wel een nieuwe, genummerde opvolger aangemaakt.

Wanneer de bestaande flowcode al een intern versienummer bevat, wordt dat als uitgangspunt gebruikt voor de eerstvolgende flownaam. Als geen betrouwbare bestaande versie beschikbaar is, start de nieuwe opvolger bij `v1.0`.

### Websiteweergave

De website toont bij iedere flowbeschrijving voortaan:

- de exacte actuele actieve flownaam inclusief versie;
- de huidige status;
- indien relevant de directe voorganger;
- welke versie de documentatie beschrijft;
- de wijziging waarmee deze versie is ontstaan.

Homepage-links wijzen altijd naar de functionele flowbeschrijving; die pagina vermeldt welke Homey-versie op dat moment actief is.

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

De namen in deze tabel beschrijven de **huidige bestaande situatie bij invoering van de versioneringsregel**. Zodra één van deze flows inhoudelijk wordt aangepast, wordt de wijziging als nieuwe genummerde flowversie uitgevoerd.

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
