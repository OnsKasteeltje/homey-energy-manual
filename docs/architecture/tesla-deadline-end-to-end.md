# Tesla deadline — end-to-end keten

## Doel

Dit document beschrijft de **actuele productie-keten** voor een Tesla-deadline: welke component eigenaar is van command lifecycle, afgeleide deadline-state, realtime execution en fysieke Easee-writes.

De gecontroleerde keten is:

```text
Website / Invoer V2
  ↓ POST + control-PIN
Cloudflare Worker
  ↓ GitHub Contents API PUT
GitHub main: docs/data/tesla-deadline-command.json
  ↓ Pi command fetcher (60 s)
Pi: /home/jeroen/ems/data/tesla-deadline-command.json
  ↓ OnSuccess / watchdog
Pi deadline derived-state builder
  ↓
/home/jeroen/ems/data/ev-deadline-shadow-state.json
  ↓
Pi /control/current
  ↓
Homey PI Dynamic Planner Bridge v1.5.9
  ↓
EM2_Power_Intent
  ↓
EV Power Adapter v0.2.0
  ↓
EV Gate v0.3.0
  ↓
EV Power writer v0.4.5 [LIVE]
  ↓
Easee / Tesla
```

Pi is deadline lifecycle/planning authority. Homey remains realtime executor/safety boundary and the guarded EV writer is the sole automatic physical Easee writer.

## 1. Website → Cloudflare Worker

De private Invoer V2 gebruikt de bestaande authenticated Worker-write route. De browser bevat geen GitHub-token. De Worker source staat canoniek onder:

`apps/cloudflare/tesla-deadline-worker.js`

De request bevat minimaal:

```json
{
  "active": true,
  "deadline": "YYYY-MM-DDTHH:MM",
  "currentSoc": 27,
  "targetSoc": 40,
  "maxA": 8
}
```

De PIN wordt meegestuurd als `X-Tesla-Control-Pin`. De Worker valideert input, genereert een nieuwe `requestId`, gebruikt de operationele `calibrationKWhPerPercent` en berekent:

`goalKWh = (targetSoc - currentSoc) × calibrationKWhPerPercent`

De command-SOC is input-only. Er is geen live Tesla-SOC telemetry in deze keten.

## 2. Cloudflare Worker → GitHub command

De Worker schrijft via de GitHub Contents API naar:

`docs/data/tesla-deadline-command.json`

Het bestand is tijdens de huidige migratiefase de duurzame commandbron voor de Pi. Belangrijke velden zijn:

- `schema=2`
- `requestId`
- `requestedAt`
- `active`
- `deadline`
- `currentSoc`
- `targetSoc`
- `calibrationKWhPerPercent`
- `goalKWh`
- `maxA`

## 3. GitHub command → Pi runtime command

De actieve consumer is:

`services/pi/integrations/github/ev/fetch_deadline_command.py`

Systemd:

- `ems-ev-deadline-command.timer` — 60-seconden cadence;
- `ems-ev-deadline-command.service` — fetch/validate/atomic replace;
- succesvolle service-runs triggeren `ems-ev-deadline-state.service` via `OnSuccess=`.

Runtime command:

`/home/jeroen/ems/data/tesla-deadline-command.json`

De fetcher valideert schema, request identity, timestamp, SoC-bounds, `goalKWh`, calibratie en `maxA`. Een fetch- of validatiefout vervangt nooit de laatst geldige runtime command.

### Bekende transportbeperking — 2026-10-01

De huidige fetcher leest nog de branch-URL op `raw.githubusercontent.com`. Live evidence op 2026-10-01 liet zien dat een nieuwe GitHub commit om circa 22:08 pas om 22:12 door de Pi werd gezien, ondanks correcte 60-seconden polling. De command lifecycle, Pi derived state en Homey execution reageerden daarna direct correct.

Daarom geldt:

- sneller pollen alleen lost deze latency niet betrouwbaar op;
- de raw branch-URL is geen geschikte langetermijn transportkeuze voor tijdkritische deadline-commands;
- migratie naar een cache-onafhankelijke GitHub Contents REST read is technische schuld / geplande follow-up;
- totdat die migratie is uitgevoerd blijft GitHub command latency onderdeel van deadline feasibility.

Dit is uitsluitend de **website → Pi command-transfer**. De live Homey ↔ Pi state/control transport blijft LAN-lokaal en is niet afhankelijk van GitHub.

## 4. Pi deadline derived state

Builder:

`services/pi/state/ev/deadline/build_deadline_state.py`

Runtime output:

`/home/jeroen/ems/data/ev-deadline-shadow-state.json`

Schema:

`EMS_PI_EV_DEADLINE_SHADOW_STATE_V0.2`

Per nieuwe `requestId` wordt een immutable request-baseline opgebouwd. Relevante velden zijn onder andere:

```text
requestId
deadlineAt
goalKWh
maxA
baselineMeterKWh
deliveredKWh
remainingKWh
latestStartAt
status
telemetryAt
```

De Easee cumulatieve meter is checkpoint/validation only. Realtime voortgang wordt afgeleid uit canonical Homey Core `tesla.power_w`, geïntegreerd over canonical telemetry timestamps. De normale Homey Core cadence is vijf minuten; de deadline execution contract accepteert maximaal 420 seconden telemetry age.

Conceptueel:

```text
remainingKWh = max(0, goalKWh - deliveredKWh)

latestStart =
    deadline
    - remainingKWh / availableDeadlinePowerKW
```

Een deadline zonder expliciete offset wordt door de Pi canoniek geïnterpreteerd in `Europe/Amsterdam`.

## 5. Pi planning en /control/current

De Pi is planner/deadline authority. De status/control API projecteert de actuele deadline als top-level contract:

`EMS_PI_EV_DEADLINE_EXECUTION_V0.1`

via:

`GET /control/current`

Het contract is fail-closed en vereist onder andere geldige Pi authority, geldige derived deadline-state en voldoende verse canonical Homey telemetry.

Belangrijke execution fields:

```text
active
requestId
deadlineAt
remainingKWh
latestStartAt
maxA
authority = PI
valid
```

De Dynamic Pi Planner behandelt deadline charging als harde constraint. Opportunistisch laden blijft een aparte PV-flexroute. Deadline execution is altijd 3P-capable en wordt begrensd door de request-specifieke `maxA`.

## 6. Homey exact-minute deadline guard

Actieve flow:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.9 ADAPTIVE UPSCALE [READY]`

Flow-ID:

`8bf53fdb-76f4-47db-8ccb-773ac515f06e`

De bridge leest `/control/current` iedere minuut en blijft alleen actief als:

`EM2_Planner_Authority == PI`

De bridge schrijft niet rechtstreeks naar Easee. Hij projecteert het geldige Pi-contract naar canonical `EM2_Power_Intent`.

Voor een actieve deadline gebruikt Homey live Easee connectivity/charge-state als executor evidence. Wanneer:

```text
deadline active
AND Tesla connected
AND remainingKWh > 0
AND now >= min(explicit latestStart, derived latestStart)
```

geldt:

```text
mode       = 3P
requestedA = deadline maxA
status     = NUMERIC_DEADLINE_TARGET
source     = REMAINING_KWH_OVER_TIME_TO_DEADLINE
reason     = HOMEY_EXECUTOR_DEADLINE_GUARD
```

De Pi blijft eigenaar van deadline-state en `maxA`; Homey wordt hierdoor geen tweede planner.

De historische Homey flow `EV Deadline Goal Adapter` is disabled en is geen onderdeel meer van de actieve keten.

## 7. Power Intent → fysieke laadregeling

De actieve keten is:

```text
EM2_Power_Intent
  ↓
EV Power Adapter v0.2.0
  ↓
EV Gate v0.3.0
  ↓
EV Power writer v0.4.5 [LIVE]
  ↓
Easee
```

Flow-ID's:

```text
Bridge   8bf53fdb-76f4-47db-8ccb-773ac515f06e
Adapter  953e9b18-3576-4557-b940-ed4a64eb2516
Gate     ec5e5d34-8205-4cf0-a661-7bf744feb6e0
Writer   fea23193-a03f-49dd-9780-7e72ee48747d
```

De writer is de enige automatische fysieke Easee-writer binnen deze keten. Deadline execution forceert 3P met de Pi-owned `maxA`; fysieke circuitlimieten en Easee safety blijven onafhankelijk begrenzend.

## 8. Deadline feasibility

Een geldige command betekent niet automatisch dat de deadline fysiek nog haalbaar is.

Feasibility hangt af van:

- tijd tot deadline;
- `remainingKWh`;
- request-specifieke `maxA`;
- werkelijke Easee/Tesla beschikbaarheid;
- command-transfer latency;
- eventuele fysieke veiligheidsbegrenzing.

Wanneer een request pas ná `latestStartAt` wordt ingevoerd of ontvangen, moet de executor direct maximaal toegestaan deadline-laden aanvragen, maar dat kan een reeds onhaalbare deadline niet alsnog haalbaar maken.

## 9. Diagnosevolgorde

Bij een ontbrekende of foutieve deadline altijd links naar rechts controleren:

```text
1. GitHub command
   docs/data/tesla-deadline-command.json
   - nieuwe requestId?
   - requestedAt/deadline/SOC/maxA correct?

2. Pi runtime command
   /home/jeroen/ems/data/tesla-deadline-command.json
   - dezelfde requestId?
   - fetch status UPDATED/UNCHANGED?
   - command-transfer latency?

3. Pi derived state
   /home/jeroen/ems/data/ev-deadline-shadow-state.json
   - status TRACKING?
   - remainingKWh?
   - latestStartAt?
   - telemetry fresh?

4. /control/current
   - deadline.valid?
   - deadline.active?
   - authority PI?
   - maxA correct?

5. Homey PI Bridge
   - deadlineGuard.active?
   - deadlineGuard.applied?
   - connected?
   - forceFromAt bereikt?
   - phase command 3P + maxA?

6. Adapter / Gate / writer
   - Adapter EXECUTABLE?
   - Gate PASS?
   - writer LIVE / write result?

7. Easee / Tesla
   - plugged_in_paused of plugged_in_charging?
   - offered A?
   - target A?
   - 3-fase stroom?
   - werkelijk vermogen?
```

Deze volgorde voorkomt dat een upstream command-latency als planner- of actuatorprobleem wordt behandeld.

## 10. Verantwoordelijkheden

```text
Website          = gebruikersinvoer
Worker           = authenticatie + duurzame GitHub command-write
GitHub command   = tijdelijke duurzame overdrachtsbron website → Pi
Pi fetcher       = command-ingress + validatie + atomic runtime publication
Pi deadline state= lifecycle/progress/latestStart
Pi Planner/API   = planning + deadline execution contract
Homey Bridge     = realtime executor guard + canonical Power Intent
EV Adapter/Gate  = vertaling + validatie
EV writer        = enige automatische fysieke Easee-write
Easee/Equalizer  = lokale elektrische safety
```

Er is één planner/deadline authority (Pi) en één automatische fysieke writer (Homey EV writer). Dual ownership is verboden.


## 11. Planner-onafhankelijke deadline-uitvoering — PR #212 (LIVE sinds 2026-10-09)

Deze aanpassing is via PR #212 geïntegreerd op `main` als commit `7c3eb3121ad04f5380e906a812364080954adbe7`. De Pi API en de bestaande Homey Bridge v1.5.9 zijn op 9 oktober 2026 gecontroleerd naar productie gepromoveerd, na afloop van de 12:00-deadline. De Homey EV Adapter, Gate en enige fysieke Actuator blijven ongewijzigd.

De Pi behandelt een deadline als eigen gebruikersintentie. Een falende PV-planner mag een geldige, actieve deadline niet blokkeren. Er blijft **één** `GET /control/current`, **één** Homey PI Bridge en **één** EV Adapter → Gate → Actuator → Easee-keten; er komt geen tweede charger-controller of Homey publisher.

- **PLANNER:** bestaand gedrag en bestaande targets bij een geldig plan; `executionMode=PLANNER` en `planner.valid=true`.
- **DEADLINE_ONLY:** uitsluitend bij een onbruikbaar PV-plan én een geldig, actief, toekomstig Pi-deadlinecontract met verse canonical telemetrie. `planner.valid=false` met de echte foutreden. Het controlcommando verloopt uiterlijk na 90 seconden of op de deadline.
- In `DEADLINE_ONLY` staan PV-opportunity en batterij uit, WW op `HOLD`, Quooker op `OFF`. Er volgt **geen** extra fysieke EV-write uit de Pi; Homey bevestigt verbinding, 3P-modus, `maxA`, revisies, freshness en bestaande hardwarelimieten.
- Zonder geldige deadline of met ongeldige globale autorisatie blijft het complete controlcommando **fail-closed**.

Health/observability blijft onderscheid maken tussen API-beschikbaarheid en plannergezondheid. Bij een uitvoerbare deadline-only fallback geeft `GET /health`:

```json
{
  "control_endpoint_status": "ready",
  "control_execution_mode": "DEADLINE_ONLY",
  "control_planner_status": "degraded",
  "control_planner_reason": "PLAN_STALE",
  "control_deadline_active": true,
  "control_deadline_valid": true
}
```

`control_endpoint_status=ready` zegt alleen dat Homey een bruikbaar controlcommando kan ontvangen; het zegt **niet** dat de PV-planner gezond is. Bij een gezonde planner rapporteert `control_planner_status=ready`. De bestaande `control_endpoint_status` en `control_valid_until` blijven compatibel.

Regressiebewijs: `tests/control/test_ev_deadline_planner_independence.py`, `tests/homey/ev-deadline-planner-independent-bridge.test.mjs` en `scripts/ems_architecture_gate.sh`. Voor promotie opnieuw op de geïsoleerde Pi-worktree uitvoeren. Dit is uitgevoerd in afzonderlijke stappen: Pi API deployment met backup `/home/jeroen/ems/backup/runtime-20261009-122100`, daarna gerichte Homey Bridge update en byte-identieke GitHub readback. Productie `/health` en `/control/current` waren gezond (`PLANNER`, `planner.valid=true`, geen actieve deadline). De live Bridge bleef ingeschakeld en niet defect; Easee stond na cutover op 0 A / 0 W. Oude bridgecode voor rollback: GitHub-commit `a378702fa404df6732a5f0490d37e88656db1edf`. Een werkelijk planner-down + urgente deadline is nog niet in productie voorgekomen en is alleen offline getest.


## 12. Local Pi EV Deadline Command Ingress V1.1 — LIVE (2026-10-09)

Source: merged PR #213, `6b2a2de8da64d542232c1cb42c0658e6eb50fc07`. On 2026-10-09 the Pi deployed the V1.1 Status API, Web Data API, website and private Caddy configuration. The old `ems-ev-deadline-command.timer` and command fetch service were explicitly disabled/stopped. The Pi command file is now the sole runtime source; the existing Homey Bridge/Gate/Actuator are untouched. A **new valid website command and resulting Easee physical behavior have not yet been tested end to end**.

Private command chain:

```text
Tailscale-only EMS Invoer V2 (http://100.127.130.0/settings/)
  -> Caddy POST /web/commands/tesla (remote_ip Tailnet only)
  -> 127.0.0.1:3100/commands/tesla (loopback-only + control PIN)
  -> /home/jeroen/ems/data/tesla-deadline-command.json (atomic)
  -> existing derived-state builder (immediately, under file lock)
  -> existing /control/current
  -> unchanged Homey Bridge/Adapter/Gate/sole Actuator/Easee
```

Credential must be manually provisioned to `/etc/ems/tesla-control.pin`,
owned by jeroen and mode 0600, minimum 8 characters. No PIN is stored in Git.
The entire V2 website is available at **one** Tailscale-only address,
`http://100.127.130.0/`, both at home and away. Caddy binds exclusively to
the Pi tailnet interface; **ordinary LAN `http://192.168.1.42` website
access is deliberately removed** after cutover. The single site hosts Live,
Invoer, History and the future SwiftUI-app API calls. HTTP application
traffic is protected within Tailscale's encrypted WireGuard tunnel; this
is not a public HTTP listener. A user device must join the authorized
tailnet before it can access the site. The PIN still independently protects
command POST; read-only pages require only Tailscale membership. No public
port is opened. Server validates intent, schema, future deadline, request-specific
maxA, SoC and goal energy; generates server-side requestId. A clientRequestId
prevents a retry of the same request from creating a new baseline.
Invalid requests fail closed without changing the current command.

The read-only `GET /web/commands/current` reads the same runtime command
file and accepts `active=false` with null SoC. The worker's settings
functionality is outside this migration.

The existing derived-state builder is serialized between API and systemd
invocations using a host-local file lock, and writes output atomically.
If immediate derivation fails, the API returns accepted + PENDING_WATCHDOG;
the existing 60-second deadline-state timer remains as recovery.

**Production cutover evidence, 2026-10-09:**
1. Pi read-only worktree preflight at `671b4086d`: 18/18 new tests PASS, architecture gate PASS, Caddy validation "Valid configuration", Tailscale `100.127.130.0` present.
2. Source merged via PR #213; Pi `main` fast-forwarded to `6b2a2de8d`.
3. Runtime backup at `/home/jeroen/ems/backup/ev-ingress-v11-20261009-222745`. The status/web-data API and private frontend/Caddy were updated and restarted/reloaded. `GET /web/commands/current` and `GET /web/state/current` passed. HTTP listener showed **only** `100.127.130.0:80`.
4. PIN stored in `/etc/ems/tesla-control.pin` with restricted access. Negative POSTs: wrong PIN HTTP 401, expired deadline HTTP 400. SHA-256 of canonical runtime command file remained unchanged.
5. `ems-ev-deadline-command.timer` disabled/stopped and `ems-ev-deadline-command.service` stopped; both inactive in shell validation. `ems-ev-deadline-state.timer`, `ems-status-api.service` and `ems-web-data-api.service` active. Website readback of legacy requestId `483bb445-b434-47f8-91ac-318c11060e24` succeeded.
6. The Cloudflare Worker may still exist for legacy `ems_settings`; its Tesla GitHub write route is **not** a Pi command source anymore. Do not re-enable legacy fetch without reconciling newer local commands.

**Pending acceptance:** submit a new *deliberate* authenticated deadline via the Tailscale website; check requestId in runtime command and derived state, `/control/current`, Homey Bridge/Gate, Easee target/offered A and the time to actual charging when applicable. Test cancellation. Device access from Mac/iPhone via Tailscale on home Wi-Fi and mobile data, plus SwiftUI ATS/PWA secure-origin behavior, require separate client verification.

One-URL note: do not create a separate LAN-write or LAN-read experience.
The existing Homey → Pi control connection on 192.168.1.42:3100 is a
separate internal service and is NOT moved to Tailscale. A browser on the
LAN must use the Tailscale website URL; all devices must have Tailscale
installed and connected. SwiftUI/iOS HTTP App Transport Security and secure
browser/PWA contexts must be verified separately before native/PWA cutover:
WireGuard transport encryption does not by itself make an HTTP URL an
HTTPS secure origin. An eventual HTTPS-on-tailnet improvement must retain
one private origin and must not expose the website publicly.

All manual deadline inputs are interpreted as Europe/Amsterdam. The form
never reinterprets the unzoned command timestamp using the visiting browser's
local timezone; the Pi is authoritative for future-deadline validation. This
is especially important when entering a deadline while travelling abroad via
Tailscale.
