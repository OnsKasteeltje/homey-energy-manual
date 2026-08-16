# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De live kaart gebruikt voor de fysieke energiebalans en bekende apparaten één gezamenlijke Homey-snapshot.

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

Rechtstreeks gemeten zijn **P1**, **PV-productie**, **Tesla-laadvermogen** en **boilervermogen**. Wasmachine en droger leveren via hun Homey-integratie wel een actuele apparaatstatus maar geen afzonderlijk live wattage. Daarvoor wordt bewust geen vermogen geschat.

**Overig verbruik** wordt daarom berekend als:

```text
Overig = woningverbruik - TeslaW - boilerW
```

Het werkelijke verbruik van wasmachine, droger en andere niet afzonderlijk gemeten apparaten zit dus in Overig. Hun status wordt daarnaast informatief als `ACTIEF` of `idle` getoond.

## Grootverbruikers onder Huishouden

- **Tesla / Easee** — werkelijk `measure_power` uit dezelfde snapshot;
- **Boiler** — werkelijk `measure_power` en aan/uit-status uit dezelfde snapshot;
- **Wasmachine — L2, groep 1, aardlek 1** — actuele Homey-status, geen individueel wattage;
- **Droger — L3, groep 2, aardlek 1** — actuele Homey-status, geen individueel wattage;
- **Overig huishouden** — woningverbruik minus afzonderlijk gemeten Tesla en boiler.

## Tesla gevraagd versus werkelijk

De publisher neemt ook de door Homey/Easee gevraagde laadstroom (`target_charger_current`) en de Easee-laadstatus mee. Het werkelijke Tesla-vermogen komt rechtstreeks uit `measure_power`. De Easee Equalizer blijft altijd de harde veiligheidslaag voor de hoofdaansluiting.

## Tesla deadlinebediening

Onder het Tesla/Easee-deel staat de deadline-interface. Bij **Geen deadline** worden de overige invoervelden verborgen. De Tesla wordt dan uitsluitend opportunistisch op werkelijk PV-overschot geladen en kan als flexibele exportbuffer worden gebruikt. Een lage of negatieve prijs alleen veroorzaakt zonder deadline dus geen netladen.

Bij **Deadline actief** worden gevraagd:

- **Gereed uiterlijk** — datum en tijd;
- **Huidige SOC** — actuele percentage uit Tesla-app/auto;
- **Doel-SOC** — gewenste laadpercentage bij de deadline;
- **Max. laadstroom** — bovengrens voor de automatische regeling.

Omdat Tesla-SOC nog niet automatisch beschikbaar is, is **Huidige SOC een handmatige momentopname**. Iedere nieuwe opgeslagen deadline krijgt daarom een nieuwe `requestId`; vanaf v2.3 wordt de geladen-energie teller daarbij altijd opnieuw gestart vanaf de actuele Easee-meterstand.

### Interne kalibratie

De gebruiker voert geen kWh-doel in. De beveiligde Worker zet het SOC-verschil intern om naar benodigde laadenergie. De eerste praktijkkalibratie is **71% → 90%, 3×10 A, circa 7,1 kW, Tesla-ETA 1u35** en levert voorlopig circa **0,59 kWh per procentpunt**. Het afgeleide kWh-doel blijft intern beschikbaar voor voortgang en catch-up.

### Tesla laden v2.3: deadline + forecast + prijs

`Tesla laden v2.3` is de enige automatische Easee-writer. v2.1 en v2.2 zijn uitgeschakeld. De harde deadline blijft altijd leidend; M7 optimaliseert alleen zolang de deadline nog ruimte laat.

De M7-prijssignalen zijn relatief aan **nu**: `M7_Price_Cheap_Next4h=true` betekent dat de huidige stroomprijs lager is dan de volgende vier uur; `M7_Price_Expensive_Next4h=true` betekent dat de huidige prijs hoger is dan de volgende vier uur. `M7_PV_Top4h=true` betekent dat **het huidige uur** één van de vier uren met de hoogste verwachte zonne-opbrengst tussen 09:00 en 18:00 is.

De beslisvolgorde bij een actieve deadline is:

1. **Deadline/catch-up** — vanaf `EV Latest start` wordt op de ingestelde maximale laadstroom geladen, ongeacht prijs of forecast.
2. **Negatieve stroomprijs** — vóór latest-start mag direct op maximaal ingestelde stroom worden geladen.
3. **Actueel PV-overschot** — werkelijk beschikbaar overschot krijgt voorrang en bepaalt de mogelijke laadstroom, met minimaal circa 6 A.
4. **Gunstige prijs nu** — wanneer de huidige prijs lager is dan de komende vier uur en niet tegelijk als duur wordt gemarkeerd, mag op maximaal ingestelde stroom worden geladen.
5. **Gunstig PV-forecastuur nu** — wanneer het huidige uur tot de beste vier forecasturen behoort en de prijs niet ongunstig is, mag met 6 A worden geladen als er nog geen voldoende groot werkelijk overschot is.
6. **Duurder moment / geen aanleiding** — wachten zolang dat de deadline niet in gevaar brengt.

M7 blijft zelf **read-only**. `Tesla laden v2.3` leest alleen `M7_Price_Negative`, `M7_Price_Cheap_Next4h`, `M7_Price_Expensive_Next4h` en `M7_PV_Top4h`. De Easee Equalizer kan de werkelijk geleverde stroom altijd verder begrenzen voor installatiebeveiliging.

### Veilige write-route

De publieke GitHub Pages-site bevat geen Homey- of GitHub-token. De keten is:

```text
Website → Cloudflare Worker → tesla-deadline-command.json → Tesla laden v2.3 → M7-context + Homey Logic → Easee
```

De Worker valideert deadline, huidige SOC, doel-SOC en maximale laadstroom en vereist bij iedere wijziging de persoonlijke control-PIN. De Worker berekent intern `goalKWh`; Homey gebruikt dit voor de resterende energie en `Latest start`.

## Actualiteit

De Tesla-regeling evalueert iedere **2 minuten**. M7 vernieuwt zijn prijs- en PV-context iedere **15 minuten**. De website leest alleen reeds gepubliceerde data en veroorzaakt geen extra polling naar Homey.

Later kan dezelfde kaart worden uitgebreid met de Victron-laag: batterij laden/ontladen, netladen, eilandbedrijf en vermogensgrenzen per fase.
