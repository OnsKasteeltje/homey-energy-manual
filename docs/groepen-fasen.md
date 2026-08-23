# Groepen & fasen

Deze pagina is een **levend overzicht van de elektrische indeling van de woning**. Het doel is om per apparaat vast te leggen op welke fase, groep/automaat en aardlekschakelaar het is aangesloten. Fase, groep en aardlek worden bewust als drie afzonderlijke eigenschappen bijgehouden.

## Betrouwbaarheidsniveaus

| Status | Betekenis |
|---|---|
| **Bevestigd** | De fase, groep of aardlekindeling is in een afzonderlijke praktijktest of fysieke controle duidelijk vastgesteld. |
| **Waarschijnlijk** | De koppeling past bij het gemeten gedrag of de groepenkast, maar is nog niet afzonderlijk gevalideerd. |
| **Open** | Nog onvoldoende informatie om de eigenschap toe te wijzen. |

!!! info "Fase is niet hetzelfde als groep of aardlek"
    De P1-meter meet L1, L2 en L3 aan de hoofdaansluiting. Een groepnummer identificeert de installatieautomaat. De aardlekschakelaar geeft aan onder welke aardlekbeveiliging die groep valt. Deze drie gegevens mogen niet door elkaar worden gehaald.

## Aardlek- en groepenstructuur

| Aardlekschakelaar | Beveiligde groepen | Status |
|---|---:|---|
| **Aardlek 1** | **1–3** | **Bevestigd** |
| **Aardlek 2** | **4–7** | **Bevestigd** |
| **Aardlek 3** | **8–10** | **Bevestigd** |
| **Aardlek 4** | **11–13** | **Bevestigd** |

**Groep 14** is apart bevestigd als de **3-polige B16-schuurvoeding**.

## Huidige indeling

| Apparaat / installatie | Fase | Groep / automaat | Aardlek | Status / onderbouwing |
|---|---:|---:|---:|---|
| Wasmachine | **L2** | **Groep 1** | **Aardlek 1** | **Bevestigd.** Fase uit testwas; groep fysiek vastgesteld. |
| Droger | **L3** | **Groep 2** | **Aardlek 1** | **Bevestigd.** Fase uit droogtest; groep fysiek vastgesteld. |
| Tesla / Easee-lader | **L1 + L2 + L3** | Laadgroep nog te documenteren | Nog te bepalen | 3-fase verbruiker; afzonderlijke fasewaarden zichtbaar in Homey. |
| Elektrische boiler | **L2** | Nog te bepalen | Volgt uit groep | Verwarmingsbelasting circa 1,93–2,13 kW verschijnt op L2. |
| Vaatwasser | Nog te bepalen | **Groep 5 óf groep 12** | **Aardlek 2 óf 4** | **Nog te bevestigen.** Bij groep 5 hoort aardlek 2; bij groep 12 aardlek 4. |
| **ATAG oven** | **L3 (kandidaat)** | Nog te bepalen | Nog te bepalen | **Waarschijnlijk.** Rond de ATAG-melding *Snel voorverwarmen klaar* op 18-08 om 18:21 is vlak ervoor een duidelijke extra belasting op L3 zichtbaar (circa 1,3–1,5 kW gemiddeld per 5 min), die na het meldmoment afneemt. Nog valideren met extra start/stopmomenten. |
| Elektrische kookplaat / fornuis | Nog te bepalen | Nog te bepalen | Nog te bepalen | Afzonderlijke validatie nodig; niet gelijkgesteld aan de ATAG-oven. |
| Waterkoker | **L2** | Nog te bepalen | Volgt uit groep | Aan/uit-test: circa 2,15 kW extra op L2. |
| Koffiezetapparaat | Nog te bepalen | Nog te bepalen | Nog te bepalen | Fasekoppeling nog niet betrouwbaar bevestigd. |
| Quooker | Nog te bepalen | Nog te bepalen | Nog te bepalen | Nog te valideren. |
| Quatt warmtepomp / CV-installatie | Nog te bepalen | Nog te bepalen | Nog te bepalen | Nog te valideren. |
| SolarEdge SE3680H | **L3** | Nog te bepalen | Volgt uit groep | **Bevestigd / HIGH.** Fysieke aan/uit-test op 22-08-2026 met directe P1-fasewaarden. |
| GoodWe GW4200D-NS | **L2** | Nog te bepalen | Volgt uit groep | **Bevestigd / HIGH.** Fysieke aan/uit-test op 22-08-2026 met directe P1-fasewaarden. |
| GoodWe GW2000-XS | **L3** | Nog te bepalen | Volgt uit groep | **Bevestigd / HIGH.** Fysieke aan/uit-test op 22-08-2026 met directe P1-fasewaarden. |
| Schuurvoeding | **L1 + L2 + L3** | **Groep 14, 3-polig B16** | Apart / n.v.t. in schema 1–13 | **Bevestigd.** Fysiek in de meterkast gecontroleerd. |

## Wat is nu al zeker?

- **Groep 1 → wasmachine → aardlek 1 → L2**;
- **Groep 2 → droger → aardlek 1 → L3**;
- **aardlek 1 → groepen 1–3**;
- **aardlek 2 → groepen 4–7**;
- **aardlek 3 → groepen 8–10**;
- **aardlek 4 → groepen 11–13**;
- **groep 14 → 3-polige B16-schuurvoeding**;
- Tesla/Easee is een 3-fase verbruiker;
- boiler en waterkoker zijn aan L2 gekoppeld;
- **GoodWe GW4200D-NS → L2**;
- **SolarEdge SE3680H → L3**;
- **GoodWe GW2000-XS → L3**;
- **L1 heeft geen PV-omvormer**.

De vaatwasser is beperkt tot twee kandidaten: **groep 5 (aardlek 2)** of **groep 12 (aardlek 4)**. De **ATAG-oven heeft L3 als kandidaatfase**, maar is nog niet als bevestigd aangemerkt.

## Gevalideerde PV-fasemapping

Op **22 augustus 2026** zijn de drie PV-omvormers afzonderlijk fysiek aan/uit geschakeld terwijl de **directe P1-fasewaarden** zijn gevolgd. De fysieke schakeling was ground truth; vertraagde Homey-/omvormerwaarden zijn niet gebruikt als primaire fase-identificatie.

| Omvormer | Fase | Validatie |
|---|---:|---|
| SolarEdge SE3680H-RW000BEN4 | **L3** | **VALIDATED / HIGH** |
| GoodWe GW4200D-NS | **L2** | **VALIDATED / HIGH** |
| GoodWe GW2000-XS | **L3** | **VALIDATED / HIGH** |

Daarmee geldt fysiek: **L1 geen PV-omvormer, L2 de grote GoodWe, L3 SolarEdge + kleine GoodWe**. De daardoor zichtbare fase-onbalans bij PV-productie is verklaarbaar en is op zichzelf geen storing.

## Automatische PV-fasemonitor

De 24-uurs fasemeting blijft beschikbaar als **diagnostiek en historische controle**, maar is niet langer nodig om de drie PV-fasen te bepalen: die zijn inmiddels fysiek bevestigd. De monitor publiceert tijd-consistente snapshots van P1 L1/L2/L3, totaal P1 en de drie PV-omvormers naar `docs/data/pv-phase-24h.json`.

## Live 24-uurs fase-analyse

<div id="pv-phase-24h">
  <p><em>Live fase-analyse wordt geladen…</em></p>
</div>

!!! note "Interpretatie"
    De live correlatie is nu aanvullend diagnostisch. Voor de drie PV-omvormers is de fysieke aan/uit-test van 22-08-2026 leidend.

## Meetmethode voor fase en groep

Voor een betrouwbare fasekoppeling wordt bij voorkeur één apparaat tegelijk getest. Voor PV-omvormers is de fase inmiddels bevestigd met een gecontroleerde fysieke uitschakeltest en directe P1-fasewaarden. Een exact groepnummer wordt pas als bevestigd gemarkeerd wanneer de koppeling fysiek is vastgesteld via een gecontroleerde uitschakeltest of fysieke verificatie.

### ATAG-oven: kandidaatfase L3

Voor de oven gebruiken we de ATAG-appmeldingen als externe tijdmarkeringen en vergelijken die met de historische P1-fasereeksen. Op **18 augustus 2026 om 18:21** meldde de oven dat snel voorverwarmen gereed was. In de 5-minutenmetingen is op **L3** vlak daarvoor een extra positieve belasting van grofweg **1,3–1,5 kW** zichtbaar; na het meldmoment neemt deze belasting duidelijk af. L1 en L2 laten rond hetzelfde markeringsmoment geen vergelijkbaar patroon zien.

Dit is voldoende om **L3 als kandidaatfase / waarschijnlijk** te registreren, maar nog niet om de fase als bevestigd te behandelen. Voor bevestiging worden meerdere onafhankelijke oven-start/stop- of voorverwarmmomenten vergeleken, bij voorkeur zonder gelijktijdige grote onbekende verbruikers.

!!! warning "Veiligheid"
    Schakel alleen installatieautomaten met de normale bedieningshendel. Verwijder geen afdekkappen en raak geen bedrading of spanningsvoerende delen aan.

## Fasebelasting

Wasmachine, boiler en waterkoker zijn aan L2 gekoppeld. Vooral boiler en waterkoker kunnen samen ongeveer 4,1 kW toevoegen. De **GoodWe GW4200D-NS produceert eveneens op L2**. De droger is aan L3 gekoppeld; daarnaast produceren **SolarEdge SE3680H en GoodWe GW2000-XS beide op L3**. De ATAG-oven is voorlopig eveneens een **L3-kandidaat**. Dit fasebeeld is relevant voor de voorbereiding van de Victron-opstelling; de single-phase MultiPlus is daarom in de hardwarebaseline op **L1** voorzien.

## Beheerregel

Nieuwe betrouwbare inzichten over **fase-, groep- of aardlekindeling** worden direct op deze pagina verwerkt. Onzekere koppelingen blijven expliciet als onzeker gemarkeerd; er wordt niet tussen alternatieven gegokt.

## Open vervolgstappen

De vaatwasser moet nog definitief tussen **groep 5 en groep 12** worden onderscheiden. De **ATAG-oven moet met aanvullende app-gemarkeerde start/stop- of voorverwarmmomenten worden gevalideerd voordat L3 naar Bevestigd kan**. Daarnaast blijven onder meer kookplaat/fornuis, koffiezetapparaat, Quooker en Quatt qua exacte groep/fase nog open. De exacte groepen van boiler, waterkoker en de drie PV-omvormers moeten eveneens nog fysiek aan groep/automaat worden gekoppeld.

> Laatste inhoudelijke update: 23 augustus 2026. De fysiek gevalideerde PV-fasemapping van 22 augustus is verwerkt: **GoodWe GW4200D-NS = L2; SolarEdge SE3680H = L3; GoodWe GW2000-XS = L3; L1 heeft geen PV-omvormer**.
