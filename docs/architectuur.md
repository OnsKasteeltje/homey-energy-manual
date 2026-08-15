# Architectuuroverzicht

Deze pagina beschrijft de huidige en geplande Homey-energiearchitectuur als één samenhangend regelsysteem.

De centrale gedachte is:

```text
                ┌─────────────────────┐
                │    PV-productie     │
                │ SE + GoodWe + GW2000│
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │      P1-meter       │
                │ netto import/export │
                └─────────┬───────────┘
                          │
                          ▼
               ┌───────────────────────┐
               │   Energie Manager     │
               │    Homey / EMS        │
               └───────┬───────┬───────┘
                       │       │
            ┌──────────┘       └───────────┐
            ▼                              ▼
      ┌────────────┐                 ┌────────────┐
      │   Tesla    │                 │   Boiler   │
      │   Easee    │                 │ HSTP 200   │
      └────────────┘                 └────────────┘
            │                              │
            └──────────┬───────────────────┘
                       ▼
                ┌─────────────┐
                │ Teruglevering│
                └─────────────┘
```

De **Quooker** valt bewust niet simpelweg in deze prioriteitsketen. Die heeft eigen gebruiksvensters en wordt daarom als **constraint** behandeld.

---

## 1. Bronnen en meetlaag

### PV-bronnen

De woning heeft drie afzonderlijke PV-omvormers:

- SolarEdge SE3680H;
- GoodWe GW4200D-NS;
- GoodWe GW2000-XS.

Voor de centrale regeling is de **P1-meter leidend**. Daarmee wordt het werkelijke netto saldo van de woning gebruikt, ongeacht welke omvormer op dat moment produceert.

### P1-meter

De P1-meter levert:

- netto import/export;
- faseverdeling;
- cumulatief verbruik;
- cumulatieve teruglevering.

Voor de huidige Homey-regeling wordt vooral het actuele netto vermogen gebruikt.

```text
P1 < 0 W  → netto teruglevering
P1 > 0 W  → netto afname
```

---

## 2. Centrale beslislaag

De centrale Energie Manager combineert:

- P1-netvermogen;
- Tesla/Easee laadstatus en vermogen;
- boilervermogen;
- Quooker-status;
- tijdvensters;
- seizoensmodus;
- toekomstige prijs-/contractregels.

De huidige nieuwe versie draait eerst in **shadow mode**. Hij berekent beslissingen en logt ze, maar stuurt de grote verbruikers nog niet centraal aan.

---

## 3. Prioriteitsmodel

De gewenste flexibele-verbruikersprioriteit is:

```text
1. Normaal huishoudelijk verbruik
2. Tesla
3. Boiler
4. Teruglevering
```

Dit betekent niet dat Tesla altijd stroom krijgt. De Tesla moet voldoende vermogen kunnen krijgen om zinvol te laden.

### Tesla

Minimale 3-fase laadstroom:

```text
3 × 6 A ≈ 4,14 kW
```

Daarom krijgt Tesla alleen prioriteit wanneer voldoende vermogen beschikbaar is.

### Boiler

De boiler vraagt circa:

```text
1,95–2,0 kW
```

Daardoor kan de boiler PV benutten in situaties waar te weinig vermogen beschikbaar is voor Tesla.

### Restenergie

Wat daarna overblijft, wordt teruggeleverd.

---

## 4. Quooker als constraint

De Quooker wordt **niet** behandeld als vrij regelbare flexibele belasting.

Reden:

- warmwatercomfort heeft directe gebruiksimpact;
- de bestaande Quooker-flows hebben functionele tijdvensters;
- het verbruik is relatief klein ten opzichte van Tesla en boiler;
- de Quooker mag de centrale prioriteitslogica niet onverwacht verstoren.

Daarom is Quooker een **constraint**:

```text
Energie Manager
    │
    ├─ leest Quooker-status
    ├─ respecteert bestaand tijdvenster
    └─ stuurt Quooker voorlopig niet centraal aan
```

### Huidige Quooker-vensters

| Dagtype | Toegestaan venster |
|---|---|
| Werkdagen | **15:00–19:00** |
| Weekend | **08:00–19:00** |

Buiten dit venster wordt Quooker in de Energie Manager gemarkeerd als **BUITEN_VENSTER**.

Binnen het venster als **TOEGESTAAN**.

De bestaande Quooker-flows blijven leidend zolang de centrale Energie Manager nog in shadow mode is.

---

## 5. Warmwaterarchitectuur

Er zijn twee warmwaterbronnen:

```text
Elektrische boiler  ←→  handmatige omschakeling  ←→  Vaillant CV
```

Homey regelt alleen de elektrische boiler automatisch.

De fysieke omschakeling naar CV blijft handmatig.

### `WW_Boilermodus`

| Waarde | Betekenis |
|---|---|
| JA | elektrische boiler actief |
| NEE | CV actief |

Homey gebruikt deze variabele als bronselectie.

---

## 6. Seizoensbeslissing

Homey beoordeelt niet één dag, maar zeven volledige meetdagen.

Voor 2026:

```text
≤ 3 goede PV-dagen → advies naar CV
≥ 5 goede PV-dagen → advies naar boiler
```

De tussenruimte voorkomt pendelen.

De melding gaat naar **Mr Horizon** en vereist handmatige fysieke omschakeling.

---

## 7. Tesla-laadarchitectuur

De Tesla-laag bestaat uit:

- Easee Charger;
- Easee Equalizer;
- Tesla Model 3 Highland RWD;
- bestaande Tesla-flows;
- nieuwe centrale Energie Manager.

De nieuwe monitoring gebruikt voortaan:

```text
evcharger_charging
meter_power (cumulatief)
measure_power (alleen actueel)
```

De historische `measure_power` Insight wordt niet gebruikt als primaire bron omdat daarin null-waarden voorkomen.

Per laadsessie worden straks vastgelegd:

- starttijd;
- eindtijd;
- duur;
- geladen kWh;
- gemiddeld vermogen;
- maximaal vermogen.

---

## 8. Shadow versus actief

### Actief

Actieve bestaande regelingen sturen werkelijk apparaten.

Voorbeelden:

- huidige warmwateroptimalisatie;
- bestaande Tesla-laadflows;
- bestaande Quooker-flows.

### Shadow

De centrale Energie Manager:

- leest;
- berekent;
- logt;
- vergelijkt;
- stuurt nog niet.

Doel:

```text
werkelijk gedrag
      versus
gesimuleerde centrale beslissing
```

Na voldoende validatie kan de centrale Energie Manager stapsgewijs delen overnemen.

---

## 9. Constraints-overzicht

| Constraint | Effect |
|---|---|
| Tesla minimaal 3×6 A | onder ca. 4,14 kW geen zinvolle laadstart |
| Boiler circa 2 kW | benut kleiner PV-overschot |
| Boiler startvenster huidig | 09:30–14:30 |
| Boiler hard einde huidig | 15:30 |
| Gepland boilervenster | start tot 16:30, einde 18:00 |
| Quooker werkdagen | 15:00–19:00 |
| Quooker weekend | 08:00–19:00 |
| CV ↔ boiler | handmatige omschakeling |
| `WW_Boilermodus` | bepaalt welke warmwaterbron logisch actief is |
| 7-daagse hysterese | voorkomt veelvuldig omschakelen |
| Shadow mode | centrale manager stuurt nog geen apparaten |
| P1 beschikbaarheid | zonder P1 geen centrale vermogensbeslissing |
| Device beschikbaarheid | ontbrekend apparaat → fout/fail-safe |
| Flowversionering | per functionele flowfamilie maximaal één actieve versie |

---

## 10. Architectuur met alle beslisregels

```text
                         ┌──────────────────────┐
                         │      PV-bronnen      │
                         │ SE + GW4200 + GW2000 │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      P1-meter        │
                         │ netto huisbalans     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │      ENERGIE MANAGER         │
                    │ Homey / later Victron EMS    │
                    └───────┬─────────┬────────────┘
                            │         │
              ┌─────────────┘         └─────────────┐
              ▼                                     ▼
      ┌────────────────┐                     ┌────────────────┐
      │     TESLA      │                     │     BOILER     │
      │ ≥ ~4,14 kW     │                     │ ≥ ~2,1 kW PV   │
      │ prioriteit #2  │                     │ prioriteit #3  │
      └────────────────┘                     └────────────────┘
              │                                     │
              └─────────────┬───────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │ Teruglevering   │
                   └─────────────────┘

        Parallelle constraints:
        ─────────────────────────────────────────────
        Quooker: werktijden/weekendvenster respecteren
        CV↔boiler: handmatig, WW_Boilermodus leidend
        7-daagse seizoenshysterese
        Shadow-validatie vóór centrale aansturing
        Fail-safe bij ontbrekende P1/device-data
        Maximaal één actieve versie per flowfamilie
```

---

## 11. Toekomstige Victron-laag

De geplande Victron-architectuur voegt later toe:

- MultiPlus-II 5000;
- Cerbo GX;
- VM/3P75CT;
- thuisbatterij;
- Victron EMS.

Daarbij wordt de rolverdeling:

```text
Victron EMS
  └─ batterij / net / energie-optimalisatie

Homey
  └─ huishoudelijke flexibiliteit en orchestratie
       ├─ Tesla
       ├─ boiler
       ├─ Quooker constraints
       └─ gebruikersmeldingen
```

Homey blijft dus vooral de **comfort- en verbruikersorchestrator**.

Victron wordt de primaire laag voor batterij- en netoptimalisatie.

---

## 12. Flowversionering en wijzigingsbeheer

Vanaf 15 augustus 2026 geldt voor iedere Homey-flowfamilie:

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

Naamgeving:

```text
<functionele flownaam> vX.Y
```

Een normale wijziging verhoogt de subversie. Oude versies worden als rollback-/referentiepunt behouden, maar van dezelfde functionele flowfamilie mag **maximaal één versie actief** zijn.

Bestaande ongenummerde flows blijven bestaan tot hun eerstvolgende inhoudelijke wijziging. Op dat moment wordt een nieuwe genummerde opvolger aangemaakt in plaats van de bestaande flow in-place te wijzigen.

De websitebeschrijving en wijzigingshistorie worden tegelijk met de nieuwe Homey-versie aangepast.

---

## 13. Ontwerpprincipes

De architectuur volgt deze principes:

- meten vóór sturen;
- centrale P1 als waarheid voor huisbalans;
- Tesla vóór boiler;
- boiler benut kleiner PV-overschot;
- Quooker als constraint, niet als vrije batterijachtige belasting;
- seizoenswissels met hysterese;
- handmatige fysieke omschakelingen expliciet documenteren;
- fail-safe boven agressieve optimalisatie;
- eerst shadow mode, daarna gecontroleerde migratie;
- iedere inhoudelijke flowwijziging maakt een nieuwe genummerde flowversie;
- van één functionele flowfamilie is maximaal één versie actief;
- oude flowversies blijven beschikbaar voor rollback/referentie;
- alle Homey-wijzigingen tegelijk vastleggen in Flow Manual en website.
