# Architectuuroverzicht

Deze pagina beschrijft de huidige en geplande Homey-energiearchitectuur als één samenhangend regelsysteem.

De architectuur kent bewust verschillende lagen:

```text
                  METEN / CONTEXT

Homey devices + Logic + M7 context
              ↓
Energy Manager State Collector v1.0
              ↓
        EM_Runtime_State

              ORCHESTRATIE

            ENERGY MANAGER
                 Homey
        ┌────────┼────────┐
        ▼        ▼        ▼
     Shadow   Allocator  Tesla v2.6

            FYSIEKE ENERGIESTROOM

 PV-bronnen ───► HUISBUS ◄────► GRID / P1
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
     Huishouden   Tesla     Boiler
```

De **Energy Manager ligt niet in het elektrische stroompad**. Hij observeert, beslist en stuurt flexibele verbruikers. De fysieke energiestroom loopt via de elektrische installatie.

De **Quooker** valt niet simpelweg in de flexprioriteitsketen. Die heeft eigen gebruiksvensters en wordt als constraint behandeld.

---

## 1. Bronnen en meetlaag

### PV-bronnen

De woning heeft drie afzonderlijke PV-omvormers:

- SolarEdge SE3680H;
- GoodWe GW4200D-NS;
- GoodWe GW2000-XS.

Voor de centrale regeling is de **P1-meter leidend** voor de netto huisbalans. Daarnaast worden L1, L2 en L3 afzonderlijk gemonitord.

```text
P1 < 0 W  → netto teruglevering
P1 > 0 W  → netto afname
```

### Centrale runtime-state

Vanaf 16 augustus 2026 draait `Energy Manager State Collector v1.0` iedere twee minuten. Deze flow leest in één HomeyScript-run de relevante devices en Logic-variabelen en bouwt:

```text
EM_Runtime_State
```

De centrale snapshot bevat onder andere:

- P1 totaal en L1/L2/L3;
- Tesla/Easee vermogen, laadstatus, setpoint en meterstand;
- Equalizer-fasestromen;
- boilervermogen en aan/uit-status;
- PV-productie per omvormer;
- wasmachine- en drogerstatus;
- warmwater-, deadline- en M7-context.

Niet iedere flow hoeft hierdoor opnieuw alle apparaten op te vragen.

---

## 2. Centrale beslislaag

De centrale Energy Manager combineert onder andere:

- P1-netvermogen;
- L1/L2/L3-fasebelasting;
- Tesla/Easee laadstatus en werkelijk vermogen;
- boilervermogen en semantische boilerstatus;
- Quooker-status;
- tijdvensters;
- seizoensmodus;
- prijs-/PV-forecastcontext.

De centrale Energy Manager draait nog in **shadow mode**. Hij berekent en logt beslissingen, maar neemt de centrale fysieke aansturing nog niet volledig over.

Actuele shadowlagen zijn:

- `Energie Manager PV - Shadow Mode v1.6.7` — iedere 5 minuten;
- `Energy Manager Allocator - Shadow v0.2.4` — iedere 5 minuten, vanuit `EM_Runtime_State`.

De operationele Tesla-aansturing blijft bij `Tesla laden v2.6`.

---

## 3. Prioriteitsmodel voor flexibele energie

De gewenste energietoewijzing is:

```text
1. Normaal huishoudelijk verbruik
2. Tesla
3. Boiler
4. Teruglevering
```

### Tesla

De minimale zinvolle 3-fase laadstroom is:

```text
3 × 6 A ≈ 4,14 kW
```

Tesla krijgt daarom alleen flexprioriteit wanneer voldoende vermogen beschikbaar is, tenzij een deadline catch-up vereist.

### Boiler

De boiler vraagt circa 1,95–2,0 kW en kan daardoor kleiner PV-overschot benutten dan de Tesla.

### Restenergie

Wat na huishoudelijk verbruik, Tesla en boiler resteert, wordt teruggeleverd.

---

## 4. Veiligheids- en regelhiërarchie

De Energy Manager is **niet de hoogste regelautoriteit**. Lokale veiligheids- en hardwarelagen krijgen altijd voorrang.

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer load balancing
          ↓
Victron grid/batterijregeling (later)
          ↓
Homey Energy Manager / flex-orchestratie
          ↓
Tesla / boiler
```

### Easee Equalizer is leidend voor laadveiligheid

De Easee Equalizer mag autonoom de Tesla-laadstroom verlagen of het laden pauzeren wanneer de totale of fasebelasting dit vereist. Homey probeert zo'n ingreep **nooit te overrulen**.

### Gevraagd versus werkelijk Tesla-vermogen

De actieve orchestratie onderscheidt altijd:

- door Homey **gevraagde** laadstroom;
- door Easee **werkelijk geleverde** laadstroom/vermogen.

Vanaf `Tesla laden v2.6` wordt 0 W bij een actief laadverzoek niet automatisch aan de Equalizer toegeschreven. Alleen wanneer tegelijkertijd voldoende hoge Equalizer-fasebelasting wordt gemeten, wordt de oorzaak specifiek als Equalizer-blokkade geclassificeerd.

### Geen directe herverdeling na Equalizer-ingreep

Wanneer de Equalizer Tesla terugregelt, wordt het ogenschijnlijk vrijgekomen vermogen niet automatisch direct aan de boiler toegewezen. Eerst worden net- en fasebelasting opnieuw beoordeeld.

---

## 5. Quooker als constraint

De Quooker is geen vrij regelbare flex-load. Bestaande vensters blijven leidend zolang de centrale Energy Manager in shadow mode draait.

| Dagtype | Toegestaan venster |
|---|---|
| Werkdagen | **15:00–19:00** |
| Weekend | **08:00–19:00** |

Binnen het venster is Quooker `TOEGESTAAN`; daarbuiten `BUITEN_VENSTER`.

---

## 6. Warmwaterarchitectuur

Er zijn twee warmwaterbronnen:

```text
Elektrische boiler  ←→  handmatige omschakeling  ←→  Vaillant CV
```

Homey regelt alleen de elektrische boiler automatisch. De fysieke omschakeling blijft handmatig.

### `WW_Boilermodus`

| Waarde | Betekenis |
|---|---|
| JA | elektrische boiler actief |
| NEE | CV actief |

De boilerobserver gebruikt de gevalideerde keten:

```text
VERWARMEN → AFKOELEN_WACHT → OP_TEMPERATUUR
```

---

## 7. Seizoensbeslissing

Homey beoordeelt zeven volledige meetdagen.

Voor 2026:

```text
≤ 3 goede PV-dagen → advies naar CV
≥ 5 goede PV-dagen → advies naar boiler
```

De tussenruimte voorkomt pendelen. De melding vereist handmatige fysieke omschakeling.

---

## 8. Tesla-laadarchitectuur

De Tesla-laag bestaat uit:

- Easee Charger;
- Easee Equalizer;
- Tesla Model 3;
- `Tesla laden v2.6`;
- M7 prijs-/PV-context;
- centrale Energy Manager.

`Tesla laden v2.6` is de enige automatische schrijver van de dynamische Easee-laadstroom en evalueert iedere twee minuten.

Monitoring gebruikt de werkelijke laadstatus en het werkelijke vermogen. De Energy Manager mag nooit alleen op een laadsetpoint vertrouwen wanneer de Equalizer lokaal heeft teruggestuurd.

---

## 9. Shadow versus actief

### Actief

Bestaande regelingen sturen werkelijk apparaten, zoals delen van warmwaterlogica en `Tesla laden v2.6`.

### Shadow

De centrale Energy Manager:

- leest;
- berekent;
- logt;
- vergelijkt;
- stuurt nog niet centraal.

Doel:

```text
werkelijk gedrag
      versus
gesimuleerde centrale beslissing
```

### Actuele shadow cadence

`Energie Manager PV - Shadow Mode v1.6.7` draait één keer per **5 minuten**. De oude combinatie van een 2-minutentrigger plus aparte 15-minutentrigger is verwijderd. GitHub-publicatie wordt intern nog ongeveer iedere 15 minuten bepaald.

`Energy Manager Allocator - Shadow v0.2.4` draait eveneens iedere **5 minuten** en gebruikt de centrale `EM_Runtime_State` in plaats van opnieuw alle devices op te halen.

---

## 10. Publicatie- en observatielaag

De websitepublicatie is bewust uit de kritische regelroute gehouden.

```text
EM_Runtime_State
   └─→ Live energie publicatie v1.2 → GitHub → website

Shadow v1.6.7
   └─→ shadowhistorie → GitHub

GitHub status sync v1.4
   └─→ flowstatus → GitHub
```

Actuele cadans:

| Functie | Ritme |
|---|---:|
| State Collector v1.0 | 2 min |
| Tesla laden v2.6 | 2 min |
| Shadow v1.6.7 | 5 min |
| Allocator Shadow v0.2.4 | 5 min |
| Live energie v1.2 | 5 min |
| M7 context | 15 min |
| GitHub status sync v1.4 | 30 min |

Deze indeling verlaagt Homey-load door **één keer meten, meerdere keren gebruiken**.

---

## 11. Constraints-overzicht

| Constraint | Effect |
|---|---|
| Installatieveiligheid / 3×25 A | absolute bovengrens |
| Easee Equalizer | lokale load balancing heeft voorrang op Homey |
| Werkelijk Tesla-vermogen | leidend boven gevraagd setpoint |
| L1/L2/L3-fasebelasting | meewegen vóór nieuwe flexbeslissing |
| Equalizer-ingreep | geen directe herverdeling naar boiler |
| Tesla minimaal 3×6 A | onder ca. 4,14 kW geen zinvolle laadstart |
| Boiler circa 2 kW | benut kleiner PV-overschot |
| Quooker werkdagen | 15:00–19:00 |
| Quooker weekend | 08:00–19:00 |
| CV ↔ boiler | handmatige omschakeling |
| `WW_Boilermodus` | bepaalt logische warmwaterbron |
| 7-daagse hysterese | voorkomt veelvuldig omschakelen |
| Shadow mode | centrale manager stuurt nog geen apparaten |
| P1 beschikbaarheid | zonder P1 geen centrale vermogensbeslissing |
| Device beschikbaarheid | ontbrekend apparaat → fail-safe |
| Runtime-state ouder dan 5 min | allocator weigert state fail-safe |
| Flowversionering | per flowfamilie maximaal één actieve versie |

---

## 12. Toekomstige Victron-laag

De geplande Victron-architectuur voegt later toe:

- MultiPlus-II 5000;
- Cerbo GX;
- VM/3P75CT;
- thuisbatterij;
- Victron EMS.

Rolverdeling:

```text
Victron EMS
  └─ batterij / net / energie-optimalisatie

Easee Equalizer
  └─ lokale EV-load balancing / installatiebescherming

Homey
  └─ huishoudelijke flexibiliteit en orchestratie
       ├─ Tesla-doel
       ├─ boiler
       ├─ Quooker constraints
       └─ gebruikersmeldingen
```

Homey blijft comfort- en verbruikersorchestrator. Victron wordt primaire batterij-/netlaag. Easee Equalizer blijft autonoom voor veilige EV-load balancing.

---

## 13. Flowversionering en wijzigingsbeheer

Voor iedere Homey-flowfamilie geldt:

```text
inhoudelijke wijziging
      ↓
nieuwe flow met hoger versienummer
      ↓
validatie
      ↓
nieuwe versie actief
oude versie inactief
```

Van dezelfde functionele flowfamilie mag maximaal één versie actief zijn. Websitebeschrijving en wijzigingshistorie worden tegelijk bijgewerkt.

De load-optimalisatie van 16 augustus 2026 heeft onder andere geleid tot:

```text
Shadow v1.6.6           → v1.6.7
Allocator v0.2.3        → v0.2.4
Live energie v1.1       → v1.2
GitHub status sync v1.3 → v1.4
+ State Collector v1.0
```

---

## 14. Ontwerpprincipes

De architectuur volgt deze principes:

- meten vóór sturen;
- installatieveiligheid vóór optimalisatie;
- lokale hardwarebeveiliging nooit overrulen;
- werkelijk vermogen boven gevraagd vermogen;
- centrale P1 plus L1/L2/L3 als waarheid voor net- en fasebelasting;
- Tesla vóór boiler binnen de beschikbare veilige flexruimte;
- Quooker als constraint;
- fail-safe boven agressieve optimalisatie;
- eerst shadow mode, daarna gecontroleerde migratie;
- **één keer meten, meerdere keren gebruiken** waar dat veilig kan;
- veiligheidskritische Tesla-besturing blijft rechtstreeks actuele data lezen;
- Homey zo licht mogelijk houden; analyse/historie/visualisatie zoveel mogelijk buiten Homey;
- iedere inhoudelijke flowwijziging maakt een nieuwe genummerde flowversie;
- alle relevante wijzigingen tegelijk vastleggen in Flow Manual en wijzigingshistorie.

> Laatste architectuurupdate: **16 augustus 2026** — centrale runtime-state en Homey-loadoptimalisatie geïntegreerd.
