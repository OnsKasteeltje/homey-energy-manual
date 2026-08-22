# Victron hardwarebaseline

_Status: 22 augustus 2026_

## 1. Doelarchitectuur

De actuele werkhypothese is een **AC-coupled Victron ESS** op een bestaande 3×25 A netaansluiting.

- Victron MultiPlus-II 48/5000: **1-fase ESS op L1**.
- Cerbo GX als GX-/communicatielaag.
- VM-3P75CT in de meterkast als centrale 3-fasemeter voor L1/L2/L3.
- MultiPlus, Cerbo GX en batterijbank in de schuur.
- Bestaande verbinding meterkast–schuur: circa 20 m, 5G2,5 mm², huidige ontwerpgrens 3×16 A totdat installatiegegevens anders bevestigen.
- Bestaande PV-omvormers blijven AC-coupled.
- ESS-regeling: `Total of all phases`.
- Homey blijft huishoudelijke orkestratielaag; Victron wordt eigenaar van batterij/SOC/netregeling.

Victron schrijft voor dat een single-phase ESS binnen een 3-fase net op **L1** wordt aangesloten. Met `Total of all phases` regelt het single-phase ESS de som L1+L2+L3 richting de ingestelde netsetpointwaarde, ook al vindt de fysieke laad/ontlaadstroom van de MultiPlus op L1 plaats.

## 2. Gevalideerde PV-fasemapping

Op 22 augustus 2026 zijn de drie PV-omvormers fysiek aan/uit geschakeld terwijl de directe P1-fasewaarden zijn gevolgd. De fysieke schakeling was ground truth; vertraagde Homey/inverterwaarden zijn niet gebruikt als primaire fase-identificatie.

| Omvormer | Installatie | Fase | Validatie |
|---|---|---:|---|
| SolarEdge SE3680H-RW000BEN4 | SolarEdge PV | **L3** | VALIDATED / HIGH |
| GoodWe GW4200D-NS | grote GoodWe, schuur, 12 panelen | **L2** | VALIDATED / HIGH |
| GoodWe GW2000-XS | kleine GoodWe / CV, 6 panelen | **L3** | VALIDATED / HIGH |

Daarmee geldt fysiek:

- **L1:** geen PV-omvormer;
- **L2:** GoodWe GW4200D-NS;
- **L3:** SolarEdge SE3680H + GoodWe GW2000-XS.

De waargenomen fase-onbalans is daarom verklaarbaar en is op zichzelf geen storing. L3 kan bij zon veel sterker exporteren dan L1 en L2.

## 3. MultiPlus-fasekeuze

De MultiPlus-II 48/5000 wordt op **L1** ontworpen. Dit sluit aan op de Victron ESS-installatie-eis voor een single-phase ESS in een 3-fase net en voorkomt bovendien dat de batterij-inverter fysiek wordt toegevoegd aan de reeds PV-zware L2/L3-fasen.

Conceptueel:

```text
NET / HOOFDAANSLUITING 3×25 A
          │
     hoofdschakelaar
          │
      VM-3P75CT
     meet L1/L2/L3
          │
 ┌────────┼────────┐
 L1       L2       L3
 │        │        ├─ SolarEdge SE3680H
 │        │        └─ GoodWe GW2000-XS
 │        └────────── GoodWe GW4200D-NS
 │
 └─ bestaande schuurvoeding 5G2,5 mm², ~20 m
          │
      beveiliging
          │
 MultiPlus-II 48/5000
      AC-IN L1
       │     │
    AC-OUT  48 V DC
       │     │
 backup-   batterijbank
 groepen      │
             Cerbo GX
```

## 4. Bestaande schuurvoeding en AC-limiet

De bestaande schuurverbinding wordt voorlopig als **3×16 A** behandeld. Zolang deze infrastructuur niet opnieuw installatietechnisch is beoordeeld of verzwaard, geldt als ontwerpregel:

`MultiPlus AC input current limit ≤ 16 A`.

Bij circa 230 V correspondeert 16 A met ongeveer 3,68 kVA netvermogen op de betreffende fase. PowerAssist kan aan AC-out batterijvermogen toevoegen, maar verhoogt uiteraard niet de toegestane stroom door de bestaande voedingskabel en beveiliging.

De definitieve automaat-, aardlek-, selectiviteits- en kabeldimensionering moet vóór bestelling/plaatsing worden getoetst aan de exacte MultiPlus-II hardwarevariant, aanlegwijze en geldende installatie-eisen.

## 5. AC-out / noodstroom

De voorkeursarchitectuur is **geen volledige woning of volledige schuur achter AC-out**, maar een aparte backupverdeler met geselecteerde essentiële belastingen. Zware flexloads zoals Tesla, elektrische boiler en andere grote niet-kritische verbruikers horen niet standaard op de backup-uitgang.

Bij netuitval vormt één MultiPlus op L1 geen 3-fase eiland. De bestaande PV-omvormers op L2 en L3 zijn daarom in deze basisarchitectuur niet beschikbaar als noodstroom-PV. Een echte 3-fase ESS/backuparchitectuur vereist ten minste één inverter/charger per fase.

## 6. DC-zijde

De 48 V DC-zijde is een hoogstroominstallatie. Definitieve DC-kabeldoorsnede, hoofdzekering, DC-disconnect, rails en batterijbeveiliging worden niet op basis van een chat-aanname vastgezet maar rechtstreeks uit de actuele handleidingen van de exact gekozen MultiPlus-II en batterijconfiguratie gedimensioneerd.

De batterijbank blijft een afzonderlijk bestelbesluit totdat capaciteit, maximaal laad-/ontlaadvermogen, BMS-communicatie en beveiliging definitief zijn herbevestigd.

## 7. Ontwerpstatus

- `VALIDATED` — PV-fasemapping L2/L3.
- `DECIDED` — single-phase ESS/MultiPlus op L1.
- `DECIDED` — VM-3P75CT meet alle drie fasen.
- `DECIDED` — ESS gebruikt `Total of all phases`.
- `DECIDED` — bestaande 5G2,5 mm² / circa 20 m blijft uitgangspunt; 16 A is de huidige AC-input ontwerpgrens.
- `DECIDED` — aparte geselecteerde backupgroepen achter AC-out.
- `OPEN` — definitieve beveiligingsmatrix AC/DC.
- `OPEN` — definitieve batterijbank en DC-dimensionering.
- `OPEN` — definitieve lijst backupgroepen.

## 8. Referentie

Voor de ESS-fasekeuze en multiphase-regeling is de actuele Victron **ESS Design & Installation Manual** leidend. Daarin staat voor een single-phase ESS op een 3-fase net zowel de L1-installatie-eis als de werking van `Total of all phases` beschreven.
