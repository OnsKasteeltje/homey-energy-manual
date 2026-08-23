# Planner Shadow

<div id="planner-shadow" class="planner-shadow" data-source="../data/energy-planner-shadow.json" data-history="../data/energy-day-series-7d.json">
  <div class="ps-banner"><strong>SHADOW — geen fysieke aansturing</strong><span>Deze pagina is uitsluitend observability. Geen Victron-, Easee-, boiler- of andere actuatorwrites.</span></div>
  <div id="ps-status">Plannerdata laden…</div>
</div>

Deze pagina visualiseert de actuele output van `EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW` en rekent voor afgeronde historische dagen een **energetische replay** door met het afgesproken simulatiescenario: MultiPlus-II 48/5000 + 3× Pylontech US5000 (14,4 kWh nominaal).

De replay gebruikt uitsluitend de gemeten P1-netimport/-export uit de bestaande 5-minutenhistorie. Daarmee wordt zichtbaar hoeveel export theoretisch in de accu had kunnen worden opgeslagen en hoeveel latere import daarmee had kunnen worden vermeden. Een eurobesparing wordt pas getoond zodra het tariefmodel expliciet en reproduceerbaar aan de replay is gekoppeld; de pagina verzint geen tarieven.
