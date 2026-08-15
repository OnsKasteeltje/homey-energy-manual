# Energie Manager PV

**Modus:** Shadow / read-only  
**Homey-status:** 🟢 Actief  
**Actieve flow:** `Energie Manager PV - Shadow Mode v1.6.4`  
**Voorgaande flow:** `Energie Manager PV - Shadow Mode` — 🔴 Inactief

De actuele v1.6.4-flow is in Homey ingeschakeld. De flow werkt volledig in shadow/read-only-modus en stuurt geen Tesla, laadpaal of boiler aan. Hij observeert en berekent de gewenste energiesturing, houdt de boilerstatus en boilercycli bij en publiceert meetdata naar GitHub.

## Berekening

```text
PV beschikbaar = max(0, -P1 + werkelijk Tesla-vermogen + werkelijk boilervermogen)
```

## Tesla-prioriteit

| Beschikbaar PV | Shadow-doel |
|---:|---:|
| < 4.140 W | 0 A |
| 4.140–4.829 W | 6 A |
| 4.830–5.519 W | 7 A |
| 5.520–6.209 W | 8 A |
| 6.210–6.899 W | 9 A |
| 6.900–7.589 W | 10 A |
| ≥ 7.590 W | 11 A |

Boiler wordt alleen toegestaan als na Tesla-reservering minimaal circa **2,1 kW** resteert.

## Easee Equalizer als harde veiligheidslaag

De **Easee Equalizer blijft altijd leidend voor lokale load balancing** van de laadpaal. De Energy Manager mag een begrenzing of laadpauze van de Equalizer nooit proberen te overrulen.

De regelhiërarchie is:

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer load balancing
          ↓
Victron grid/batterijregeling (later)
          ↓
Homey Energy Manager / flex-orchestratie
          ↓
Tesla / boiler
```

Wanneer bijvoorbeeld tijdens Tesla-laden een oven of andere grote belasting wordt ingeschakeld, mag de Equalizer de Tesla-laadstroom zelfstandig verlagen of het laden pauzeren om overbelasting te voorkomen.

### Gevraagd versus werkelijk Tesla-vermogen

De toekomstige actieve Energy Manager maakt expliciet onderscheid tussen:

- **gevraagde laadstroom / doelvermogen** vanuit Homey;
- **werkelijke laadstroom / werkelijk vermogen** dat Easee na load balancing daadwerkelijk levert.

Vervolgbeslissingen worden gebaseerd op **werkelijk Tesla-vermogen en actuele P1/fasebelasting**, niet alleen op de door Homey gevraagde laadstroom.

Voorbeeld:

```text
Homey vraagt 10 A
        ↓
Equalizer begrenst naar 6 A
        ↓
Energy Manager accepteert 6 A als actuele werkelijkheid
        ↓
geen herhaalde poging om onmiddellijk weer 10 A af te dwingen
```

### Geen foutieve herverdeling naar boiler

Wanneer de Equalizer Tesla terugregelt, wordt het ogenschijnlijk vrijgekomen vermogen **niet automatisch direct aan de boiler toegewezen**. Eerst moet opnieuw worden beoordeeld:

- totaal P1-netvermogen;
- L1/L2/L3-fasebelasting;
- werkelijk Tesla-vermogen;
- boilerstatus en boilerconstraint;
- resterende veilige marge.

Hiermee voorkomen we dat Homey na een veiligheidsingreep van Easee direct een andere grote belasting inschakelt en zo dezelfde net- of fasegrens opnieuw benadert.

### Hysterese na Equalizer-ingreep

Voor de toekomstige actieve orchestratie geldt als ontwerpregel een korte stabilisatieperiode na onverwacht terugregelen of pauzeren van Tesla. Richtwaarde is **1–2 minuten** voordat vrijgekomen vermogen opnieuw aan een flexibele belasting wordt toegewezen.

De definitieve tijd wordt vóór activering in shadow mode gevalideerd. Het doel is regel-pingpong tussen Homey en Easee te voorkomen.

!!! info "Huidige status"
    Deze regels zijn nu als **doelarchitectuur/constraint** vastgelegd. De actieve `Energie Manager PV - Shadow Mode v1.6.4` blijft read-only en is hiervoor niet functioneel gewijzigd.

## Boiler-observer en cyclusregistratie

De actuele v1.6.4-flow observeert de boiler zonder deze te schakelen. Een vermogen boven **1,5 kW** wordt als `VERWARMEN` beschouwd. Na minimaal 15 minuten bevestigd verwarmen en vervolgens minder dan **100 W gedurende 10 minuten** doorloopt de observer `AFKOELEN_WACHT` naar `OP_TEMPERATUUR`.

Boilercycli worden op basis van de 2-minutenmetingen bijgehouden en afgeronde cycli worden gepubliceerd naar:

`docs/data/boiler-cycles.json`

## 2-minuten sampler

De actieve v1.6.4-flow wordt iedere 2 minuten uitgevoerd. De persistente runtime-state wordt opgeslagen in een Homey Logic-string. Hiermee worden onder andere de boiler-observer en actieve cyclus bijgehouden.

## 15-minuten websitepublicatie

Dezelfde Advanced Flow heeft daarnaast een 15-minuten trigger. De actuele baseline wordt gepubliceerd naar:

`docs/data/shadow-baseline-v01.json`

De GitHub-JSON vormt een persistente websitehistorie van maximaal 720 gepubliceerde samples. Daarnaast worden afgeronde dagen compact bewaard in `docs/data/energy-daily-history.json`.

## Aangestuurde apparaten

**Geen.** v1.6.4 is volledig read-only/shadow. De flow observeert en registreert, maar voert geen fysieke schakelingen uit.

## Versiebeheer

De ongenummerde voorganger `Energie Manager PV - Shadow Mode` is uitgeschakeld. De actuele operationele shadow-versie is `Energie Manager PV - Shadow Mode v1.6.4`. Volgens de gehanteerde versieafspraak hoort maximaal één versie binnen dezelfde flowfamilie actief te zijn.
