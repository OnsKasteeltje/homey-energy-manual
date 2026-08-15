# Warm water optimalisatie — PV boiler + CV advies

**Status:** 🟢 Actief  
**Flow:** `Warm water optimalisatie - PV boiler + CV advies`

De flow draait iedere 5 minuten en stuurt de elektrische boiler aan; de CV-omschakeling blijft handmatig.

Deze pagina maakt onderscheid tussen de **huidige actieve warmwaterregeling**, de **harde comfortconstraint voor boilermodus** en de **geplande integratie met Energy Manager, M7, Quooker en Victron ESS**.

## 1. Doel en uitgangspunt

De warmwaterregeling combineert twee bestaande warmtebronnen:

| Onderdeel | Uitgangspunt |
|---|---|
| Elektrische boiler | **Stiebel Eltron HSTP 200**, 200 liter |
| Gemeten boilervermogen tijdens werkelijk verwarmen | circa **1,95–2,0 kW** |
| CV-ketel | **Vaillant ecoTEC exclusive** |
| PV-meetbasis | netto P1-import/-export van de gehele woning |
| CV ↔ boiler omschakeling | **handmatig** |

De elektrische boiler wordt automatisch aan/uit gestuurd. De Vaillant CV-ketel wordt **niet** automatisch omgeschakeld. Homey geeft alleen advies over de gewenste warmwaterbron.

## 2. Huidige actieve regeling

De actieve warmwaterflow gebruikt nog de bestaande PV-regeling. Een verwarmingscyclus mag starten wanneer:

- `WW_Boilermodus = JA`;
- het tijdstip binnen het huidige startvenster ligt;
- gedurende minimaal 5 minuten ongeveer **2,1 kW netto P1-export** beschikbaar is.

Na inschakelen geldt een minimumlooptijd van ongeveer **30 minuten**. Daarna mag de boiler worden uitgeschakeld wanneer gedurende circa **10 minuten meer dan 0,5 kW netto uit het net wordt afgenomen**.

De huidige actieve tijdvensters zijn nog:

| Regeling | Huidig actief |
|---|---:|
| Nieuwe start mogelijk | **09:30–14:30** |
| Hard einde | **15:30** |

!!! warning "Belangrijk"
    Deze tijden zijn de **huidige actieve implementatie**, maar ze voldoen nog niet volledig aan de inmiddels vastgestelde comfortconstraint voor boilermodus. Die constraint wordt hieronder apart beschreven en wordt eerst via shadow-validatie in de centrale orchestrator voorbereid.

## 3. Harde comfortconstraint in boilermodus

Wanneer de woning in **boilermodus** staat (`WW_Boilermodus = JA`), moet de elektrische boiler dagelijks voldoende gelegenheid krijgen om warm water te leveren.

De nieuwe harde randvoorwaarde is:

> De boiler moet per dag **minimaal 4 uur beschikbaar/ingeschakeld kunnen zijn** en deze 4 uur moeten **uiterlijk om 19:00** zijn gerealiseerd.

Deze randvoorwaarde is belangrijker dan pure PV-optimalisatie. Een dag met weinig zon mag er dus niet toe leiden dat de boiler structureel te weinig gelegenheid krijgt om op temperatuur te komen.

In CV-modus (`WW_Boilermodus = NEE`) geldt deze 4-uursvoorwaarde niet, omdat warm tapwater dan door de CV-ketel wordt geleverd.

### Gevolg voor toekomstige logica

De orchestrator moet daarom niet alleen kijken naar huidig PV-overschot, maar ook naar **resterende tijd tot 19:00** en **hoeveel boilertijd vandaag al is gehaald**.

Conceptueel:

```text
boilermodus = JA
      │
      ├─ voldoende boilertijd vóór 19:00 al gehaald?
      │       ├─ JA → flexibel optimaliseren op PV/prijs
      │       └─ NEE
      │            ├─ nog ruim tijd → zoveel mogelijk op gunstige PV/prijs
      │            └─ deadline nadert → boiler steeds hogere prioriteit geven
      │
      └─ uiterlijk 19:00 moet de minimale 4 uur zijn veiliggesteld
```

## 4. Boilerstatus en gevalideerde state-machine

De nachtelijke praktijktest van **15 op 16 augustus 2026** heeft het onderscheid tussen schakelstatus en werkelijke warmtevraag end-to-end gevalideerd.

De boiler kan in Homey `onoff = true` blijven terwijl het interne thermostaatcontact het element uitschakelt. In dat geval is de boiler elektrisch beschikbaar, maar trekt hij **0 W** omdat de ingestelde temperatuur is bereikt.

De Energy Manager gebruikt daarom vanaf **v1.6.4** een semantische boilerstatus in plaats van alleen `onoff`:

```text
VERWARMEN
   ↓
AFKOELEN_WACHT
   ↓ 10 minuten continu < 100 W
OP_TEMPERATUUR
```

De relevante detectieregels zijn:

- **VERWARMEN:** gemeten boilervermogen > **1,5 kW**;
- de verwarmfase moet eerst gedurende circa **15 minuten** bevestigd zijn;
- na bevestigd verwarmen start bij < **100 W** de fase `AFKOELEN_WACHT`;
- blijft het vermogen vervolgens **10 minuten continu <100 W**, dan wordt `OP_TEMPERATUUR` bevestigd;
- stijgt het vermogen in die wachtperiode weer, dan vervalt de bevestiging en keert de status terug naar `VERWARMEN`/wachtlogica.

Hiermee is `boiler ingeschakeld + 0 W` niet langer slechts “waarschijnlijk warm”, maar in combinatie met de vooraf bevestigde verwarmfase en de 10-minutenwachttijd een **gevalideerd OP_TEMPERATUUR-signaal**.

### Gevalideerde boilercyclus 15→16 augustus 2026

De volledige cyclus is succesvol doorlopen en persistent opgeslagen in `docs/data/boiler-cycles.json`:

| Kenmerk | Waarde |
|---|---:|
| Start | **15-08-2026 23:06** |
| Einde | **16-08-2026 00:15** |
| Duur | **69 minuten** |
| Eindreden | `OP_TEMPERATUUR` |
| Geschat boilerverbruik | **1,856 kWh** |
| `reached_temperature` | **true** |

De waargenomen keten was daarmee volledig:

**VERWARMEN → AFKOELEN_WACHT → OP_TEMPERATUUR → registratie in `boiler-cycles.json`**.

Dit is de eerste volledige end-to-end acceptatie van de boilercycluslogica.

## 5. Samenwerking met Tesla

De centrale PV-prioriteit blijft als uitgangspunt:

```text
1. Huishoudelijk verbruik
          ↓
2. Tesla
          ↓
3. Boiler
          ↓
4. Teruglevering
```

Daarbij geldt één belangrijke nuance: de boiler heeft een **comfortdeadline**. Zolang er voldoende tijd over is tot 19:00 kan Tesla voorrang krijgen. Naarmate de boiler zijn minimale 4 uur nog niet heeft gehaald en de deadline dichterbij komt, moet de boilerprioriteit toenemen.

De boiler is daarnaast nuttig voor PV-overschotten die te klein zijn voor zinvol 3-fase Tesla-laden maar wel groot genoeg zijn voor ongeveer 2 kW boilervermogen.

## 6. Rol van de Energy Manager shadowlagen

De actieve warmwaterflow wordt nu nog niet direct vervangen door de centrale orchestrator. De overgang wordt stapsgewijs voorbereid met onafhankelijke shadowlagen.

### Energy Manager v1.6.4

`Energie Manager PV - Shadow Mode v1.6.4` is de actieve semantische observatielaag. Deze flow stuurt geen apparaten aan, maar bepaalt onder meer de gevalideerde boilerstatus, volgt actieve boilercycli en publiceert baseline-, dag- en boilercyclusdata naar GitHub.

### M7 Opportunity Shadow v1.3

`M7 - Opportunity Score - Shadow v1.3` voegt prijs- en PV-forecastcontext toe en gebruikt vanaf v1.3 de **gevalideerde semantische boilerstatus** uit de Energy Manager in plaats van alleen de elektrische schakelstand.

Daarbij geldt:

- `OP_TEMPERATUUR`: geen start- of uitstelkandidaat;
- `AFKOELEN_WACHT`: geen kandidaat zolang de eindstatus nog wordt bevestigd;
- `VERWARMEN`: kan bij dure netimport als uitstelbare boilerbelasting gelden;
- `UIT`: kan bij gunstige omstandigheden als startkandidaat gelden;
- te oude of onbekende status: conservatief geen boilerkandidaat.

De directe validatie na de nachtelijke boilercyclus liet zien dat M7 v1.3 correct `OP_TEMPERATUUR` las terwijl `boilerOn=true` en het vermogen 0 W was. M7 zette daardoor `boilerCanStart=false` en `boilerCanDefer=false` en koos bij `DEFER_FLEX_LOAD` terecht kandidaat `NONE` in plaats van de reeds warme boiler.

Het doel blijft eerst aantonen dat de nieuwere logica betere keuzes maakt voordat zij de actieve warmwaterflow mag vervangen of overrulen.

## 7. Quooker als aanvullende comfortconstraint

De Quooker wordt via bestaande Homey-flows aangestuurd. Die bestaande flows en tijdvensters blijven voorlopig leidend.

De centrale orchestrator gebruikt Quooker in eerste instantie alleen als context:

- staat de Quooker aan of uit;
- bevindt het huidige tijdstip zich binnen een toegestaan Quooker-venster;
- kan flexibel vermogen beter naar Tesla, boiler, batterij of Quooker gaan zonder comfort te verstoren.

De warmwaterflow zelf verandert de Quooker-regeling niet.

## 8. M7 prijs- en PV-forecast

M7 voegt voorspellende context toe zonder apparaten aan te sturen. De huidige signalen zijn:

| Signaal | Betekenis |
|---|---|
| `priceNegative` | actuele prijs is negatief |
| `priceCheapNext4h` | nu is relatief goedkoop t.o.v. komende vier uur |
| `priceExpensiveNext4h` | nu is relatief duur t.o.v. komende vier uur |
| `pvTop4h` | huidig uur hoort tot de vier beste verwachte PV-uren tussen 09:00 en 18:00 |

Voor warm water betekent dit dat de orchestrator straks kan afwegen of de boiler beter **nu**, **later op verwachte PV** of — als de 19:00-deadline nadert — **ongeacht de forecast** moet draaien.

## 9. Toekomstige Victron ESS-integratie

De toekomstige Victron ESS-laag verandert de rolverdeling niet:

- **Homey** wordt economische/comfort-orchestrator;
- **Cerbo/Victron** blijft de snelle ESS- en batterijregelaar;
- Homey bepaalt bijvoorbeeld wanneer batterijcapaciteit strategisch moet worden benut voor PV, goedkope stroom, Tesla of warm water;
- Homey vervangt geen BMS-, ESS- of elektrische beveiligingen.

Voor de warmwaterlogica kan Victron later relevant worden wanneer goedkope netstroom of batterijcapaciteit wordt ingezet om de 19:00-warmwaterconstraint slimmer te halen.

## 10. `WW_Boilermodus`

De fysieke omschakeling tussen CV en elektrische boiler blijft handmatig.

| `WW_Boilermodus` | Betekenis |
|---|---|
| **JA** | warm tapwater via elektrische boiler |
| **NEE** | warm tapwater via Vaillant CV |

In CV-modus houdt de warmwaterflow de elektrische boiler uit. Na fysieke omschakeling moet `WW_Boilermodus` daarom ook worden bijgewerkt.

## 11. Seizoensadvies

Het bestaande seizoensadvies blijft voorlopig onderdeel van de warmwaterflow. Homey beoordeelt meerdere dagen en adviseert wanneer handmatig omschakelen tussen CV en boiler logisch is.

Dit advies wordt later opnieuw geëvalueerd zodra M7-forecastdata en de centrale orchestrator voldoende meetgeschiedenis hebben. Tot die tijd blijft de huidige advieslogica leidend.

## 12. Fail-safe en veiligheid

De regeling blijft bewust conservatief:

- in CV-modus blijft de elektrische boiler uit;
- Homey schakelt de Vaillant CV niet automatisch om;
- bij ontbrekende kritieke meetdata moet de regeling stoppen in plaats van gokken;
- minimumlooptijden en vertragingen voorkomen onrustig schakelen;
- legacy-boilerflows blijven uit om dubbele aansturing te voorkomen;
- shadowflows sturen geen apparaten aan;
- M7 gebruikt een te oude of onbekende boilerstatus niet als flexkandidaat;
- de 4-uursvoorwaarde vóór 19:00 wordt eerst gecontroleerd in shadowlogica voordat actieve orchestratie wordt aangepast.

## 13. Actuele status

| Onderdeel | Status |
|---|---|
| Warm water optimalisatie | 🟢 **Actief** |
| `WW_Boilermodus` | actief als bronkeuze |
| Boiler Homey on/off write | ✅ gevalideerd |
| Werkelijk boilervermogen tijdens verwarmen | ✅ circa 1,95–2,0 kW gevalideerd |
| Semantische boilerstatus | ✅ `VERWARMEN → AFKOELEN_WACHT → OP_TEMPERATUUR` gevalideerd |
| OP_TEMPERATUUR-bevestiging | ✅ 10 minuten continu <100 W na bevestigde verwarmfase |
| Volledige boilercyclusregistratie | ✅ gevalideerd in `boiler-cycles.json` |
| Huidige startvenster | **09:30–14:30** |
| Huidig hard einde | **15:30** |
| Minimale boilertijd in boilermodus | **4 uur/dag** |
| Deadline minimale boilertijd | **19:00** |
| Energy Manager v1.6.4 | 🟢 actieve shadowobservatie |
| M7 prijs/PV-context | 🟡 read-only/shadow |
| M7 Opportunity Score v1.3 | 🟢 actief in shadow; semantische boilerstatus geïntegreerd |
| Quookerregeling | bestaande Homey-flows blijven leidend |
| Victron ESS | toekomstig; nog niet geïnstalleerd |
| CV ↔ boiler omschakeling | handmatig |

## 14. Volgende optimalisatiestap

De belangrijke technische onzekerheid rond het herkennen van een daadwerkelijk warme boiler is hiermee weggenomen. De volgende ontwerpstap is daarom niet meer “kan Homey OP_TEMPERATUUR betrouwbaar herkennen?”, maar **hoe deze gevalideerde status samen met comfortdeadline, PV, prijs, Tesla en later Victron wordt gebruikt voor actieve orchestratie**.

Daarbij vergelijken we nog steeds:

1. wat de huidige actieve warmwaterregeling werkelijk doet;
2. wat Energy Manager v1.6.4 observeert en zou adviseren;
3. wat M7 v1.3 met prijs- en PV-forecast adviseert.

Pas daarna wordt de actieve warmwaterregeling vervangen of verder geïntegreerd in de centrale Energy Manager. De harde ontwerpvoorwaarde blijft: **in boilermodus moet de 4-uurswarmwaterconstraint uiterlijk om 19:00 gegarandeerd zijn**.
