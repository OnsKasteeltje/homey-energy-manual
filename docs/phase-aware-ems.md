# Phase-aware EMS-regels

_Status: 22 augustus 2026_

## Doel

De EMS-beslislaag gebruikt niet alleen het totale P1-netvermogen, maar bewaakt waar relevant ook L1/L2/L3 afzonderlijk. Fase-onbalans is daarbij **regelinput en diagnostiek**, niet automatisch een foutconditie.

## Gevalideerde fysieke context

- Hoofdaansluiting: 3×25 A.
- L1: geen PV-omvormer; geplande single-phase Victron MultiPlus-II.
- L2: GoodWe GW4200D-NS.
- L3: SolarEdge SE3680H + GoodWe GW2000-XS.
- Tesla/Easee: 3-fase belasting; tijdens de gevalideerde deadline-laadsessie ongeveer symmetrisch over de drie fasen.

## Architectuurregel

```text
P1 totaal
   │
   ├─► economische/netto energiebalans
   │
   └─► P1 L1/L2/L3
             │
             ▼
       phase safety guard
       3×25 A per fase
             │
             ▼
       flex-/controlbesluit
```

Een netto exportwaarde betekent niet dat iedere fase afzonderlijk exporteert. Door de PV-verdeling kan L1 importeren terwijl L2/L3 exporteren. Grote regelbare belastingen mogen daarom niet uitsluitend op basis van de som van de drie fasen worden beoordeeld wanneer fasebelasting relevant is voor veiligheid of beschikbare marge.

## Tesla/Easee

De Easee Equalizer blijft de autonome harde lokale load-balancinglaag. Homey/EMS mag deze beveiliging niet omzeilen. Het EMS kan de fasewaarden gebruiken voor planning, classificatie en preventieve guards, maar de Equalizer blijft leidend voor de feitelijke toegestane laadstroom.

## Victron

De toekomstige single-phase Victron ESS staat fysiek op L1. Met Victron `Total of all phases` mag de batterijregeling de totale L1+L2+L3 netbalans compenseren. Daardoor kan L1 lokaal exporteren terwijl L2/L3 importeren of omgekeerd; dit is bij deze architectuur niet automatisch een fout.

De EMS-UI en diagnose mogen daarom onderscheid maken tussen:

- **netto woningbalans**: som van L1+L2+L3;
- **fasebalans**: individuele stromen/vermogens per fase;
- **faseveiligheid**: marge ten opzichte van de installatiegrens per fase.

## Invariant

`PHASE_IMBALANCE` mag niet zelfstandig dezelfde semantiek krijgen als een elektrische fout. Alleen overschrijding van ingestelde fasegrenzen, ongeldige metingen of een andere expliciete safety-condition mag een safety-block veroorzaken.

Deze regel moet worden meegenomen in toekomstige Tesla-, boiler- en Victron-controlwijzigingen en in de requirements-traceability wanneer de phase guard operationeel wordt geïmplementeerd.
