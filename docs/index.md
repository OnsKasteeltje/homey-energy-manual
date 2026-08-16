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

Voor de **Tesla-laadregeling** is de ingestelde modus leidend. Zonder deadline toont de homepage de Tesla als opportunistische belasting/exportbuffer. Zodra een deadline via **Live energiestroom** is ingesteld, toont de homepage de deadline, SOC-doel en maximale laadstroom; de operationele Homey-status zoals wachten op PV of catch-up wordt daaronder weergegeven zodra die beschikbaar is.

De **Easee Equalizer** is de harde lokale veiligheidslaag boven de Homey-laadbeslissing. Dit is op 16 augustus 2026 in de praktijk gevalideerd met de oven als extra belasting: Homey bleef 10 A vragen, terwijl Easee de Tesla terugbracht van circa **3×10 A / 7,0 kW** naar **3×8 A / 5,6 kW** toen de fasebelasting opliep tot ongeveer **L1 8 A · L2 21 A · L3 16 A** op de 3×25 A-aansluiting. De homepage toont daarom voortaan gevraagd versus werkelijk laadniveau en markeert een waarschijnlijke Equalizer-begrenzing wanneer die zichtbaar is.

Oude of uitgeschakelde flowversies worden hier bewust niet als hoofdcomponent getoond. Gebruik de flowdocumentatie en wijzigingshistorie voor versiedetails.
