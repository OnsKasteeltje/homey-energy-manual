# Homey Energy Manual

<div id="home-architecture">
  <div class="ha-shell">
    <div class="ha-health">
      <strong>Architectuuroverzicht laden…</strong>
      <span>Live status wordt uit de bestaande Homey/GitHub-publicaties opgebouwd.</span>
    </div>
  </div>
</div>

## Architectuurprincipe

De homepage volgt de doelarchitectuur van de energieregeling: **meten → context → beslissing → validatie → aansturing**, met **publicatie & historie** en **platform & infrastructuur** als ondersteunende lagen.

Vanaf **Energy Core v2 / Core Tick v0.9.7** wordt de **Quatt** expliciet als serieuze `COMFORT_BASELOAD` meegenomen. Het actuele Quatt-verbruik wordt uit dezelfde centrale Homey-device-snapshot gelezen en veroorzaakt dus geen extra periodieke device-call. Omdat P1 het huidige Quatt-verbruik al bevat, wordt dat vermogen niet dubbel van de export afgetrokken. In plaats daarvan reserveert Energy Core extra Quatt-rampmarge voordat resterend PV-overschot als flexbudget voor boiler of Tesla beschikbaar komt. Quatt blijft daarbij `OBSERVE_ONLY`: Energy Core stuurt de warmtepomp niet fysiek.

De publieke state bevat daarom naast P1, PV, Tesla en warm water ook een expliciet `energy_budget`, waaronder **flex-exportbudget**, **Quatt-rampreserve** en **discretionair importbudget**. Dezelfde structuur is voorbereid op toekomstige Victron-batterijsteun.

Voor de **Tesla-laadregeling** is de ingestelde modus leidend. Zonder deadline toont de homepage de Tesla als opportunistische belasting/exportbuffer. Zodra een deadline via **Live energiestroom** is ingesteld, toont de homepage de deadline, SOC-doel en maximale laadstroom; de operationele Homey-status zoals wachten op PV, catch-up of Equalizer-blokkade wordt daaronder weergegeven zodra die beschikbaar is.

Na het verstrijken van een Tesla-deadline wordt deze op de homepage niet meer als actief toekomstdoel gepresenteerd. De kaart sluit dan af als **Tesla gereed / doel voor deadline gehaald**, **Tesla deadline gemist**, of **Deadline verstreken · resultaat onzeker/onbekend** wanneer de Homey-runtime door bijvoorbeeld een baseline- of kalibratieafwijking geen betrouwbare eindbeoordeling kan geven. De website bepaalt alleen deze presentatie; Homey blijft bron voor deadline, laadvoortgang en runtime-status.

De **Easee Equalizer** is de harde lokale veiligheidslaag boven de Homey-laadbeslissing. Dit is op 16 augustus 2026 in de praktijk gevalideerd met de oven als extra belasting: Homey bleef 10 A vragen, terwijl Easee de Tesla terugbracht van circa **3×10 A / 7,0 kW** naar **3×8 A / 5,6 kW** toen de fasebelasting opliep tot ongeveer **L1 8 A · L2 21 A · L3 16 A** op de 3×25 A-aansluiting.

De operationele Tesla-laag onderscheidt daarom drie situaties: **normaal**, **Equalizer begrenst** en **Equalizer blokkeert**. Een volledige blokkade wordt pas na een bevestigingsperiode met een actief laadverzoek en vrijwel 0 W werkelijk Tesla-vermogen geclassificeerd, zodat korte start/stop-transiënten niet verkeerd worden gelabeld. Bij zo'n blokkade mag Easee de auto lokaal pauzeren en automatisch weer vrijgeven zodra de zware woningbelasting afneemt. Werkelijk geleverd vermogen blijft leidend voor de resterende laadbehoefte en deadlinebeoordeling.

Oude of uitgeschakelde flowversies worden hier bewust niet als hoofdcomponent getoond. Gebruik de flowdocumentatie en wijzigingshistorie voor versiedetails.
