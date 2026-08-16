# Energiehistorie

<div id="energy-history-dashboard">
  <p><em>Energiehistorie wordt geladen…</em></p>
</div>

!!! info "Datakwaliteit"
    **Dag** gebruikt de bestaande 24-uurs fasepublicatie voor PV-productie, woningverbruik en netimport/-export. **Week** en **Maand** gebruiken de compacte dagelijkse historie die de Energy Manager al publiceert. De historische dataset wordt vanaf nu verder opgebouwd; oudere perioden kunnen daarom nog gedeeltelijk zijn.

!!! note "Opslag voorbereid"
    De interface bevat nu al **Accu geladen** en **Accu ontladen**. Zolang er nog geen Victron-opslagmeting beschikbaar is, worden deze waarden bewust als **0 / nog geen opslagmeting** weergegeven. Er wordt geen fictieve batterijdata berekend.

## Berekeningsprincipes

Voor de huidige AC-gekoppelde situatie zonder gemeten batterij wordt op dagniveau gerekend met:

```text
PV-productie = SolarEdge + GoodWe GW4200D-NS + GoodWe GW2000-XS
Woningverbruik = PV-productie + P1-netvermogen
Netimport = max(P1, 0)
Netexport = max(-P1, 0)
Direct eigen PV-verbruik ≈ min(PV-productie, woningverbruik)
```

De grafiek toont vermogenswaarden door de tijd; de kengetallen erboven worden uit de meetreeks naar kWh geïntegreerd. De huidige meetfrequentie is circa twee minuten voor de 24-uurs fasepublicatie.

## Activiteitstijdlijn

Waar de bestaande baseline voldoende statusinformatie bevat, toont de pagina gebeurtenissen zoals wasmachine/droger actief of idle en boilerstatusovergangen. Dit helpt pieken in de energiegrafiek te verklaren zonder individueel apparaatvermogen te verzinnen.
