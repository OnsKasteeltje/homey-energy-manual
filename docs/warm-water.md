# Warm water optimalisatie — Energy Core v2

**Status:** 🟢 actief in **PURE SHADOW**  
**Actieve kern:** `EM v2 | 00 Core Tick | v0.9.5`  
**Context:** `EM v2 | 30 Context | Price + PV v0.1`  
**Fysieke v2-boilerwrites:** **uitgeschakeld**

De warmwaterregeling is onderdeel van Energy Core v2. Core observeert de elektrische boiler, leidt de dagstatus af en berekent iedere vijf minuten de gewenste aansturing. Fysieke aan/uit-acties zijn nog niet actief.

## Dagdoel

Het primaire comfortdoel is dat de elektrische boiler eenmaal per lokale kalenderdag aantoonbaar `OP_TEMPERATUUR` bereikt. Zodra dat is gebeurd blijft `goalReachedToday=true` tot de dagwissel. De 240-minutenregel is alleen fallback wanneer `OP_TEMPERATUUR` niet betrouwbaar wordt vastgesteld.

## Detectie OP_TEMPERATUUR

```text
boiler aan + vermogen > 1500 W gedurende minimaal 15 min
    → verwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende minimaal 10 min
    → interne thermostaat afgeslagen
    → OP_TEMPERATUUR bereikt
```

Belangrijke meetbeperking: wanneer het externe boilerrelais UIT staat kan Core geen nieuwe thermische warmtevraag waarnemen. Een nieuwe warmtevraag is alleen indirect zichtbaar nadat het relais is vrijgegeven en het vermogen vervolgens >1500 W wordt. Deze beperking is leidend voor Planner v0.12.

## WW Planner v0.12 — vastgesteld SHADOW-ontwerp

Planner v0.12 behandelt het boilervat als thermische opslag. Doel is het dagelijkse comfortdoel tegen de laagste verwachte marginale energiekosten te bereiken, zonder extra device-polling en zonder fysieke writes tijdens validatie.

### Dag- en nachtcyclus

1. Nadat `OP_TEMPERATUUR` is bereikt blijft het relais beschikbaar tot **19:00**. Core probeert dezelfde dag niet opnieuw opportunistisch te verwarmen.
2. Om **19:00** mag het relais UIT: toestand `NIGHT_HOLD`. Vanaf dat moment accepteren we bewust dat nieuwe thermische vraag niet zichtbaar is.
3. Om **00:00 lokale tijd** opent een nieuw kalenderdagdoel. Nachtoptimalisatie telt alleen voor de nieuwe dag en start daarom principieel niet vóór middernacht.
4. Vanaf 00:00 kan een uitzonderlijk goedkoop nachtvenster leiden tot `NIGHT_PRICE_RELEASE`.
5. Zonder nacht-release blijft de boiler in `NIGHT_HOLD` en wacht de planner op werkelijk bruikbaar PV/netoverschot.
6. Bij voldoende werkelijk overschot vóór 10:00 volgt `PV_RELEASE`.
7. Is er vóór **10:00** geen betere opportunity, dan volgt `DEADLINE_RELEASE`: relais beschikbaar ongeacht prijs/PV. Dit is de comfortgarantie.
8. Na iedere release wordt niet opnieuw opportunistisch UIT geschakeld totdat de verwarmingsvraag/cyclus is beoordeeld. Het verdwijnen van export doordat de boiler zelf circa 1,9 kW gaat gebruiken is dus géén stoptrigger.

### Logische toestanden

```text
AVAILABLE
   ↓ 19:00 + dagdoel bereikt
NIGHT_HOLD
   ├─ goedkoopste economische nachtkeuze → NIGHT_PRICE_RELEASE
   ├─ voldoende echt overschot          → PV_RELEASE
   └─ 10:00 bereikt                     → DEADLINE_RELEASE

RELEASE
   ├─ vermogen blijft <100 W → geen actuele thermische vraag
   └─ vermogen >1500 W ≥15m → HEATING_CONFIRMED
                                  ↓ thermostaat <100 W ≥10m
                              OP_TEMPERATUUR
```

Een release is een toestemming om de boilerthermostaat zelf te laten beslissen. `RELEASE` betekent dus niet automatisch 1,9 kW verbruik.

## Economische beslisregel

De planner vergelijkt niet simpelweg `PV` met `netstroom`. Eigen PV heeft een opportunity cost: wanneer die kWh anders geëxporteerd zou worden, is de gemiste terugleververgoeding de marginale prijs van boilerverwarming met PV.

Conceptueel:

```text
nachtkosten_per_kWh = importprijs_nacht
pv_kosten_per_kWh    = gemiste_exportwaarde
wachtkosten_per_kWh  = beste verwachte marginale kosten vóór 10:00
```

`NIGHT_PRICE_RELEASE` is economisch aantrekkelijk wanneer de actuele/nabije nachtprijs voldoende lager is dan de beste verwachte kosten van wachten. Om voor triviale prijsverschillen niet onnodig vroeg thermisch te laden geldt in de eerste SHADOW-versie een ontwerp-marge van **€0,05/kWh**. Negatieve prijzen vormen een aparte sterke opportunity.

### Initiële prioriteitsvolgorde

1. `CATCHUP / SAFETY` — comfortdoel dreigt niet haalbaar te worden.
2. `PRICE_NEGATIVE` — na 00:00, nieuw dagdoel open: `NIGHT_PRICE_RELEASE / MUST`.
3. `NIGHT_ECONOMIC` — nachtprijs minimaal €0,05/kWh gunstiger dan beste verwachte marginale kosten vóór 10:00: `NIGHT_PRICE_RELEASE / SHOULD`.
4. `PV_SURPLUS` — werkelijk flex-overschot kan boiler + reserves dragen: `PV_RELEASE / SHOULD`.
5. `DEADLINE_10` — 10:00 zonder eerdere release: `DEADLINE_RELEASE / MUST`.
6. Anders `NIGHT_HOLD / WAIT`.

Een simpele `PV > 2 kW`-voorwaarde wordt expliciet niet gebruikt. De relevante grootheid is werkelijk beschikbaar flex-overschot na woningverbruik, netveiligheidsreserve en Quatt-reserve.

## Benodigd Context-contract voor v0.12

De bestaande 15-minuten Price + PV Context blijft de plaats waar externe prijs- en forecastinformatie wordt samengevat. Core hoeft hiervoor geen extra Homey-devices te pollen.

Voorgestelde aanvullende velden:

```text
current_price_eur_kwh
night_min_price_eur_kwh
night_min_price_at
best_price_before_10_eur_kwh
export_value_eur_kwh
pv_forecast_before_10_kwh
expected_flex_surplus_before_10_kwh
pv_outlook_class = LOW | MEDIUM | HIGH
```

Afgeleide plannerwaarden:

```text
expected_wait_cost_eur_kwh
night_advantage_eur_kwh
night_economic = true | false
```

Bij stale/onvolledige economische context mag geen opportunistische nachtstart plaatsvinden. De 10:00-comfortrelease en safety/catch-up blijven wel beschikbaar.

## Scenario-matrix v0.12

| Scenario | Nachtprijs | PV/ochtend | Verwachte keuze | Reden |
|---|---:|---|---|---|
| Negatieve prijs na 00:00 | < €0 | willekeurig | `NIGHT_PRICE_RELEASE / MUST` | energie economisch zeer aantrekkelijk; nieuw dagdoel open |
| Goedkope nacht, slechte PV | €0,10 | LOW | `NIGHT_PRICE_RELEASE / SHOULD` | goedkoper dan waarschijnlijke ochtendimport |
| Goedkope nacht, goede PV maar exportwaarde €0,15 | €0,12 | HIGH | `NIGHT_PRICE_RELEASE / SHOULD` indien margebeleid gehaald | nacht kan zelfs goedkoper zijn dan PV met gemiste exportwaarde |
| Nacht €0,20, goede PV, exportwaarde €0,15 | €0,20 | HIGH | `NIGHT_HOLD` → wacht op PV | PV heeft lagere marginale kosten |
| Nacht en ochtend vrijwel gelijk | €0,18 vs €0,17 | MEDIUM | `NIGHT_HOLD` | verschil < economische marge; thermische flexibiliteit bewaren |
| Vroege echte export ≥ boiler + reserves | — | werkelijk overschot | `PV_RELEASE / SHOULD` | benut aantoonbaar overschot, niet alleen forecast |
| Forecast goed maar nog geen export | — | HIGH forecast | `NIGHT_HOLD` | forecast alleen is geen fysieke PV-release-trigger |
| Geen opportunity om 10:00 | duur/geen zon | LOW | `DEADLINE_RELEASE / MUST` | comfort boven optimalisatie |
| Release, boiler blijft <100 W | — | — | `AVAILABLE/NO_HEAT_DEMAND` | thermostaat vraagt geen warmte; vrijwel geen energiekosten |
| Release, direct >1500 W | — | — | `HEATING_CONFIRMED`, lock | thermische vraag aangetoond; opportunity niet opnieuw evalueren tijdens cyclus |
| Export verdwijnt na start boiler | — | — | doorverwarmen onder lock | boiler veroorzaakt zelf verdwijnen van export; geen oscillatie |
| Context stale vóór 10:00 | onbekend | onbekend | geen nacht/economische release; 10:00 `MUST` | fail-safe bij ontbrekende forecast/prijsdata |

## Voorbeeldberekening

Met `boilerExpectedW ≈ 1900 W` kost een uur bevestigde verwarming ongeveer 1,9 kWh.

- Nacht €0,12/kWh → circa **€0,23**.
- Ochtendimport €0,25/kWh → circa **€0,48**.
- PV die anders tegen €0,15/kWh geëxporteerd wordt → opportunity cost circa **€0,29**.

In dit voorbeeld is €0,12 nachtstroom economisch gunstiger dan zowel latere import als het opofferen van export. Bij €0,20/kWh nachtstroom en €0,15/kWh exportwaarde is wachten op PV juist aantrekkelijker.

De uiteindelijke planner moet daarom marginale kosten vergelijken in plaats van de vaste regel `PV altijd eerst` te gebruiken.

## Huidige opportunity planner — v0.11 runtime

De momenteel actieve SHADOW-runtime gebruikt nog de bestaande opportunityset:

| Opportunity | Startvoorwaarde | Run-lock |
|---|---|---:|
| `EXPORT` | ≥2100 W actuele netexport | 15 min |
| `PV_FORECAST` | top-4 PV-forecast én ≥500 W export | 15 min |
| `PRICE_NEGATIVE` | negatieve prijs én ≥30 min tot volgend tariefuur | 30 min |
| `PRICE_CHEAP` | goedkoper dan komende 4 uur én ≥30 min tot volgend tariefuur | 30 min |
| `CATCHUP` | verder wachten bedreigt dagdoel/deadline | 0 min opportunity-lock |

Planner v0.12 hierboven is dus **ontwerp/documentatie**, nog niet actief in Homey.

## Fallback en deadline — huidige runtime

De huidige dagelijkse regelperiode eindigt om 19:00. Vanaf Core Tick v0.9.5 wordt catch-up niet meer gebaseerd op relais-aan-tijd.

`boilerOnMinToday` blijft beschikbaar als diagnostiek, maar de fallback gebruikt `heatingMinToday`. Alleen een interval waarin het relais AAN staat én het gemeten boilervermogen >1500 W is telt mee:

```text
heatingNow = boilerOn && boilerPowerW > 1500 W
heatingMinToday += deltaMin alleen wanneer heatingNow
remainingFallbackMin = max(0, 240 - heatingMinToday)
```

Als `OP_TEMPERATUUR` al is bereikt wordt `remainingFallbackMin` direct 0.

## Context en freshness

De huidige `EM v2 | 30 Context | Price + PV v0.1` vernieuwt iedere 15 minuten prijs- en PV-signalen zonder fysieke device-scan. Core accepteert context tot maximaal 35 minuten oud. Bij stale context worden prijs en forecast genegeerd; harde comfort-/safetyregels blijven bruikbaar.

## Veiligheid

De runtime blijft volledig Shadow:

```text
controlMode            = SHADOW
readOnly               = true
deviceWrites           = false
physicalWritePerformed = false
```

Planner v0.12 verandert dit niet. De eerstvolgende implementatiestap is uitsluitend Context-uitbreiding + Planner v0.12 in SHADOW. Pas na scenario- en live-validatie kan fysieke Control opnieuw worden overwogen.

## Samenwerking met andere energieverbruikers

WW is één flexibele belasting binnen Energy Core v2. De centrale architectuur budgetteert gezamenlijk tussen huishoudelijk basisverbruik, Tesla/Easee, elektrische boiler, Quatt als comfortload en later Victron/batterij. Een toekomstige batterij vergroot de keuzevrijheid: PV kan dan mogelijk economisch beter in de accu worden opgeslagen dan direct thermisch worden geladen. De marginale-kostenbenadering van v0.12 is daarop voorbereid.

> **Volgende stap:** Context-contract uitbreiden en Planner v0.12 uitsluitend in SHADOW laten meedraaien. Geen fysieke boilerwrites tijdens deze stap.
