# Groepen & fasen

Deze pagina is een **levend overzicht van de elektrische indeling van de woning**. Het doel is om per apparaat vast te leggen op welke fase en, zodra bekend, op welke groep/automaat het is aangesloten. De indeling wordt stap voor stap bevestigd met Homey/P1-metingen, de groepenkastfoto en praktische tests.

## Betrouwbaarheidsniveaus

| Status | Betekenis |
|---|---|
| **Bevestigd** | De fase of groep is in een afzonderlijke praktijktest duidelijk vastgesteld. |
| **Waarschijnlijk** | De koppeling past bij het gemeten gedrag, de technische aansluiting of de groepenkastfoto, maar is nog niet afzonderlijk elektrisch gevalideerd. |
| **Open** | Nog onvoldoende informatie om een fase of groep toe te wijzen. |

!!! info "Fase is niet hetzelfde als groep"
    De P1-meter meet L1, L2 en L3 aan de hoofdaansluiting. Daarmee kan een apparaat vaak betrouwbaar aan een **fase** worden gekoppeld, maar niet automatisch aan een specifiek genummerde installatieautomaat. Voor het exacte groepnummer is een aanvullende uitschakeltest of fysieke controle van de groepenkast nodig.

## Huidige indeling

| Apparaat / installatie | Fase | Groep / automaat | Status | Onderbouwing |
|---|---:|---:|---|---|
| Wasmachine | **L2** | Nog te bepalen | **Fase bevestigd / groep open** | Tijdens de testwas van 15-08-2026 steeg L2 van circa 1,97 kW naar circa 3,83–3,90 kW. De extra belasting van ongeveer 1,9 kW past bij het verwarmingselement van de wasmachine; L1 en L3 vertoonden geen vergelijkbare sprong. |
| Droger | **L3** | Nog te bepalen | **Fase bevestigd / groep open** | Tijdens de droogtest van 15-08-2026 veranderde vooral L3: de teruglevering nam af van ongeveer 350–380 W naar circa 40–65 W. L1 en L2 bleven vrijwel vlak. |
| Tesla / Easee-lader | **L1 + L2 + L3** | Laadgroep nog te documenteren | **Fase bevestigd / groep open** | De lader is een 3-fase verbruiker en in Homey zichtbaar met afzonderlijke stroomwaarden per fase. Het exacte automaatnummer moet nog uit de kastindeling worden vastgelegd. |
| Elektrische boiler | **L2** | Nog te bepalen | **Fase bevestigd / groep open** | Tijdens verwarmen trok de boiler circa 1,93–2,13 kW; de duidelijke extra belasting verscheen op L2. De aansluitfase is daarmee praktisch bevestigd. |
| Vaatwasser | Nog te bepalen | Nog te bepalen | **Open** | Praktijktest uitgevoerd, maar fasekoppeling nog niet voldoende geïsoleerd om formeel vast te leggen. |
| Elektrisch fornuis / kookplaat | Nog te bepalen | Nog te bepalen | **Open** | Grootverbruiker; test viel deels samen met andere belasting. Fase-/groepindeling moet daarom afzonderlijk worden vastgesteld. |
| Waterkoker | **L2** | Nog te bepalen | **Fase bevestigd / groep open** | Gecontroleerde aan/uit-test op 15-08-2026: terwijl de boiler bleef verwarmen steeg P1 L2 van circa 2,00 kW naar circa 4,15 kW. De extra belasting was circa 2,15 kW; L1 en L3 bleven vrijwel gelijk. |
| Koffiezetapparaat | Nog te bepalen | Nog te bepalen | **Open** | Korte testbelasting uitgevoerd; fasekoppeling nog niet betrouwbaar genoeg om te bevestigen. |
| Quooker | Nog te bepalen | Nog te bepalen | **Open** | Regeling is in Homey gedocumenteerd, maar de elektrische fase/groep is nog niet aan deze inventaris toegevoegd. |
| Quatt warmtepomp / CV-installatie | Nog te bepalen | Nog te bepalen | **Open** | Energieverbruik is in Homey beschikbaar; fase- en groepstoewijzing moet nog worden gevalideerd. |
| PV-omvormers | Per omvormer te bepalen | Per omvormer te bepalen | **Open** | Voor de volledige nettopologie moet per omvormer worden vastgelegd op welke fase en groep deze invoedt. |
| Schuurvoeding | **L1 + L2 + L3** | **Groep 14, 3-polig B16** | **Waarschijnlijk** | Op basis van de aangeleverde meterkastfoto en de Victron-documentatie wordt groep 14 voorlopig als de 3-fase 3×16 A voeding naar de schuur behandeld. Definitieve bevestiging via gecontroleerde uitschakeltest blijft nodig. |

## Wat is nu al zeker?

De praktijktests van 15 augustus 2026 geven een duidelijk fasebeeld voor vier afzonderlijke huishoudelijke verbruikers:

- **L2:** wasmachine, elektrische boiler en waterkoker;
- **L3:** droger;
- **L1 + L2 + L3:** Tesla/Easee-lader;
- **groep 14:** waarschijnlijk de 3-polige B16-schuurvoeding.

Voor de huishoudelijke apparaten is het **exacte installatieautomaatnummer nog niet bewezen**. Dat kan niet betrouwbaar uit alleen P1-fasemeting worden afgeleid. Deze pagina maakt daarom voortaan expliciet onderscheid tussen een bevestigde fase en een bevestigde groep.

## Meetmethode voor fase

Voor een betrouwbare fasekoppeling wordt bij voorkeur één apparaat tegelijk getest:

1. noteer een stabiele uitgangssituatie van P1 totaal en L1/L2/L3;
2. start slechts één te identificeren apparaat;
3. wacht tot het apparaat daadwerkelijk vermogen trekt;
4. vergelijk de verandering op L1, L2 en L3;
5. herhaal zo nodig tijdens een herkenbare vermogensfase, zoals verwarmen of centrifugeren.

## Meetmethode voor exact groepnummer

Een groepnummer wordt pas als **Bevestigd** gemarkeerd wanneer de koppeling fysiek is vastgesteld. De voorkeursmethode is:

1. zorg dat het te identificeren apparaat aan staat of duidelijk vermogen trekt;
2. schakel één vermoedelijke installatieautomaat uit;
3. controleer dat uitsluitend het bedoelde apparaat of circuit spanningsloos wordt;
4. schakel de automaat weer in en controleer herstel;
5. leg automaatnummer, fase en aangesloten apparaten direct op deze pagina vast.

!!! warning "Veiligheid"
    Schakel alleen installatieautomaten met de normale bedieningshendel. Verwijder geen afdekkappen en raak geen bedrading of spanningsvoerende delen aan. Bij twijfel moet de fysieke identificatie door een elektricien worden uitgevoerd.

## Reeds geïdentificeerd

### Wasmachine — L2

De 20-minutenwas op 15 augustus 2026 gaf een zeer duidelijke verwarmingspiek op L2. Rond de verwarmingsfase liep L2 op van ongeveer 1,97 kW naar ongeveer 3,9 kW. Dat maakt de fase-identificatie sterk.

### Droger — L3

Bij de droger was de stijging kleiner en geleidelijker, passend bij een zuiniger regelend droogproces. De verandering vond vrijwel uitsluitend op L3 plaats. Daarom is de droger als L3 vastgelegd.

### Elektrische boiler — L2

Tijdens actief verwarmen trok de boiler ongeveer 2 kW. De extra belasting verscheen duidelijk op L2. Daarmee is de boiler aan L2 gekoppeld. De huidige toestand waarin de boiler ingeschakeld kan zijn maar vrijwel geen vermogen trekt, past bij thermostatische afslag en verandert deze fase-identificatie niet.

### Waterkoker — L2

Tijdens de gecontroleerde test op 15 augustus 2026 bleef de boiler verwarmen en steeg L2 van circa 2,00 kW naar circa 4,15 kW zodra de waterkoker werd aangezet. De extra circa 2,15 kW verscheen vrijwel volledig op L2. Daarmee is de waterkoker als L2 bevestigd.

### Schuurvoeding — waarschijnlijk groep 14

In het integrale Victron-ontwerp is op basis van de groepenkastfoto vastgelegd dat **groep 14 waarschijnlijk de 3-polige B16-voeding naar de schuur** is. Omdat dit nog niet met een gecontroleerde uitschakeltest is bevestigd, blijft de status *Waarschijnlijk*.

!!! warning "Fasebelasting L2"
    Wasmachine, boiler en waterkoker zijn alle drie aan L2 gekoppeld. Vooral boiler en waterkoker kunnen samen ongeveer 4,1 kW toevoegen; wanneer de wasmachine tegelijk verwarmt kan L2 tijdelijk nog aanzienlijk zwaarder worden belast. Dit wordt meegenomen bij toekomstige fasebalancering en energie-optimalisatie.

## Beheerregel

Nieuwe betrouwbare inzichten over **fase- of groepindeling** worden voortaan direct in deze GitHub-pagina verwerkt. Daarbij blijven de niveaus **Bevestigd**, **Waarschijnlijk** en **Open** leidend; een vermoeden wordt niet zonder voldoende validatie als bevestigd vastgelegd.

## Open vervolgstappen

De eerstvolgende nuttige fase-identificaties zijn de **vaatwasser, kookplaat/fornuis, koffiezetapparaat, Quooker en PV-omvormers**. Daarnaast moeten voor de reeds op fase geïdentificeerde apparaten — **wasmachine, droger, boiler, waterkoker en Tesla/Easee** — de exacte installatieautomaten nog fysiek worden gekoppeld. Ook groep 14 als schuurvoeding moet nog éénmaal met een gecontroleerde uitschakeltest worden bevestigd.

> Laatste inhoudelijke update: 15 augustus 2026, avond. De fase-informatie uit de praktijktests is verwerkt; exacte groepnummers worden alleen toegevoegd wanneer ze daadwerkelijk zijn bewezen.
