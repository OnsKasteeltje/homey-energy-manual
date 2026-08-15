# Architectuuroverzicht

Deze pagina beschrijft de huidige en geplande Homey-energiearchitectuur als één samenhangend regelsysteem.

De architectuur kent bewust twee verschillende lagen:

```text
                 BESTURING / ORCHESTRATIE

                    ENERGY MANAGER
                       Homey
                    /          \
                   ▼            ▼
                Tesla         Boiler

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

De fasemeting wordt gebruikt voor analyse, fase-identificatie en later voor veilige actieve orchestratie.

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

De huidige centrale Energy Manager draait nog in **shadow mode**. Hij berekent en logt beslissingen, maar neemt de centrale fysieke aansturing nog niet over.

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

Tesla krijgt daarom alleen flexprioriteit wanneer voldoende vermogen beschikbaar is.

### Boiler

De boiler vraagt circa 1,95–2,0 kW en kan daardoor kleiner PV-overschot benutten dan de Tesla.

### Restenergie

Wat na huishoudelijk verbruik, Tesla en boiler resteert, wordt teruggeleverd.

---

## 4. Veiligheids- en regelhiërarchie

De Energy Manager is **niet de hoogste regelautoriteit**. Lokale veiligheids- en hardwarelagen krijgen altijd voorrang.

De doelhiërarchie is:

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

Voorbeeld:

```text
Tesla laadt op Homey-doel 10 A
        ↓
oven of andere grote verbruiker gaat aan
        ↓
Easee Equalizer verlaagt naar 6 A of pauzeert
        ↓
Homey accepteert de werkelijke laadstroom
        ↓
geen directe poging om opnieuw 10 A af te dwingen
```

### Gevraagd versus werkelijk Tesla-vermogen

De actieve orchestratie moet altijd onderscheid maken tussen:

- door Homey **gevraagde** laadstroom;
- door Easee **werkelijk geleverde** laadstroom/vermogen.

Nieuwe beslissingen worden genomen op basis van de werkelijke toestand: Tesla-vermogen, P1 en L1/L2/L3.

### Geen directe herverdeling na Equalizer-ingreep

Wanneer de Equalizer Tesla terugregelt, wordt het ogenschijnlijk vrijgekomen vermogen niet automatisch direct aan de boiler toegewezen. Eerst worden net- en fasebelasting opnieuw beoordeeld.

### Stabilisatie / hysterese

Na onverwacht terugregelen of pauzeren door Easee wordt in de toekomstige actieve regeling een korte stabilisatieperiode gebruikt voordat vermogen opnieuw wordt toegewezen. Richtwaarde: **1–2 minuten**. De definitieve waarde wordt vóór activering in shadow mode gevalideerd.

Doel: voorkomen dat Easee en Homey tegen elkaar in gaan regelen.

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
- bestaande Tesla-flows;
- centrale Energy Manager.

Monitoring gebruikt de werkelijke laadstatus en het werkelijke vermogen. De Energy Manager mag nooit alleen op een laadsetpoint vertrouwen wanneer de Equalizer lokaal heeft teruggestuurd.

Per laadsessie kunnen onder andere starttijd, eindtijd, duur, geladen kWh, gemiddeld en maximaal vermogen worden vastgelegd.

---

## 9. Shadow versus actief

### Actief

Bestaande regelingen sturen werkelijk apparaten, zoals delen van warmwater-, Tesla- en Quookerlogica.

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

De nieuwe Equalizer-/faseveiligheidsregels worden eerst in shadow mode gevalideerd voordat ze onderdeel worden van actieve orchestratie.

---

## 10. Constraints-overzicht

| Constraint | Effect |
|---|---|
| Installatieveiligheid / 3×25 A | absolute bovengrens |
| Easee Equalizer | lokale load balancing heeft voorrang op Homey |
| Werkelijk Tesla-vermogen | leidend boven gevraagd setpoint |
| L1/L2/L3-fasebelasting | meewegen vóór nieuwe flexbeslissing |
| Equalizer-ingreep | geen directe herverdeling naar boiler |
| Stabilisatie na terugregelen | richtwaarde 1–2 min; nog te valideren |
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
| Flowversionering | per flowfamilie maximaal één actieve versie |

---

## 11. Doelarchitectuur met veiligheidslagen

```text
                 BESTURING

             ┌──────────────────┐
             │  ENERGY MANAGER  │
             │      Homey       │
             └───────┬──────────┘
                     │ gewenste laadstroom
                     ▼
              ┌─────────────┐
              │ Easee       │
              │ Charger     │
              └──────┬──────┘
                     │
        ┌────────────▼────────────┐
        │ Easee Equalizer        │
        │ lokale load balancing  │
        └────────────┬────────────┘
                     │ werkelijk vermogen
                     ▼
                   Tesla

                 ENERGIE

PV ─────────► HUISBUS ◄────────► GRID
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
     Huis     Tesla    Boiler
```

De Energy Manager beslist over comfort en flexibiliteit. De Equalizer bewaakt lokaal de laadruimte. Geen hogere softwaredoelstelling mag een lokale veiligheidsbegrenzing terugdraaien.

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

---

## 14. Ontwerpprincipes

De architectuur volgt deze principes:

- meten vóór sturen;
- installatieveiligheid vóór optimalisatie;
- lokale hardwarebeveiliging nooit overrulen;
- werkelijk vermogen boven gevraagd vermogen;
- centrale P1 plus L1/L2/L3 als waarheid voor net- en fasebelasting;
- na veiligheidsingrepen eerst stabiliseren, daarna opnieuw beslissen;
- Tesla vóór boiler binnen de beschikbare veilige flexruimte;
- Quooker als constraint;
- fail-safe boven agressieve optimalisatie;
- eerst shadow mode, daarna gecontroleerde migratie;
- Homey zo licht mogelijk houden; analyse/historie/visualisatie zoveel mogelijk buiten Homey;
- iedere inhoudelijke flowwijziging maakt een nieuwe genummerde flowversie;
- alle relevante wijzigingen tegelijk vastleggen in Flow Manual en wijzigingshistorie.
