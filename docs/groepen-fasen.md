# Groepen & fasen

Deze pagina is een **levend overzicht van de elektrische indeling van de woning**. Het doel is om per apparaat vast te leggen op welke fase en, zodra bekend, op welke groep/automaat het is aangesloten. De indeling wordt stap voor stap bevestigd met Homey/P1-metingen en praktische tests.

## Betrouwbaarheidsniveaus

| Status | Betekenis |
|---|---|
| **Bevestigd** | De fase is in een afzonderlijke praktijktest duidelijk uit het P1-profiel afgeleid. |
| **Waarschijnlijk** | De koppeling past bij het gemeten gedrag of de technische aansluiting, maar is nog niet afzonderlijk gevalideerd. |
| **Open** | Nog onvoldoende informatie om een fase of groep toe te wijzen. |

!!! info "Fase is niet hetzelfde als groep"
    De P1-meter meet L1, L2 en L3 aan de hoofdaansluiting. Daarmee kan een apparaat vaak betrouwbaar aan een **fase** worden gekoppeld, maar niet automatisch aan een specifiek genummerde installatieautomaat. Voor het exacte groepnummer is een aanvullende test of controle in de groepenkast nodig.

## Huidige indeling

| Apparaat / installatie | Fase | Groep / automaat | Status | Onderbouwing |
|---|---:|---:|---|---|
| Wasmachine | **L2** | Nog te bepalen | **Bevestigd** | Tijdens de testwas van 15-08-2026 steeg L2 van circa 1,97 kW naar circa 3,83–3,90 kW. De extra belasting van ongeveer 1,9 kW past bij het verwarmingselement van de wasmachine; L1 en L3 vertoonden geen vergelijkbare sprong. |
| Droger | **L3** | Nog te bepalen | **Bevestigd** | Tijdens de droogtest van 15-08-2026 veranderde vooral L3: de teruglevering nam af van ongeveer 350–380 W naar circa 40–65 W. L1 en L2 bleven vrijwel vlak. |
| Tesla / Easee-lader | **L1 + L2 + L3** | Laadgroep nog te documenteren | **Waarschijnlijk** | De lader is als 3-fase verbruiker in Homey zichtbaar met afzonderlijke stroomwaarden P1/P2/P3. Exacte automaat/groep nog vastleggen. |
| Elektrische boiler | **L2** | Nog te bepalen | **Bevestigd** | Tijdens verwarmen trok de boiler circa 1,93 kW; de P1-belasting op L2 lag rond 2,00 kW terwijl L1 en L3 laag bleven. De aansluitfase is daarmee praktisch bevestigd. |
| Vaatwasser | Nog te bepalen | Nog te bepalen | **Open** | Praktijktest uitgevoerd, maar fasekoppeling nog niet formeel in dit overzicht gevalideerd. |
| Elektrisch fornuis / kookplaat | Nog te bepalen | Nog te bepalen | **Open** | Grootverbruiker; fase-/groepindeling nog apart vastleggen. |
| Waterkoker | **L2** | Nog te bepalen | **Bevestigd** | Gecontroleerde aan/uit-test op 15-08-2026: terwijl de boiler bleef verwarmen steeg P1 L2 van circa 2,00 kW naar circa 4,15 kW. De extra belasting was circa 2,15 kW; L1 en L3 bleven vrijwel gelijk. |
| Koffiezetapparaat | Nog te bepalen | Nog te bepalen | **Open** | Korte testbelasting; fasekoppeling nog te bevestigen. |
| Quooker | Nog te bepalen | Nog te bepalen | **Open** | Regeling is in Homey gedocumenteerd, maar de elektrische fase/groep is nog niet aan deze inventaris toegevoegd. |
| Quatt warmtepomp / CV-installatie | Nog te bepalen | Nog te bepalen | **Open** | Energieverbruik is in Homey beschikbaar; fase- en groepstoewijzing moet nog worden gevalideerd. |
| PV-omvormers | Per omvormer te bepalen | Per omvormer te bepalen | **Open** | Voor de volledige nettopologie moet per omvormer worden vastgelegd op welke fase en groep deze invoedt. |

## Meetmethode

Voor een betrouwbare koppeling wordt bij voorkeur één apparaat tegelijk getest:

1. noteer een stabiele uitgangssituatie van P1 totaal en L1/L2/L3;
2. start slechts één te identificeren apparaat;
3. wacht tot het apparaat daadwerkelijk vermogen trekt;
4. vergelijk de verandering op L1, L2 en L3;
5. herhaal zo nodig tijdens een herkenbare vermogensfase, zoals verwarmen of centrifugeren;
6. leg daarna met de groepenkast het exacte automaatnummer vast.

## Reeds geïdentificeerd

### Wasmachine — L2

De 20-minutenwas op 15 augustus 2026 gaf een zeer duidelijke verwarmingspiek op L2. Rond de verwarmingsfase liep L2 op van ongeveer 1,97 kW naar ongeveer 3,9 kW. Dat maakt de fase-identificatie sterk.

### Droger — L3

Bij de droger was de stijging kleiner en geleidelijker, passend bij een zuiniger regelend droogproces. De verandering vond vrijwel uitsluitend op L3 plaats. Daarom is de droger als L3 vastgelegd.

### Elektrische boiler — L2

Tijdens actief verwarmen trok de boiler circa 1,93 kW. De P1-belasting op L2 lag tegelijkertijd rond 2,00 kW, terwijl L1 en L3 laag bleven. Daarmee is de boiler aan L2 gekoppeld.

### Waterkoker — L2

Tijdens de gecontroleerde test op 15 augustus 2026 bleef de boiler verwarmen en steeg L2 van circa 2,00 kW naar circa 4,15 kW zodra de waterkoker werd aangezet. De extra circa 2,15 kW verscheen vrijwel volledig op L2. Daarmee is de waterkoker als L2 bevestigd.

!!! warning "Fasebelasting L2"
    Boiler en waterkoker zitten beide op L2. Als beide gelijktijdig verwarmen, voegen zij samen ongeveer 4,1 kW belasting aan L2 toe. Dit wordt meegenomen bij toekomstige fasebalancering en energie-optimalisatie.

## Beheerregel

Nieuwe betrouwbare inzichten over **fase- of groepindeling** worden voortaan direct in deze GitHub-pagina verwerkt. Daarbij blijven de niveaus **Bevestigd**, **Waarschijnlijk** en **Open** leidend; een vermoeden wordt niet zonder voldoende validatie als bevestigd vastgelegd.

## Open vervolgstappen

De eerstvolgende nuttige identificaties zijn de **vaatwasser, kookplaat/fornuis, Quooker en PV-omvormers**. Zodra de fase bekend is, kan het exacte groepnummer worden toegevoegd door de betreffende automaat gecontroleerd uit te schakelen of de kastindeling te vergelijken met de bedrading.

> Laatste inhoudelijke update: 15 augustus 2026.
