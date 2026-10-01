# Tesla deadline write-route

## Actuele productie-route

De website schrijft **niet rechtstreeks naar Homey of Easee**.

```text
Invoer V2
  ↓ POST + control-PIN
Cloudflare Worker
  ↓ GitHub Contents API PUT
docs/data/tesla-deadline-command.json
  ↓ 60 s Pi command fetch
/home/jeroen/ems/data/tesla-deadline-command.json
  ↓
Pi deadline derived state
  ↓
Pi /control/current
  ↓
Homey PI Dynamic Planner Bridge v1.5.3
  ↓
EV Adapter v0.2.0 → Gate v0.3.0 → writer v0.4.4 [LIVE]
  ↓
Easee / Tesla
```

De historische Homey `EV Deadline Goal Adapter` / `Tesla laden v2.7.4` route is **niet meer actief**. Deadline lifecycle, remaining energy en `latestStartAt` zijn Pi-owned. Homey is realtime executor/safety en de guarded EV writer blijft de enige automatische fysieke Easee-writer.

Voor de volledige actuele trace en diagnosevolgorde:

`docs/architecture/tesla-deadline-end-to-end.md`

## Security boundary

De browser bevat geen GitHub- of Homey-token. De Cloudflare Worker bewaart het GitHub write-token als secret en vereist de aparte control-PIN.

Canonical Worker source:

`apps/cloudflare/tesla-deadline-worker.js`

De command-SOC is invoer voor de energie-opgave; er is geen live Tesla-SOC telemetry in deze route.

## Command ownership

De Worker schrijft schema-2 commands naar:

`docs/data/tesla-deadline-command.json`

De Pi haalt deze command op en publiceert hem atomair als:

`/home/jeroen/ems/data/tesla-deadline-command.json`

De Pi valideert een command voordat deze de runtime command vervangt. Een foutieve of niet-ophaalbare command mag de laatste geldige command niet overschrijven.

## Deadline lifecycle en voortgang

Canonical builder:

`services/pi/state/ev/deadline/build_deadline_state.py`

Canonical runtime state:

`/home/jeroen/ems/data/ev-deadline-shadow-state.json`

De Pi bewaakt:

- request identity;
- deadline;
- request-specifieke `maxA`;
- delivered/remaining kWh;
- `latestStartAt`;
- lifecycle status;
- canonical telemetry freshness.

Realtime charging progress wordt uit canonical Homey Core measured Tesla power geïntegreerd. De Easee cumulative meter is checkpoint/validation only en niet de realtime integratiebron.

## Homey execution

De actieve bridge is:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.3 PHASE-AUTHORITY [READY]`

De bridge consumeert `/control/current` en past de executor-side deadline guard toe. Vanaf de noodzakelijke starttijd vraagt hij voor een aangesloten Tesla:

```text
3P
requestedA = Pi deadline maxA
status = NUMERIC_DEADLINE_TARGET
```

De fysieke keten blijft:

```text
Bridge
  ↓
EV Power Adapter v0.2.0
  ↓
EV Gate v0.3.0
  ↓
EV Power writer v0.4.4 [LIVE]
  ↓
Easee
```

Homey mag realtime safety afdwingen maar mag niet opnieuw zelfstandig de deadline of resterende energie plannen.

## Huidige GitHub transportbeperking

Per 2026-10-01 leest de Pi de command nog via een `raw.githubusercontent.com/main/...` branch-URL.

Live evidence op 2026-10-01:

- website-request rond 22:08:19;
- GitHub commit rond 22:08:20;
- Pi-polls bleven meerdere minuten de vorige request zien;
- nieuwe request werd pas om 22:12:28 als `UPDATED` geaccepteerd;
- de Pi derived state werd vervolgens binnen ongeveer één seconde correct `TRACKING`;
- Homey/Easee schakelde daarna naar de gevraagde deadline current.

Deze latency is dus command-transport technical debt en niet een reden om Pi deadline ownership of Homey executor ownership te veranderen.

Geplande follow-up: de Pi read-route migreren van raw branch delivery naar de GitHub Contents REST API, met passende authenticatie/cache-semantiek en regressietests. Tot die wijziging is uitgevoerd beschrijft dit document bewust de **huidige** raw-fetch als productiegedrag.

## Guardrails

- Pi = enige deadline/planner authority.
- Homey = realtime executor/safety.
- EV writer = enige automatische fysieke Easee writer.
- Geen browsersecret.
- Geen Homey polling door de Pi voor deadline progress.
- Canonical Homey telemetry blijft push-fed.
- Een command-transferfout mag geen alternatieve planner of writer activeren.
- Een gemiste/onhaalbare deadline mag niet worden verborgen door timestamps of targets te herschrijven.
