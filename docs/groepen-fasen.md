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
| Elektrisch fornuis / kookplaat | Nog te bepalen | Nog te bepalen | Nog te bepalen | Afzonderlijke validatie nodig. |
| Waterkoker | **L2** | Nog te bepalen | Volgt uit groep | Aan/uit-test: circa 2,15 kW extra op L2. |
| Koffiezetapparaat | Nog te bepalen | Nog te bepalen | Nog te bepalen | Fasekoppeling nog niet betrouwbaar bevestigd. |
| Quooker | Nog te bepalen | Nog te bepalen | Nog te bepalen | Nog te valideren. |
| Quatt warmtepomp / CV-installatie | Nog te bepalen | Nog te bepalen | Nog te bepalen | Nog te valideren. |
| SolarEdge SE3680H | **Wordt gemonitord** | Nog te bepalen | Volgt uit groep | Automatische fasecorrelatie actief. |
| GoodWe GW4200D-NS | **Wordt gemonitord** | Nog te bepalen | Volgt uit groep | Automatische fasecorrelatie actief. |
| GoodWe GW2000-XS | **Wordt gemonitord** | Nog te bepalen | Volgt uit groep | Automatische fasecorrelatie actief. |
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
- boiler en waterkoker zijn aan L2 gekoppeld.

De vaatwasser is beperkt tot twee kandidaten: **groep 5 (aardlek 2)** of **groep 12 (aardlek 4)**.

## Automatische PV-fasemonitor

De 24-uurs fasemeting wordt gepubliceerd door de actieve Homey Advanced Flow **`Fase 24h publicatie v1.4`**. Iedere **5 minuten** wordt één tijd-consistente snapshot gemaakt van P1 L1/L2/L3, totaal P1, de drie PV-omvormers en de relevante live belastingen. De laatste 24 uur worden gepubliceerd naar `docs/data/pv-phase-24h.json`.

De analyse in v1.4 is **tijdgebaseerd** en rekent niet met een vast aantal samples. Voor de omvormer-correlatie worden de werkelijke observatieduur en timestamps gebruikt; confidence kan vanaf 60 minuten naar middel en vanaf 120 minuten naar hoog, mits ook aan de correlatie- en margecriteria wordt voldaan. Start/stop-events van wasmachine en droger worden beoordeeld met meetpunten binnen een tijdvenster van circa **±7 minuten**. Daardoor blijft de analyse correct wanneer de meetfrequentie later opnieuw wordt aangepast.

De status van een omvormer wordt pas naar **Bevestigd** gewijzigd wanneer de correlatie voldoende eenduidig is of aanvullend met een gecontroleerde test is gevalideerd.

## Live 24-uurs fase-analyse

<div id="pv-phase-24h">
  <p><em>Live fase-analyse wordt geladen…</em></p>
</div>

!!! note "Interpretatie"
    **Beste fase** is de fase met de sterkste gemeten samenhang. **Confidence** is een indicatie op basis van de correlatiescore, de marge ten opzichte van nummer twee en voldoende werkelijke observatieduur. Het aantal samples is alleen informatief; timestamps bepalen de analyse. Een automatische uitkomst wordt niet zonder aanvullende beoordeling als fysiek bevestigd beschouwd.

## Meetmethode voor fase en groep

Voor een betrouwbare fasekoppeling wordt bij voorkeur één apparaat tegelijk getest. Voor PV-omvormers gebruiken we daarnaast automatische correlatie. Een exact groepnummer wordt pas als bevestigd gemarkeerd wanneer de koppeling fysiek is vastgesteld via een gecontroleerde uitschakeltest of fysieke verificatie.

!!! warning "Veiligheid"
    Schakel alleen installatieautomaten met de normale bedieningshendel. Verwijder geen afdekkappen en raak geen bedrading of spanningsvoerende delen aan.

## Fasebelasting

Wasmachine, boiler en waterkoker zijn aan L2 gekoppeld. Vooral boiler en waterkoker kunnen samen ongeveer 4,1 kW toevoegen. De droger is aan L3 gekoppeld. Dit blijft relevant voor toekomstige fasebalancering en de voorbereiding van de Victron-opstelling.

## Beheerregel

Nieuwe betrouwbare inzichten over **fase-, groep- of aardlekindeling** worden direct op deze pagina verwerkt. Onzekere koppelingen blijven expliciet als onzeker gemarkeerd; er wordt niet tussen alternatieven gegokt.

## Open vervolgstappen

De vaatwasser moet nog definitief tussen **groep 5 en groep 12** worden onderscheiden. Daarnaast blijven onder meer kookplaat/fornuis, koffiezetapparaat, Quooker en Quatt qua exacte groep/fase nog open. De exacte groepen van boiler en waterkoker moeten eveneens nog fysiek worden gekoppeld.

> Laatste inhoudelijke update: 16 augustus 2026. Fase 24h publicatie v1.4 gebruikt een 5-minutenmeetinterval en tijdgebaseerde analyse; groepen 1 en 2 zijn gekoppeld aan wasmachine en droger; aardlekstructuur 1–4 voor groepen 1–13 is vastgelegd; vaatwasser beperkt tot groep 5 of 12.
