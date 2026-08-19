# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De kaart gebruikt uitsluitend de revision-consistente publieke snapshot van **Energy Core v2**.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend"
    De website leest uitsluitend `energy-state-v2.json`. Een websitebezoek veroorzaakt **geen Homey-call**. De actieve `EM v2 | 00 Core Tick | v0.9.7` maakt iedere vijf minuten één centrale device-/Logic-snapshot en gebruikt diezelfde snapshot voor State, Decision, Shadow, Warm Water en publicatie.

## Meetketen

```text
Homey devices + Logic
        ↓
EM v2 | 00 Core Tick | v0.9.7
        ↓
EM2_State (revision N)
        ↓
Decision + Shadow + Warm Water (revision N)
        ↓
EM2_CORE_PUBLISH_V0.9.7 · schema 2.5
        ↓
docs/data/energy-state-v2.json
        ↓
website + balansvalidatie
```

De publicatie blijft revision-consistent: State, Decision en Shadow gebruiken dezelfde revision. De onderliggende Homey-devicecapabilities kunnen echter op verschillende momenten door hun apps zijn ververst. Daarom valideert de Live-pagina aanvullend of P1, PV, batterij en bekende verbruikers samen een fysiek mogelijke energiebalans vormen.

## Gemeten versus afgeleid

De energiebalans is:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

Een negatieve P1-waarde betekent export; een positieve P1-waarde import. Rechtstreeks beschikbaar zijn P1, de drie PV-omvormers, Tesla/Easee, boiler en Quatt CIC.

### Balansvalidatie

De Live-pagina accepteert een afgeleid woningvermogen alleen wanneer het berekende woningvermogen niet negatief is en ten minste de onafhankelijk gemeten bekende verbruikers kan bevatten, met een kleine meettolerantie. Een moment waarop bijvoorbeeld P1 al een nieuwe exportwaarde heeft maar één PV-omvormer nog zijn vorige waarde rapporteert, wordt daardoor niet meer stilzwijgend naar `Huis 0 W` afgerond.

Bij zo'n niet-tijdgelijke snapshot toont de site **`Huis —`** en **`Overig —`** met de melding `brondata niet tijdgelijk` / `wacht op sluitende snapshot`. Ook verschijnt `balans ongeldig`. Zodra de volgende snapshot weer fysiek sluitend is, worden Huis en Overig automatisch opnieuw berekend uit de fysieke energiebalans.

De woning splitst op de live kaart in zes parallelle verbruikstakken: Tesla, Boiler, Ruimteverwarming, Wasmachine, Droger en Overig. Er bestaan geen onderlinge energiestromen tussen deze categorieën; iedere pijl loopt rechtstreeks van de woning naar de betreffende verbruikstak.

### Overig verbruik

`Overig` is nadrukkelijk het **residu na alle individueel bekende vermogens**:

```text
Overig = woningverbruik
       - TeslaW
       - boilerW
       - QuattW
       - wasmachineW
       - drogerW
       - vaatwasserW
       - QuookerW
       - overige toekomstige individueel gemeten loads
```

Alleen een werkelijk gepubliceerd wattage wordt afgetrokken. Een apparaatstatus zoals `RUNNING` zonder betrouwbaar `power_w` is onvoldoende om vermogen te verzinnen. De huidige wasmachine- en drogerintegraties leveren wel apparaatstatus maar geen rechtstreeks `measure_power`; hun `loads.*.power_w` is daarom voorlopig `null`. Zolang dat zo is, blijft hun energie fysiek onderdeel van `Overig`, maar de site kan bij actieve status expliciet aangeven dat een bekende actieve load nog niet watt-nauwkeurig is uitgesplitst.

Dit voorkomt twee fouten tegelijk: bekende gemeten loads worden niet dubbel in `Overig` geteld, en niet-gemeten loads worden niet met een fictieve schatting van het residu afgetrokken.

## Ruimteverwarming — hybride Quatt

Core v0.9.7 publiceert binnen schema 2.5 een first-class `quatt`-blok met onder meer `power_w`, thermisch vermogen, COP, working modes, warmtevraag en CV-status. Quatt heeft de rol `COMFORT_BASELOAD`, staat `OBSERVE_ONLY` en is niet door deze route bestuurbaar.

De website gebruikt de CV-velden conservatief. `cv_flame = null` betekent **onbekend** en wordt nooit als bewezen `CV uit` geïnterpreteerd. De CV-ketel blijft een status binnen Ruimteverwarming en wordt niet als elektrische stroom getekend.

## Energy budget en Quatt-reserve

Core v0.9.7 behandelt Quatt als observe-only comfortload. Het actuele Quatt-verbruik zit al in de P1/woningbalans en wordt niet nogmaals van export afgetrokken. Voor flexibele lasten wordt alleen een aparte Quatt-rampreserve meegenomen. Dit beïnvloedt de besluitvorming voor flexibele lasten, maar geeft Homey **geen** recht om de Quatt aan of uit te zetten.

## Actualiteit en Homey-load

De Live-pagina veroorzaakt geen extra Homey-polls. De balansguard werkt uitsluitend op dezelfde reeds gepubliceerde JSON-snapshot. Daarmee blijft één centrale Core-device-read per vijf minuten de bron voor de site.

| Laag | Actieve versie | Functie |
|---|---|---|
| Core | `EM v2 | 00 Core Tick | v0.9.7` | één centrale device- en Logic-snapshot per 5 minuten; State/Decision/Shadow/WW/publicatie |
| Publieke state | schema `2.5` / `EM2_CORE_PUBLISH_V0.9.7` | revision-consistente snapshot met first-class `quatt`, `loads` en `energy_budget` |
| Website | `live-energy-v2.8.51.js` + `live-energy-inactive-zero-v2.8.52.js` + `live-energy-balance-guard-v2.8.53.js` | parallelle verbruikstakken; fail-safe validatie van niet-tijdgelijke P1/PV-bronnen; `Overig` als residu na beschikbare individuele wattages |

De live kaart toont revision en bron-timestamp expliciet. De status `actueel/vertraagd` komt uit dezelfde freshness-regels als de EM v2 health-indicator.

Later kan dezelfde kaart zonder architectuurwijziging worden uitgebreid met live Victron ESS-waarden voor batterij laden/ontladen, SOC en eilandbedrijf.

> Laatste update: **19 augustus 2026** — fail-safe energiebalans toegevoegd. Een fysiek onmogelijke P1/PV-combinatie wordt niet meer als `Huis 0 W` getoond, maar expliciet als niet-tijdgelijke brondata.
