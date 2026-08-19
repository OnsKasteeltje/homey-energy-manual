# Live energiestroom

Deze pagina maakt de energiearchitectuur **live zichtbaar**. De kaart gebruikt uitsluitend de revision-consistente publieke snapshot van **Energy Core v2**.

<div id="live-energy-flow">
  <p><em>Live energiestroom wordt geladen…</em></p>
</div>

!!! info "Energy Core v2 is leidend"
    De website leest uitsluitend `energy-state-v2.json`. Een websitebezoek veroorzaakt **geen Homey-call**. De actieve `EM v2 | 00 Core Tick | v0.9.8` maakt iedere vijf minuten één centrale device-/Logic-snapshot en gebruikt diezelfde snapshot voor State, Decision, Shadow, Warm Water en publicatie.

## Meetketen

```text
Homey devices + Logic
        ↓
EM v2 | 00 Core Tick | v0.9.8
        ↓
EM2_State (revision N) + fysieke balansguard
        ↓
Decision + Shadow + Warm Water (revision N)
        ↓
EM2_CORE_PUBLISH_V0.9.8 · schema 2.6
        ↓
docs/data/energy-state-v2.json
        ↓
website + aanvullende UI-balansvalidatie
```

De publicatie blijft revision-consistent: State, Decision en Shadow gebruiken dezelfde revision. De onderliggende Homey-devicecapabilities kunnen echter op verschillende momenten door hun apps zijn ververst. Vanaf Core v0.9.8 wordt daarom **vóór State/publicatie** gecontroleerd of P1, PV en de onafhankelijk gemeten bekende verbruikers samen een fysiek mogelijke energiebalans vormen.

## Gemeten versus afgeleid

De energiebalans is:

```text
woningverbruik = PV-productie + netimport - netexport ± batterij
```

Een negatieve P1-waarde betekent export; een positieve P1-waarde import. Rechtstreeks beschikbaar zijn P1, de drie PV-omvormers, Tesla/Easee, boiler en Quatt CIC.

### Balansvalidatie in Core v0.9.8

Core berekent eerst een fysiek woningkandidaat en vergelijkt dit met de onafhankelijk gemeten bekende lasten. De huidige meettolerantie is **75 W**. Een snapshot is ongeldig wanneer het woningkandidaat meer dan 75 W negatief is, of wanneer het zelfs met die tolerantie de bekende gemeten lasten niet kan bevatten.

Bij een ongeldige snapshot publiceert Core:

```text
balance.valid = false
energy_budget.house_load_w = null
energy_budget.other_house_load_w = null
energy_budget.flex_export_budget_w = 0
```

De flexruimte gaat dus **fail-closed** naar 0 W. Een niet-tijdgelijke P1/PV-combinatie kan daardoor niet meer als fictief `Huis 0 W` doorstromen naar de Energy Manager. De publieke snapshot bevat daarnaast `balance.reason`, `physical_house_candidate_w`, `known_measured_load_w`, `residual_w` en `fail_closed_flex_budget` voor diagnose.

De website houdt aanvullend `live-energy-balance-guard-v2.8.53.js` als tweede verdedigingslaag. Bij een ongeldige balans toont de Live-pagina **`Huis —`** en **`Overig —`** met `brondata niet tijdgelijk` / `wacht op sluitende snapshot`, plus `balans ongeldig`. Zodra een volgende snapshot weer sluitend is, worden de waarden automatisch hervat.

De woning splitst op de live kaart in zes parallelle verbruikstakken: Tesla, Boiler, Ruimteverwarming, Wasmachine, Droger en Overig. Er bestaan geen onderlinge energiestromen tussen deze categorieën; iedere pijl loopt rechtstreeks van de woning naar de betreffende verbruikstak.

## Live kaartindeling

De Live-pagina gebruikt vanaf `live-energy-v2.8.60.js` de donkere conceptindeling als primaire renderer. **PV Opwek**, **Batterij** en **Net** staan op de bovenste rij; **Huis** staat centraal daaronder; de zes onafhankelijke verbruikstakken staan op één horizontale rij. De componenten hebben eigen lijniconen zodat de energiestromen sneller visueel te volgen zijn.

Naast de energiestromen wordt ook de fysieke **Net ↔ accu**-koppeling via de AC-bus getoond. Die verbinding is topologisch: zij maakt zichtbaar dat batterij en net elektrisch aan dezelfde woningbus gekoppeld zijn, maar vormt **geen extra meting** en wordt daarom niet dubbel meegenomen in de energiebalans. De kaart vermeldt dit expliciet in de legenda en onderaan het diagram.

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

Alleen een werkelijk gepubliceerd wattage wordt afgetrokken. Een apparaatstatus zoals `RUNNING` zonder betrouwbaar `power_w` is onvoldoende om vermogen te verzinnen. De huidige wasmachine- en drogerintegraties leveren wel apparaatstatus maar geen rechtstreeks `measure_power`; hun `loads.*.power_w` is daarom voorlopig `null`. Zolang dat zo is, blijft hun energie fysiek onderdeel van `Overig`.

## Ruimteverwarming — hybride Quatt

Core v0.9.8 publiceert binnen schema 2.6 een first-class `quatt`-blok met onder meer `power_w`, thermisch vermogen, COP, working modes, warmtevraag en CV-status. Quatt heeft de rol `COMFORT_BASELOAD`, staat `OBSERVE_ONLY` en is niet door deze route bestuurbaar.

De website gebruikt de CV-velden conservatief. `cv_flame = null` betekent **onbekend** en wordt nooit als bewezen `CV uit` geïnterpreteerd. De CV-ketel blijft een status binnen Ruimteverwarming en wordt niet als elektrische stroom getekend.

## Energy budget en Quatt-reserve

Core v0.9.8 behandelt Quatt als observe-only comfortload. Het actuele Quatt-verbruik zit al in de P1/woningbalans en wordt niet nogmaals van export afgetrokken. Voor flexibele lasten wordt alleen een aparte Quatt-rampreserve meegenomen. Bij een ongeldige fysieke balans wordt het flex-exportbudget ongeacht de gemeten export op **0 W** gezet.

Dit beïnvloedt de besluitvorming voor flexibele lasten, maar geeft Homey **geen** recht om de Quatt aan of uit te zetten.

## Actualiteit en Homey-load

De v0.9.8-balansguard gebruikt dezelfde bestaande `Homey.devices.getDevices()`-snapshot. Er is **geen tweede device-poll en geen extra periodieke flow** toegevoegd. De website veroorzaakt eveneens geen Homey-polls en leest alleen de gepubliceerde JSON.

| Laag | Actieve versie | Functie |
|---|---|---|
| Core | `EM v2 | 00 Core Tick | v0.9.8` | één centrale device- en Logic-snapshot per 5 minuten; fysieke balance-gate; State/Decision/Shadow/WW/publicatie |
| Publieke state | schema `2.6` / `EM2_CORE_PUBLISH_V0.9.8` | revision-consistente snapshot met expliciete `balance`, first-class `quatt`, `loads` en fail-closed `energy_budget` |
| Website | `live-energy-v2.8.60.js` + `live-energy-inactive-zero-v2.8.52.js` + `live-energy-balance-guard-v2.8.53.js` | donkere conceptindeling met lijniconen; PV/Batterij/Net boven, Huis centraal; zes parallelle verbruikstakken; expliciete AC-bus-koppeling; tweede fail-safe voor niet-tijdgelijke brondata |

De eerste productievalidatie van v0.9.8 publiceerde schema 2.6 met gelijke State/Decision/Shadow-revision en een sluitende energiebalans. De safety-route bleef `SHADOW`/read-only; er zijn geen fysieke Tesla-, boiler- of Quatt-writes toegevoegd.

Later kan dezelfde kaart zonder architectuurwijziging worden uitgebreid met live Victron ESS-waarden voor batterij laden/ontladen, SOC en eilandbedrijf.

> Laatste update: **19 augustus 2026** — Live kaart overgezet naar de donkere conceptindeling; Core v0.9.8 blijft leidend voor de energiedata en balansvalidatie.
