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

## 4. Boiler aan betekent niet automatisch werkelijk verwarmen

Onze Homey-write-test heeft bevestigd dat de boiler vanuit Homey betrouwbaar **aan/uit** kan worden gezet. Tegelijk zagen we een belangrijk verschil tussen schakelstatus en werkelijk elektrisch vermogen:

- `onoff = true` kan betekenen dat de boiler beschikbaar/ingeschakeld is;
- het gemeten vermogen kan toch **0 W** zijn wanneer het interne thermostaat/contact geen warmte meer vraagt;
- tijdens werkelijk opwarmen verwachten we ongeveer **1,95–2,0 kW**.

Dit onderscheid wordt voortaan expliciet gebruikt in de analyse. Alleen naar `onoff` kijken is onvoldoende om vast te stellen of de boiler nog energie nodig heeft.

Een belangrijk toekomstig afgeleid signaal wordt daarom:

```text
boiler ingeschakeld + vermogen ~0 W
        → waarschijnlijk op temperatuur / geen actuele warmtevraag
```

Dit moet nog verder worden gevalideerd met langere meetreeksen voordat het als harde regel wordt gebruikt.

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

### Baseline v0.1

`Energie Manager PV - Shadow Mode` simuleert de bestaande PV-prioritering en schrijft geen apparaten aan.

### Shadow v0.2 + Quooker

`Energie Manager PV - Shadow Mode v0.2 Quooker` voegt Quookerstatus en bestaande Quooker-tijdvensters toe aan de context, nog steeds zonder apparaten vanuit de shadowflow te sturen.

### M7 Opportunity Shadow

`M7 - Opportunity Score - Shadow` voegt prijs- en PV-forecastcontext toe en berekent per kwartier een Opportunity Score, advies, kandidaat en reden. Deze dataset blijft volledig gescheiden van de baseline.

Het doel is eerst aantonen dat de nieuwere logica betere keuzes zou maken voordat zij de actieve warmwaterflow mag vervangen of overrulen.

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
- de 4-uursvoorwaarde vóór 19:00 wordt eerst gecontroleerd in shadowlogica voordat actieve orchestratie wordt aangepast.

## 13. Actuele status

| Onderdeel | Status |
|---|---|
| Warm water optimalisatie | 🟢 **Actief** |
| `WW_Boilermodus` | actief als bronkeuze |
| Boiler Homey on/off write | ✅ gevalideerd |
| Boiler werkelijk vermogen na inschakelen | 🟡 verder valideren; 0 W kan optreden ondanks `onoff=true` |
| Huidige startvenster | **09:30–14:30** |
| Huidig hard einde | **15:30** |
| Minimale boilertijd in boilermodus | **4 uur/dag** |
| Deadline minimale boilertijd | **19:00** |
| Baseline Energy Manager | 🟡 Shadow |
| Shadow v0.2 + Quooker | 🟡 gereed voor overgang na baseline |
| M7 prijs/PV-context | 🟡 read-only/shadow |
| M7 Opportunity Score | 🟡 parallelle shadowanalyse |
| Quookerregeling | bestaande Homey-flows blijven leidend |
| Victron ESS | toekomstig; nog niet geïnstalleerd |
| CV ↔ boiler omschakeling | handmatig |

## 14. Volgende optimalisatiestap

Na voldoende shadowdata vergelijken we drie dingen:

1. wat de huidige actieve warmwaterregeling werkelijk deed;
2. wat de Energy Manager baseline/v0.2 zou hebben gedaan;
3. wat M7 met prijs- en PV-forecast zou hebben geadviseerd.

Pas daarna wordt besloten hoe de actieve warmwaterflow wordt aangepast. De eerste harde ontwerpvoorwaarde voor die toekomstige versie is al duidelijk: **in boilermodus moet de 4-uurswarmwaterconstraint uiterlijk om 19:00 gegarandeerd zijn**.
