# Warm water optimalisatie — PV boiler + CV advies

**Status:** 🟢 Actief  
**Actieve flow:** `Warm water optimalisatie - PV boiler + CV advies v1.3`

De flow draait iedere 5 minuten en stuurt de elektrische boiler aan; de CV-omschakeling blijft handmatig.

## 1. Doel en uitgangspunt

De warmwaterregeling combineert twee warmtebronnen:

| Onderdeel | Uitgangspunt |
|---|---|
| Elektrische boiler | **Stiebel Eltron HSTP 200**, 200 liter |
| Gemeten boilervermogen tijdens werkelijk verwarmen | circa **1,95–2,0 kW** |
| CV-ketel | **Vaillant ecoTEC exclusive** |
| PV-meetbasis | netto P1-import/-export van de gehele woning |
| CV ↔ boiler omschakeling | **handmatig** |

De elektrische boiler wordt automatisch aan/uit gestuurd. De Vaillant CV-ketel wordt niet automatisch omgeschakeld. Homey geeft alleen advies over de gewenste warmwaterbron.

## 2. Actieve regeling v1.3

Vanaf **16 augustus 2026** is `Warm water optimalisatie - PV boiler + CV advies v1.3` de actieve productieflow.

De belangrijkste wijziging ten opzichte van v1.2/v1.1 is dat **OP_TEMPERATUUR nu het primaire dagelijkse comfortdoel is**. De oude regel van 240 minuten ingeschakelde boilertijd blijft alleen bestaan als fallback zolang OP_TEMPERATUUR die dag niet betrouwbaar is bevestigd.

Een PV-start is mogelijk wanneer:

- `WW_Boilermodus = JA`;
- het tijdstip tussen **09:30 en 18:30** ligt;
- gedurende minimaal 5 minuten ongeveer **2,1 kW netto P1-export** beschikbaar is.

Na inschakelen geldt een minimumlooptijd van ongeveer **30 minuten**. Daarna mag de boiler bij ongunstige omstandigheden tijdelijk worden gestopt wanneer gedurende circa **10 minuten meer dan 0,5 kW netto uit het net wordt afgenomen**, zolang het dagdoel nog veilig kan worden gehaald.

Om **19:00** eindigt de dagelijkse regelperiode.

## 3. Primair dagdoel: OP_TEMPERATUUR

Het dagdoel in boilermodus is nu:

> **De boiler moet aantoonbaar OP_TEMPERATUUR bereiken.**

De detectie is gevalideerd met de volgende state-machine:

```text
VERWARMEN
   ↓
AFKOELEN_WACHT
   ↓ 10 minuten continu < 100 W
OP_TEMPERATUUR
```

Detectieregels:

- **VERWARMEN:** boilervermogen > **1,5 kW**;
- de verwarmfase moet minimaal **15 minuten** bevestigd zijn;
- daarna start bij < **100 W** de status `AFKOELEN_WACHT`;
- blijft het vermogen **10 minuten continu <100 W** terwijl de boiler Homey-technisch AAN blijft, dan wordt `OP_TEMPERATUUR` bevestigd;
- stijgt het vermogen tijdens de wachttijd weer, dan vervalt de bevestiging.

Zodra `OP_TEMPERATUUR` die dag is bevestigd:

- geldt het warmwaterdoel als gehaald;
- wordt eventuele 240-minuten-catch-up direct beëindigd;
- wordt geen verdere boilertijd geforceerd om alsnog 4 uur te halen;
- de boiler mag worden uitgeschakeld door de warmwaterflow.

## 4. 240 minuten is alleen fallback

De oude 240-minutenregel blijft bewust behouden als veiligheidsnet voor situaties waarin de thermostaat-afslag niet betrouwbaar wordt waargenomen.

Zolang `OP_TEMPERATUUR` **niet** is bevestigd, bewaakt v1.3:

- hoeveel boilertijd die dag al beschikbaar was;
- hoeveel minuten nog ontbreken tot 240 minuten;
- hoeveel tijd resteert tot 19:00.

Wanneer verder uitstellen betekent dat 240 minuten vóór 19:00 niet meer haalbaar zijn, start de catch-up. Deze fallback mag zo nodig netstroom gebruiken om comfort te borgen.

Conceptueel:

```text
boilermodus = JA
      │
      ├─ OP_TEMPERATUUR vandaag bereikt?
      │       ├─ JA → dagdoel gehaald; geen 240-minuten-catch-up
      │       └─ NEE
      │            ├─ voldoende tijd → zoveel mogelijk PV-optimaliseren
      │            └─ deadline nadert → 240 minuten als fallback veiligstellen
      │
      └─ 19:00 einde dagelijkse regelperiode
```

## 5. Gevalideerde boilercyclus

De praktijktest van **15 op 16 augustus 2026** heeft de volledige keten end-to-end gevalideerd en persistent opgeslagen in `docs/data/boiler-cycles.json`.

| Kenmerk | Waarde |
|---|---:|
| Start | **15-08-2026 23:06** |
| Einde | **16-08-2026 00:15** |
| Duur | **69 minuten** |
| Eindreden | `OP_TEMPERATUUR` |
| Geschat boilerverbruik | **1,856 kWh** |
| `reached_temperature` | **true** |

Op **16 augustus 2026 om 10:46 lokaal** registreerde Shadow v1.6.6 opnieuw een geldige OP_TEMPERATUUR-cyclus. Daarom bevat v1.3 voor de migratiedag een eenmalige bootstrap: het dagdoel van 16 augustus wordt als reeds gehaald beschouwd, zodat de nieuwe flow niet alsnog onnodige catch-up activeert.

## 6. Samenwerking met Tesla

De centrale PV-prioriteit blijft:

```text
1. Huishoudelijk verbruik
          ↓
2. Tesla
          ↓
3. Boiler
          ↓
4. Teruglevering
```

Tesla houdt dus normaal prioriteit boven de boiler. De boiler kan vooral PV-overschot benutten dat niet nodig is voor Tesla of te klein is voor zinvol 3-fase Tesla-laden.

De boilerfallback doorbreekt die economische prioriteit alleen wanneer `OP_TEMPERATUUR` nog niet is bereikt en de comfortdeadline anders in gevaar komt.

## 7. Energy Manager en M7

De warmwaterregeling werkt samen met de centrale observatie- en beslislaag:

- `Energie Manager PV - Shadow Mode v1.6.6` publiceert de actuele energiebalans en semantische boilerstatus;
- `M7 - Opportunity Score - Shadow v1.3` gebruikt die semantische status voor prijs/PV-beslissingen;
- `OP_TEMPERATUUR` is in M7 geen start- of uitstelkandidaat;
- `AFKOELEN_WACHT` blijft conservatief geen kandidaat;
- `VERWARMEN` kan een uitstelbare belasting zijn bij dure netimport;
- `UIT` kan een startkandidaat zijn bij gunstige omstandigheden.

## 8. `WW_Boilermodus`

De fysieke omschakeling tussen CV en elektrische boiler blijft handmatig.

| `WW_Boilermodus` | Betekenis |
|---|---|
| **JA** | warm tapwater via elektrische boiler |
| **NEE** | warm tapwater via Vaillant CV |

In CV-modus houdt de warmwaterflow de elektrische boiler uit.

## 9. Fail-safe en veiligheid

De regeling blijft conservatief:

- in CV-modus blijft de elektrische boiler uit;
- Homey schakelt de Vaillant CV niet automatisch om;
- ontbrekende kritieke meetdata leiden tot stoppen in plaats van gokken;
- minimumlooptijden en hold-tijden voorkomen onrustig schakelen;
- maximaal één warmwaterproductieversie is actief;
- legacy- en testversies blijven uit;
- de tijdelijke omschakelflow voor v1.2 → v1.3 is na succesvolle migratie uitgeschakeld;
- de handmatige start van v1.3 is uitsluitend read-only diagnostiek en stuurt geen apparaten.

## 10. Actuele status

| Onderdeel | Status |
|---|---|
| Warm water optimalisatie | 🟢 **v1.3 actief** |
| Primair dagdoel | ✅ **OP_TEMPERATUUR** |
| OP_TEMPERATUUR-detectie | ✅ >1500 W ≥15 min, daarna <100 W ≥10 min terwijl AAN |
| 240 minuten | 🟡 alleen fallback zolang OP_TEMPERATUUR niet bevestigd is |
| Nieuwe PV-start mogelijk | **09:30–18:30** |
| Einde dagelijkse regelperiode | **19:00** |
| Boiler Homey on/off write | ✅ gevalideerd |
| Volledige boilercyclusregistratie | ✅ gevalideerd in `boiler-cycles.json` |
| Energy Manager | 🟢 Shadow v1.6.6 actief |
| M7 Opportunity Score | 🟢 v1.3 shadow met semantische boilerstatus |
| CV ↔ boiler omschakeling | handmatig |

## 11. Wijzigingshistorie

### v1.3 — 16 augustus 2026

- `OP_TEMPERATUUR` is het primaire dagelijkse boilerdoel geworden.
- Detectie gebruikt >1500 W gedurende minimaal 15 minuten en daarna <100 W gedurende minimaal 10 minuten terwijl de boiler AAN blijft.
- Na bevestigd `OP_TEMPERATUUR` wordt geen verdere catch-up naar 240 minuten uitgevoerd.
- 240 minuten blijft beschikbaar als fallback wanneer thermostaat-afslag niet betrouwbaar wordt bevestigd.
- PV-startvenster loopt tot 18:30; dagelijkse regelperiode eindigt om 19:00.
- Migratiedag 16-08-2026 gebruikt een eenmalige bootstrap op basis van de reeds door Shadow v1.6.6 vastgelegde geldige cyclus om 10:46 lokaal.
- Handmatige start van de flow is read-only diagnostiek.
- v1.2 nacht-test en de oude ongenummerde v1.1 zijn uitgeschakeld; slechts één warmwaterproductieversie is actief.
