# Tesla deadline — end-to-end keten

## Doel

Dit document legt vast **wat wat aanroept, welke data wordt doorgegeven en waar de verantwoordelijkheden liggen** voor een Tesla-deadline. Het is bedoeld als technische trace voor diagnose, wijzigingen en regressietests.

De gecontroleerde keten is:

```text
Website
  ↓ POST
Cloudflare Worker
  ↓ commit
GitHub: docs/data/tesla-deadline-command.json
  ↓ polling/read
Homey: EV Deadline Goal Adapter
  ↓ EM2 goals/Core state
Homey Core / energy-state-v2.json
  ↓ input
Pi Dynamic Planner
  ↓ /control/current
Homey Pi Dynamic Planner Bridge
  ↓ canonical EM2_Power_Intent
EV Power Adapter → Validation Gate → EV Actuator
  ↓
Easee / Tesla
```

## 1. Website → Cloudflare Worker

Frontend controller:

`docs/javascripts/tesla-deadline-controller-v2.8.115.js`

De controller leest:

`docs/data/tesla-control-config.json`

Daarin staat de `worker_url`. Bij **Opslaan** doet de frontend een `POST` naar die Worker met JSON:

```json
{
  "active": true,
  "deadline": "YYYY-MM-DDTHH:MM",
  "currentSoc": 51,
  "targetSoc": 95,
  "maxA": 7
}
```

De PIN wordt apart meegestuurd in header `X-Tesla-Control-Pin`.

De frontend houdt na een succesvolle POST tijdelijk een `pendingCommand` bij en controleert of Core de opdracht bevestigt. Als dat niet binnen de ingestelde acknowledgement-periode gebeurt, toont de UI een write-route fout.

## 2. Cloudflare Worker → GitHub command

De Worker schrijft de opdracht naar:

`docs/data/tesla-deadline-command.json`

Dit bestand is de persistente command-overdracht tussen website en Homey.

Voorbeeld van de live gevalideerde opdracht van 12 september 2026:

```json
{
  "schema": 2,
  "requestId": "4a5e7dfb-dace-41b3-aa45-401445cefc00",
  "requestedAt": "2026-09-12T11:56:22.620Z",
  "source": "website",
  "active": true,
  "deadline": "2026-09-14T05:00",
  "currentSoc": 51,
  "targetSoc": 95,
  "calibrationKWhPerPercent": 0.55,
  "goalKWh": 24.2,
  "maxA": 7
}
```

De Worker berekent dus ook de energie-opgave:

`goalKWh = (targetSoc - currentSoc) × calibrationKWhPerPercent`

Voor 51% → 95% bij 0,55 kWh/% is dit 24,2 kWh.

## 3. GitHub command → Homey Goal Adapter

Homey flow:

`EM v2 | 10 Input | EV Deadline Goal Adapter v0.2 METER-TRACKED`

Flow-ID:

`445cb82c-5e1f-43c3-b2cf-f2d78fec6e16`

De adapter leest de raw GitHub-versie van `docs/data/tesla-deadline-command.json` en gebruikt bij een nieuw `requestId` de opdracht als nieuwe deadline-goal.

Belangrijke velden zijn:

- `active`
- `requestId`
- `deadline`
- `goalKWh`
- `maxA`

### Meter-tracking

v0.2 gebruikt de Easee energiemeter als voortgangsbron. Bij een nieuwe request wordt een meterbaseline vastgelegd. Daarna geldt conceptueel:

```text
deliveredKWh = currentEaseeMeterKWh - baselineMeterKWh
remainingKWh = max(0, goalKWh - deliveredKWh)
```

Hierdoor wordt `remainingKWh` niet iedere cyclus teruggezet naar de oorspronkelijke `goalKWh`.

Bij ontbrekende/onbetrouwbare meterdata wordt de eerdere resterende energie conservatief behouden.

## 4. Goal Adapter → Core / energy-state-v2

Core publiceert de uitvoerbare Tesla-deadlinestatus in:

`docs/data/energy-state-v2.json`

en lokaal op de Pi in:

`/home/jeroen/ems/data/energy-state-v2.json`

Relevante Tesla-velden:

```text
connected
deadline_active
deadline_at
latest_start_at
remaining_kwh
charge_state
requested_a
```

`deadline_at` wordt als UTC timestamp gepubliceerd. Een lokale deadline van 05:00 CEST verschijnt dus als 03:00Z.

`latest_start_at` wordt opnieuw bepaald op basis van de resterende energie en het beschikbare laadvermogen. Opportunistisch laden vóór de deadline verlaagt `remaining_kwh` en kan daardoor `latest_start_at` naar later verschuiven.

### Gevalideerde live trace — 12 september 2026

Website-opdracht:

```text
51% → 95%
deadline: maandag 14-09-2026 05:00 CEST
maxA: 7 A
goal: 24.2 kWh
```

Later publiceerde Core:

```text
deadline_active = true
deadline_at = 2026-09-14T03:00:00.000Z
latest_start_at = 2026-09-13T23:01:05.590Z
remaining_kwh = 19.232
```

De Tesla meldde op dat moment ongeveer 60% SOC. 51% → 60% is 9 procentpunt; bij 0,55 kWh/% is dat 4,95 kWh. De Easee meter-tracking had circa 4,968 kWh afgeboekt (`24.2 - 19.232`). Het verschil was slechts circa 0,018 kWh. Dit is een sterke live-validatie van de gebruikte calibratie en meter-tracking, maar geen algemene garantie dat die calibratie onder alle omstandigheden exact blijft.

## 5. Core state → Pi Dynamic Planner

Canonical planner:

`src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py`

Runtime:

`/home/jeroen/ems/runtime/planner/dynamic-plan/build_dynamic_shadow_plan.py`

De planner leest de actieve Tesla-deadline uit de energy state.

Normaal blijft Tesla een secundaire flex-load: opportunistisch laden wordt gekozen op basis van PV-overschot/economische marginale waarde, nadat WW-comfort haalbaar blijft.

De deadline is een **harde constraint**. De plannerfunctie `apply_ev_deadline_constraint(...)` kan vanaf de noodzakelijke startperiode het EV-target overrulen naar `DEADLINE_REQUIRED`.

Belangrijke scheiding:

```text
vóór latestStart  → normale opportunistische PV-logica
vanaf latestStart → resterende energie wordt deadline-verplicht
```

Homey blijft eigenaar van de exacte-minuut veiligheidsuitvoering (`HOMEY_EXECUTOR_EXACT_MINUTE`). De Pi werkt met kwartierslots.

## 6. Pi → Homey executor

Pi status/control API levert de actuele plannercommand via:

`/control/current`

Homey flow:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.6 DEADLINE-GUARD [READY]`

Flow-ID:

`8bf53fdb-76f4-47db-8ccb-773ac515f06e`

De bridge is alleen actief als:

`EM2_Planner_Authority == PI`

Dit is de enige HOMEY↔PI authority gate. De bridge schrijft niet rechtstreeks naar de Easee/Tesla, maar maakt de canonical `EM2_Power_Intent`.

De bridge heeft daarnaast een executor-side deadline guard. Bij een noodzakelijke deadline-charge worden de deadline-semantiek expliciet doorgegeven als:

```text
status = NUMERIC_DEADLINE_TARGET
source = REMAINING_KWH_OVER_TIME_TO_DEADLINE
reason = HOMEY_EXECUTOR_DEADLINE_GUARD
```

Hierdoor blijft de deadline ook aan de uitvoeringskant hard bewaakt.

## 7. Power Intent → fysieke laadregeling

De EV-keten is:

```text
EM2_Power_Intent
  ↓
EV Power Adapter
  ↓
EV Power Adapter Gate
  ↓
EV Power Actuator
  ↓
Easee
```

Belangrijke flows:

```text
Adapter  953e9b18-3576-4557-b940-ed4a64eb2516
Gate     ec5e5d34-8205-4cf0-a661-7bf744feb6e0
Actuator fea23193-a03f-49dd-9780-7e72ee48747d
```

De actuator mag niet handmatig gestart worden voor een test; daarmee kan de normale live-triggersemantiek worden omzeild.

De fysieke startregels zijn bewust strenger dan alleen het plannergetal:

- 7 A of hoger kan een gepauzeerde sessie starten/hervatten.
- 6 A is toegestaan tijdens een reeds lopende laadcyclus.
- 6 A start geen gepauzeerde Tesla.

## 8. Website plannerweergave

De Planner-pagina leest niet rechtstreeks van Homey of `/control/current`. Hij leest de gepubliceerde website-shadow:

`docs/data/energy-planner-shadow-dynamic.json`

Deze wordt gebouwd door:

`src/pi/ems-runtime/planner/dynamic-plan/build_dynamic_website_shadow.py`

De website-shadow gebruikt de actuele Core deadline-state om deadline-informatie zichtbaar te maken. Dit is **observability/UI** en geen aparte control authority.

Tesla-plannerblokken zijn visueel onderscheiden:

- paars = opportunistisch
- oranje = deadline vereist

Als een zojuist ingevoerde deadline na refresh niet zichtbaar is, controleer daarom eerst of de keten command → Homey Core → website-shadow al is bijgewerkt. Alleen browser-refresh kan een nog niet gepubliceerde upstream state niet repareren.

## 9. Diagnosevolgorde

Bij een ontbrekende of foutieve deadline altijd van links naar rechts controleren:

```text
1. docs/data/tesla-deadline-command.json
   - nieuwe requestId?
   - deadline/SOC/maxA correct?

2. energy-state-v2.json → tesla
   - deadline_active?
   - deadline_at correct in UTC?
   - remaining_kwh?
   - latest_start_at?

3. Pi dynamic plan
   - deadlinePlan actief?
   - remaining/deadline overgenomen?
   - opportunistische of DEADLINE_REQUIRED slots?

4. /control/current + Pi Bridge
   - planner READY/fresh?
   - EM2_Planner_Authority == PI?
   - canonical intent correct?

5. EV adapter/gate/actuator
   - targetW/requestedA?
   - gate PASS?
   - actuator live/no-op/write?

6. Easee/Tesla
   - connected/paused/charging?
   - meterprogressie?
```

Deze volgorde voorkomt dat een UI-probleem wordt aangezien voor een plannerprobleem of dat een downstream actuator wordt aangepast terwijl de command upstream nooit is aangekomen.

## 10. Verantwoordelijkheden en guardrails

Samengevat:

```text
Website          = gebruikersinvoer
Worker           = authenticatie + persistente command-write
GitHub command   = overdrachtscontract website → Homey
Goal Adapter     = goal lifecycle + Easee meter-tracking
Homey Core       = canonical live state
Pi Planner       = optimalisatie + harde deadlineplanning
Pi Bridge        = plannerintent → canonical Homey intent + exact-deadline guard
EV Adapter/Gate  = vertaling en validatie
EV Actuator      = enige fysieke Easee-write in deze keten
Homey            = executor en lokale safety owner
```

De architectuur bevat bewust twee complementaire deadline-lagen: de Pi plant de deadline als harde constraint, terwijl Homey de exacte uitvoeringsveiligheid bewaakt. De Pi-planner zelf schrijft geen apparaten rechtstreeks aan.
