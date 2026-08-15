# Groepen & fasen

Deze pagina is een **levend overzicht van de elektrische indeling van de woning**. Het doel is om per apparaat vast te leggen op welke fase en, zodra bekend, op welke groep/automaat het is aangesloten. De indeling wordt stap voor stap bevestigd met Homey/P1-metingen, de groepenkastfoto en praktische tests.

## Betrouwbaarheidsniveaus

| Status | Betekenis |
|---|---|
| **Bevestigd** | De fase of groep is in een afzonderlijke praktijktest of fysieke controle duidelijk vastgesteld. |
| **Waarschijnlijk** | De koppeling past bij het gemeten gedrag, de technische aansluiting of de groepenkastfoto, maar is nog niet afzonderlijk elektrisch gevalideerd. |
| **Open** | Nog onvoldoende informatie om een fase of groep toe te wijzen. |

!!! info "Fase is niet hetzelfde als groep"
    De P1-meter meet L1, L2 en L3 aan de hoofdaansluiting. Daarmee kan een apparaat vaak betrouwbaar aan een **fase** worden gekoppeld, maar niet automatisch aan een specifiek genummerde installatieautomaat. Voor het exacte groepnummer is een aanvullende uitschakeltest of fysieke controle van de groepenkast nodig.

## Huidige indeling

| Apparaat / installatie | Fase | Groep / automaat | Status | Onderbouwing |
|---|---:|---:|---|---|
| Wasmachine | **L2** | Nog te bepalen | **Fase bevestigd / groep open** | Testwas 15-08-2026: duidelijke extra verwarmingsbelasting op L2. |
| Droger | **L3** | Nog te bepalen | **Fase bevestigd / groep open** | Droogtest 15-08-2026: extra belasting hoofdzakelijk op L3. |
| Tesla / Easee-lader | **L1 + L2 + L3** | Laadgroep nog te documenteren | **Fase bevestigd / groep open** | 3-fase verbruiker; afzonderlijke fasewaarden zichtbaar in Homey. |
| Elektrische boiler | **L2** | Nog te bepalen | **Fase bevestigd / groep open** | Verwarmingsbelasting circa 1,93–2,13 kW verschijnt op L2. |
| Vaatwasser | Nog te bepalen | Nog te bepalen | **Open** | Praktijktest uitgevoerd; nog onvoldoende geïsoleerd. |
| Elektrisch fornuis / kookplaat | Nog te bepalen | Nog te bepalen | **Open** | Afzonderlijke validatie nodig. |
| Waterkoker | **L2** | Nog te bepalen | **Fase bevestigd / groep open** | Aan/uit-test: circa 2,15 kW extra op L2. |
| Koffiezetapparaat | Nog te bepalen | Nog te bepalen | **Open** | Fasekoppeling nog niet betrouwbaar bevestigd. |
| Quooker | Nog te bepalen | Nog te bepalen | **Open** | Nog te valideren. |
| Quatt warmtepomp / CV-installatie | Nog te bepalen | Nog te bepalen | **Open** | Nog te valideren. |
| SolarEdge SE3680H | **Wordt gemonitord** | Nog te bepalen | **Meetfase actief** | Automatische fasecorrelatie via `PV omvormers fase-monitor v1.0`. |
| GoodWe GW4200D-NS | **Wordt gemonitord** | Nog te bepalen | **Meetfase actief** | Automatische fasecorrelatie via `PV omvormers fase-monitor v1.0`. |
| GoodWe GW2000-XS | **Wordt gemonitord** | Nog te bepalen | **Meetfase actief** | Automatische fasecorrelatie via `PV omvormers fase-monitor v1.0`. |
| Schuurvoeding | **L1 + L2 + L3** | **Groep 14, 3-polig B16** | **Bevestigd** | Op 15-08-2026 fysiek in de meterkast gecontroleerd: groep 14 is de 3-fase voeding naar de schuur. |

## Automatische PV-fasemonitor

Op **15 augustus 2026** is in Homey de Advanced Flow **`PV omvormers fase-monitor v1.0`** geactiveerd. Deze flow is uitsluitend bedoeld voor meting en analyse en schakelt geen apparaten of omvormers.

Iedere **2 minuten** wordt gelijktijdig vastgelegd:

- P1-vermogen op **L1, L2 en L3**;
- totaal P1-vermogen;
- productie van **SolarEdge SE3680H**;
- productie van **GoodWe GW4200D-NS**;
- productie van **GoodWe GW2000-XS**.

De meetreeks wordt maximaal **36 uur** opgeslagen in de aparte Homey Logic-state **`PV Fase Monitor v1.0`**. Door natuurlijke productievariaties van iedere omvormer te correleren met veranderingen op L1/L2/L3 kan de meest waarschijnlijke aansluitfase per omvormer worden bepaald zonder de omvormers actief te schakelen.

De status wordt pas van **Meetfase actief** naar **Bevestigd** gewijzigd wanneer de correlatie voldoende eenduidig is of aanvullend met een gecontroleerde test is gevalideerd.

## Wat is nu al zeker?

- **L2:** wasmachine, elektrische boiler en waterkoker;
- **L3:** droger;
- **L1 + L2 + L3:** Tesla/Easee-lader;
- **groep 14:** **bevestigd** als 3-polige B16-schuurvoeding.

Voor de overige huishoudelijke apparaten is het exacte installatieautomaatnummer nog niet bewezen.

## Meetmethode voor fase

Voor een betrouwbare fasekoppeling wordt bij voorkeur één apparaat tegelijk getest. Voor PV-omvormers gebruiken we daarnaast de automatische correlatiemethode: de afzonderlijke productie wordt over langere tijd vergeleken met de drie P1-fasen. Dit voorkomt onnodig schakelen van de omvormers en levert meerdere onafhankelijke meetpunten op.

## Meetmethode voor exact groepnummer

Een groepnummer wordt pas als **Bevestigd** gemarkeerd wanneer de koppeling fysiek is vastgesteld via een gecontroleerde uitschakeltest of fysieke verificatie.

!!! warning "Veiligheid"
    Schakel alleen installatieautomaten met de normale bedieningshendel. Verwijder geen afdekkappen en raak geen bedrading of spanningsvoerende delen aan.

## Fasebelasting

Wasmachine, boiler en waterkoker zijn alle drie aan L2 gekoppeld. Vooral boiler en waterkoker kunnen samen ongeveer 4,1 kW toevoegen. Dit blijft relevant voor toekomstige fasebalancering en voor de voorbereiding van de Victron-opstelling.

## Beheerregel

Nieuwe betrouwbare inzichten over **fase- of groepindeling** worden direct op deze pagina verwerkt. Voor Homey-flows geldt versiebeheer: een inhoudelijke aanpassing resulteert in een nieuwe subversie; slechts één versie van dezelfde functionele flow hoort actief te zijn.

## Open vervolgstappen

De actieve PV-fasemonitor verzamelt nu de data waarmee de fase van de drie omvormers kan worden bepaald. Daarnaast blijven vaatwasser, kookplaat/fornuis, koffiezetapparaat, Quooker en Quatt nog open. Voor reeds geïdentificeerde apparaten moeten de exacte installatieautomaten nog fysiek worden gekoppeld. **Groep 14 als schuurvoeding is niet langer een open punt.**

> Laatste inhoudelijke update: 15 augustus 2026, avond. Groep 14 is nu door fysieke controle in de meterkast bevestigd als de 3-polige B16-schuurvoeding.