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

Voor de **Tesla-laadregeling** is de ingestelde modus leidend. Zonder deadline toont de homepage de Tesla als opportunistische belasting/exportbuffer. Zodra een deadline via **Live energiestroom** is ingesteld, toont de homepage de deadline, SOC-doel en maximale laadstroom; de operationele Homey-status zoals wachten op PV, catch-up of Equalizer-blokkade wordt daaronder weergegeven zodra die beschikbaar is.

Na het verstrijken van een Tesla-deadline wordt deze op de homepage niet meer als actief toekomstdoel gepresenteerd. De kaart sluit dan af als **Tesla gereed / doel voor deadline gehaald**, **Tesla deadline gemist**, of **Deadline verstreken · resultaat onzeker/onbekend** wanneer de Homey-runtime door bijvoorbeeld een baseline- of kalibratieafwijking geen betrouwbare eindbeoordeling kan geven. De website bepaalt alleen deze presentatie; Homey blijft bron voor deadline, laadvoortgang en runtime-status.

De **Easee Equalizer** is de harde lokale veiligheidslaag boven de Homey-laadbeslissing. Dit is op 16 augustus 2026 in de praktijk gevalideerd met de oven als extra belasting: Homey bleef 10 A vragen, terwijl Easee de Tesla terugbracht van circa **3×10 A / 7,0 kW** naar **3×8 A / 5,6 kW** toen de fasebelasting opliep tot ongeveer **L1 8 A · L2 21 A · L3 16 A** op de 3×25 A-aansluiting.

`Tesla laden v2.4` onderscheidt daarom drie situaties: **normaal**, **Equalizer begrenst** en **Equalizer blokkeert**. Een volledige blokkade wordt pas na circa vier minuten met een laadverzoek van minimaal 6 A en vrijwel 0 W werkelijk Tesla-vermogen bevestigd, zodat korte start/stop-transiënten niet verkeerd worden gelabeld. Bij zo'n blokkade houdt Homey het laadverzoek bewust actief; Easee mag de auto lokaal pauzeren en geeft hem automatisch weer vrij zodra de zware woningbelasting afneemt. De resterende energie wordt niet als geladen beschouwd en `Latest start` blijft uit werkelijk geleverde kWh worden herberekend. Als de blokkade voortduurt na het uiterste startmoment toont de regeling **Deadline onder druk**; na de deadline kan **Deadline niet haalbaar** worden getoond.

De homepage toont in de Tesla-kaart daarom bijvoorbeeld **Equalizer begrenst · 10 A gevraagd → ~8 A werkelijk** of **Equalizer blokkeert · 10 A gevraagd → 0 A werkelijk · wacht op vrijgave**.

Oude of uitgeschakelde flowversies worden hier bewust niet als hoofdcomponent getoond. Gebruik de flowdocumentatie en wijzigingshistorie voor versiedetails.
