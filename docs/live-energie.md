# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. Sinds **Fase 24h publicatie v1.3** gebruikt de live kaart voor de fysieke energiebalans en bekende apparaten één gezamenlijke **2-minuten Homey-snapshot**.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Eén meetmoment is leidend"
    P1, de drie PV-omvormers, Tesla-laadvermogen, boilervermogen en de status van wasmachine en droger worden in dezelfde HomeyScript-run gelezen en met één timestamp gepubliceerd. De website hoeft deze waarden daardoor niet meer uit verschillende publicatiemomenten samen te voegen.

## Gemeten versus afgeleid

De energiebalans geldt boekhoudkundig als:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

De batterij is momenteel niet actief. Een negatieve P1-waarde betekent export; een positieve P1-waarde import.

Rechtstreeks gemeten in dezelfde 2-minuten snapshot zijn **P1**, **PV-productie**, **Tesla-laadvermogen** en **boilervermogen**. Wasmachine en droger leveren via hun Homey-integratie wel een actuele apparaatstatus maar geen afzonderlijk live wattage. Daarvoor wordt bewust geen vermogen geschat.

**Overig verbruik** wordt daarom berekend als:

```text
Overig = woningverbruik - TeslaW - boilerW
```

Het werkelijke verbruik van wasmachine, droger en andere niet afzonderlijk gemeten apparaten zit dus in Overig. Hun status wordt daarnaast informatief als `ACTIEF` of `idle` getoond.

## Waarom deze wijziging?

De eerdere pagina combineerde een ongeveer 2-minuten P1/PV-publicatie met een tragere Energy Manager-shadowpublicatie. Wanneer de Tesla tussen die meetmomenten begon of stopte met laden, kon meerdere kW tijdelijk ten onrechte onder **Overig verbruik** verschijnen. Een daaropvolgende veiligheidswijziging verborg bij timestampverschillen de hele apparaatlaag; dat voorkwam verkeerde getallen maar was praktisch onvoldoende bruikbaar.

De structurele oplossing is nu dat de bestaande 2-minutenpublisher zelf de live apparaatwaarden meeneemt. Daardoor hebben P1, PV, Tesla en boiler exact hetzelfde meetmoment.

## Grootverbruikers onder Huishouden

- **Tesla / Easee** — werkelijk `measure_power` uit dezelfde snapshot;
- **Boiler** — werkelijk `measure_power` en aan/uit-status uit dezelfde snapshot;
- **Wasmachine — L2, groep 1, aardlek 1** — actuele Homey-status, geen individueel wattage;
- **Droger — L3, groep 2, aardlek 1** — actuele Homey-status, geen individueel wattage;
- **Overig huishouden** — woningverbruik minus afzonderlijk gemeten Tesla en boiler.

## Tesla gevraagd versus werkelijk

De publisher neemt ook de door Homey/Easee gevraagde laadstroom (`target_charger_current`) en de Easee-laadstatus mee. Het werkelijke Tesla-vermogen komt rechtstreeks uit `measure_power`. De website kan daardoor gevraagd versus werkelijk binnen hetzelfde meetmoment vergelijken. De Easee Equalizer blijft de harde veiligheidslaag voor de hoofdaansluiting.

## Tesla deadlinebediening

Onder het Tesla/Easee-deel staat een compacte deadline-interface. De keuze tussen **Geen deadline** en **Deadline actief** staat bewust bovenaan.

Bij **Geen deadline** worden de overige invoervelden verborgen. De Tesla blijft dan opportunistisch laden en kan als flexibele exportbuffer worden gebruikt wanneer de Energy Manager dat opportuun vindt.

Bij **Deadline actief** worden vanaf v2.8.16 de voor de gebruiker natuurlijke waarden gevraagd:

- **Gereed uiterlijk** — datum en tijd;
- **Huidige SOC** — het actuele percentage dat je uit de Tesla-app/auto overneemt;
- **Doel-SOC** — het gewenste laadpercentage bij de deadline;
- **Max. laadstroom** — bovengrens voor de automatische regeling.

Omdat de Tesla-SOC nog niet automatisch beschikbaar is, is **Huidige SOC een handmatige momentopname**. De website bewaart daarom ook het tijdstip waarop die SOC werd ingevoerd. Voor een nieuwe of gewijzigde deadline moet de huidige SOC opnieuw worden gecontroleerd.

### Interne kalibratie

De gebruiker hoeft geen kWh-doel meer in te voeren. De beveiligde Worker zet het verschil tussen huidige SOC en doel-SOC intern om naar benodigde laadenergie. De eerste praktijkkalibratie is gebaseerd op het gemeten punt **71% → 90%, 3×10 A, circa 7,1 kW, Tesla-ETA 1u35**. Dit geeft voorlopig circa **0,59 kWh per procentpunt**.

De afgeleide kWh blijft intern bestaan omdat `Tesla laden v2.1` daarmee de resterende energie en het uiterste catch-upmoment berekent. Op de gebruikersinterface blijft het doel echter in procenten weergegeven. Nieuwe praktijkmetingen kunnen de kalibratiefactor later verfijnen zonder de bediening te veranderen.

### Veilige write-route

De publieke GitHub Pages-site bevat geen Homey- of GitHub-token. De keten is:

```text
Website → Cloudflare Worker → tesla-deadline-command.json → Tesla laden v2.1 → Homey Logic → Easee
```

De Worker valideert deadline, huidige SOC, doel-SOC en maximale laadstroom en vereist bij iedere wijziging een persoonlijke control-PIN. De PIN wordt niet op de website opgeslagen. De Worker berekent vervolgens het interne `goalKWh` en schrijft zowel de SOC-invoer als die afgeleide waarde in de opdracht. `Tesla laden v2.1` kan daardoor ongewijzigd de bestaande energieberekening en catch-up-logica blijven uitvoeren.

## Actualiteit

De Homey-flow draait iedere **2 minuten**. De website ververst eveneens iedere 2 minuten en markeert de meetset als vertraagd wanneer de laatste snapshot ouder dan 5 minuten is. Dit veroorzaakt geen extra polling richting Homey: de browser leest alleen de reeds naar GitHub gepubliceerde dataset.

Later kan dezelfde kaart worden uitgebreid met de Victron-laag: batterij laden/ontladen, netladen, eilandbedrijf en vermogensgrenzen per fase.
