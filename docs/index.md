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

Voor de **Tesla-laadregeling** is de ingestelde modus leidend. Zonder deadline toont de homepage de Tesla als opportunistische belasting/exportbuffer. Zodra een deadline via **Live energiestroom** is ingesteld, toont de homepage de deadline, het kWh-doel en de maximale laadstroom; de operationele Homey-status zoals wachten op PV of catch-up wordt daaronder weergegeven zodra die beschikbaar is.

Oude of uitgeschakelde flowversies worden hier bewust niet als hoofdcomponent getoond. Gebruik de flowdocumentatie en wijzigingshistorie voor versiedetails.
