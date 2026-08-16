# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De live kaart gebruikt voor de fysieke energiebalans en bekende apparaten één gezamenlijke Homey-snapshot.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Centrale snapshot is leidend"
    `Energy Manager State Collector v1.0` bouwt iedere twee minuten één centrale `EM_Runtime_State`. `Live energie publicatie v1.2` leest deze state iedere vijf minuten en publiceert de website-snapshot. De publisher hoeft daardoor niet opnieuw alle Homey-devices uit te lezen.

## Meetketen

```text
Homey devices + Logic
        ↓
Energy Manager State Collector v1.0
        ↓
EM_Runtime_State
        ↓
Live energie publicatie v1.2
        ↓
docs/data/energy-live.json
        ↓
website
```

De collector leest P1, de drie PV-omvormers, Tesla/Easee, Equalizer, boiler en de status van wasmachine en droger in één run. De websitepublisher gebruikt vervolgens die reeds verzamelde toestand.

## Gemeten versus afgeleid

De energiebalans geldt boekhoudkundig als:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

De batterij is momenteel niet actief. Een negatieve P1-waarde betekent export; een positieve P1-waarde import.

Rechtstreeks in Homey beschikbaar zijn **P1**, **PV-productie**, **Tesla-laadvermogen** en **boilervermogen**. Wasmachine en droger leveren via hun Homey-integratie wel een actuele apparaatstatus maar geen afzonderlijk live wattage. Daarvoor wordt bewust geen vermogen geschat.

**Overig verbruik** wordt daarom berekend als:

```text
Overig = woningverbruik - TeslaW - boilerW
```

Het werkelijke verbruik van wasmachine, droger en andere niet afzonderlijk gemeten apparaten zit dus in Overig. Hun status wordt daarnaast informatief als `ACTIEF` of `idle` getoond.

## Grootverbruikers onder Huishouden

- **Tesla / Easee** — werkelijk `measure_power` uit de centrale snapshot;
- **Boiler** — werkelijk `measure_power` en aan/uit-status;
- **Wasmachine — L2, groep 1, aardlek 1** — actuele Homey-status, geen individueel wattage;
- **Droger — L3, groep 2, aardlek 1** — actuele Homey-status, geen individueel wattage;
- **Overig huishouden** — woningverbruik minus afzonderlijk gemeten Tesla en boiler.

## Tesla gevraagd versus werkelijk

De centrale snapshot bevat ook de door Homey/Easee gevraagde laadstroom (`target_charger_current`) en de Easee-laadstatus. Het werkelijke Tesla-vermogen komt uit `measure_power`. De Easee Equalizer blijft altijd de harde veiligheidslaag voor de hoofdaansluiting.

Vanaf **Tesla laden v2.6** wordt een 0-W situatie oorzaakbewust behandeld. Een actief laadverzoek zonder werkelijk laadvermogen wordt niet automatisch als Equalizer-ingreep gelabeld.

De classificatie onderscheidt onder andere:

- **normaal** — werkelijk laadniveau past bij het verzoek;
- **limited** — Easee levert wel stroom, maar minder dan gevraagd;
- **zero pending** — tijdelijke nulvermogenssituatie die nog niet bevestigd is;
- **blocked** — bevestigde blokkade mét gelijktijdige hoge Equalizer-fasebelasting;
- **blocked unknown** — bevestigde blokkade zonder voldoende bewijs dat de Equalizer de oorzaak is.

Een volledige blokkade wordt pas na circa vier minuten bevestigd om korte opstart- of schakelpauzes niet verkeerd te classificeren.

## Tesla deadlinebediening

Onder het Tesla/Easee-deel staat de deadline-interface. Bij **Geen deadline** worden de overige invoervelden verborgen. De Tesla wordt dan opportunistisch gebruikt als flexibele exportbuffer.

Bij **Deadline actief** worden gevraagd:

- gereed uiterlijk;
- huidige SOC;
- doel-SOC;
- maximale laadstroom.

Omdat Tesla-SOC nog niet automatisch beschikbaar is, is **Huidige SOC een handmatige momentopname**. Iedere nieuw opgeslagen opdracht krijgt een nieuwe `requestId`.

### Interne kalibratie en meetbaseline

De beveiligde Worker zet het SOC-verschil intern om naar benodigde laadenergie. De huidige voorlopige kalibratiefactor blijft circa **0,59 kWh per procentpunt**.

Iedere nieuwe request krijgt exact één Easee-meterbaseline. De voortgang wordt daarna bepaald als:

```text
werkelijk geladen sinds SOC-invoer = actuele Easee meter_power - opgeslagen Easee-baseline
```

De baseline blijft immutable voor dezelfde `requestId`.

### Tesla laden v2.6: deadline + forecast + prijs + Equalizer-evidence

`Tesla laden v2.6` is de enige automatische Easee-writer. Oudere v2.x-versies zijn uitgeschakeld. De harde deadline blijft altijd leidend; M7 optimaliseert alleen zolang de deadline nog ruimte laat.

De basisbeslisvolgorde bij een actieve deadline is:

1. **Deadline/catch-up** — vanaf `EV Latest start` wordt op de ingestelde maximale laadstroom gevraagd.
2. **Negatieve stroomprijs** — vóór latest-start mag direct op maximaal ingestelde stroom worden geladen.
3. **Actueel PV-overschot** — werkelijk beschikbaar overschot bepaalt de mogelijke laadstroom.
4. **Gunstige prijs nu** — laden wanneer de huidige prijs relatief gunstig is en de deadline ruimte laat.
5. **Gunstig PV-forecastuur nu** — 6 A wanneer het huidige uur tot de beste forecasturen behoort en prijscontext dit toestaat.
6. **Duurder moment / geen aanleiding** — wachten zolang dat de deadline niet in gevaar brengt.

De Equalizer kan het Homey-verzoek altijd verder beperken. Alleen werkelijk geleverde Easee-kWh telt als voortgang.

Bij een langdurige nulvermogenssituatie gebruikt v2.6 tevens de actuele Equalizer-fasestromen als bewijs. Een hoge fasebelasting kan de status specifiek als Equalizer-blokkade classificeren; zonder die evidence blijft de oorzaak bewust `geblokkeerd/onbekend`.

M7 blijft zelf **read-only**.

### Veilige write-route

De publieke GitHub Pages-site bevat geen Homey- of GitHub-token. De keten is:

```text
Website
  ↓
Cloudflare Worker
  ↓
tesla-deadline-command.json
  ↓
Tesla laden v2.6
  ↓
Homey / Easee
  ↓
Easee Equalizer veiligheidslaag
```

## Actualiteit en Homey-load

De actuele ritmes zijn:

| Functie | Ritme |
|---|---:|
| State Collector v1.0 | 2 min |
| Tesla laden v2.6 | 2 min |
| Shadow v1.6.7 | 5 min |
| Allocator Shadow v0.2.4 | 5 min |
| Live energie publicatie v1.2 | 5 min |
| M7 context | 15 min |
| GitHub status sync v1.4 | 30 min |

De website zelf pollt Homey niet. De live publisher doet nog steeds één GitHub-publicatie per vijf minuten, maar gebruikt vanaf v1.2 de centrale `EM_Runtime_State` en veroorzaakt daardoor geen extra volledige device-read.

Later kan dezelfde kaart worden uitgebreid met de Victron-laag: batterij laden/ontladen, netladen, eilandbedrijf en vermogensgrenzen per fase.

> Laatste update: **16 augustus 2026** — centrale state collector en load-geoptimaliseerde publicatiearchitectuur actief; Tesla-documentatie bijgewerkt naar v2.6.
