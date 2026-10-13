# Tesla deadline — end-to-end keten

## Doel

Dit document beschrijft de **actuele productie-keten** voor een Tesla-deadline: welke component eigenaar is van command lifecycle, afgeleide deadline-state, realtime execution en fysieke Easee-writes.

De **actuele LIVE-keten sinds 9 oktober 2026** is:

```text
Private EMS Invoer V2 (Tailscale)
  ↓ POST /web/commands/tesla + control-PIN
Caddy → Pi Status API 127.0.0.1:3100/commands/tesla
  ↓ validatie, idempotency en atomaire opslag
/home/jeroen/ems/data/tesla-deadline-command.json
  ↓ directe afleiding + lokale watchdog
Pi deadline derived-state builder
  ↓
/home/jeroen/ems/data/ev-deadline-shadow-state.json
  ↓
Pi /control/current
  ↓
Homey PI Dynamic Planner Bridge v1.5.9
  ↓
EV Power Adapter v0.2.0 → EV Gate v0.3.0
  ↓
EV Power writer v0.4.6 [LIVE]
  ↓
Easee / Tesla
```

De historische Cloudflare Worker → GitHub → Pi-fetchroute is sinds de V1.1-cutover geen productie-ingress meer. Het oude GitHub-commandbestand kan nog bestaan voor legacy-doeleinden, maar mag de lokale Pi-commandstate nooit overschrijven.

Pi is deadline lifecycle/planning authority. Homey remains realtime executor/safety boundary and the guarded EV writer is the sole automatic physical Easee writer.

## 1. Website → lokale Pi-ingress (LIVE)

De private Invoer V2 is uitsluitend via Tailscale bereikbaar. De browser stuurt een JSON-POST naar `/web/commands/tesla` met `X-Tesla-Control-Pin` en een `clientRequestId` voor idempotente retries. Caddy routeert deze uitsluitend op het Pi-tailnet-adres naar de loopback-gebonden Status API. De PIN wordt geverifieerd via het host-lokale bestand `/etc/ems/tesla-control.pin` en staat nooit in Git.

De broncode is `frontend/settings/control/tesla-deadline.js` (browser), `deploy/caddy/ems-frontend-v2.Caddyfile` (private ingress) en `services/pi/api/status/tesla_command_ingest.py` (enige actieve deadline-commandwriter).

## 2. Lokale commandbron (LIVE)

De Pi valideert tijd, SoC, `maxA` en het berekende doel met kalibratie 0,62 kWh per SoC-procent. Hij genereert server-side `requestId` en schrijft de geaccepteerde opdracht atomair naar `/home/jeroen/ems/data/tesla-deadline-command.json`. Ongeldige opdrachten overschrijven nooit de vorige geldige command. De input-SoC is geen live Tesla-telemetrie.

`GET /web/commands/current` leest dezelfde Pi-runtimecommand als de afgeleide deadline-statebuilder. De bestaande `ems-ev-deadline-command.path` en `ems-ev-deadline-state.timer/.path/.service` verzorgen lokale triggers en herstel zonder GitHub-polling.

## 3. Uitgefaseerde GitHub-commandfetch (historisch)

Tot de cutover van **9 oktober 2026** liep de route via Cloudflare Worker → GitHub Contents API → `docs/data/tesla-deadline-command.json` → 60-seconden Pi GitHub-fetcher. Op 1 oktober trad daarbij aantoonbare cachevertraging op. Sinds 9 oktober is de GitHub-fetchservice gestopt en de timer uitgeschakeld; dit blijft historische context, **niet** de actuele commandbron. De overgebleven Worker kan nog een apart EMS-instellingencommand verwerken. Zie sectie 12 voor cutover- en live-validatiebewijs.

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
- lokale command-ingress- en verwerkingslatentie;
- eventuele fysieke veiligheidsbegrenzing.

Wanneer een request pas ná `latestStartAt` wordt ingevoerd of ontvangen, moet de executor direct maximaal toegestaan deadline-laden aanvragen, maar dat kan een reeds onhaalbare deadline niet alsnog haalbaar maken.

## 9. Diagnosevolgorde (LIVE)

1. Controleer browser-POST `/web/commands/tesla` via het Tailscale-adres, PIN-beveiliging en serverantwoord (200/202).
2. Controleer de lokaal opgeslagen command `/home/jeroen/ems/data/tesla-deadline-command.json`: requestId, deadline, SoC en `maxA`.
3. Controleer `/home/jeroen/ems/data/ev-deadline-shadow-state.json` en `GET /control/current`: identieke requestId, `TRACKING`, freshness, deadline.valid en authority PI.
4. Controleer Homey Bridge v1.5.9, Adapter v0.2.0 en Gate v0.3.0 op executor-evidence.
5. Controleer de enige fysieke EV writer v0.4.6 en de Easee-readback (stroom, fasen, vermogen).

GitHub-commits en de voormalige fetchstatus zijn **geen** stappen in de huidige deadline-diagnose.

## 10. Verantwoordelijkheden (LIVE)

```text
Invoer V2         = gebruikersintentie via Tailscale
Pi Status API     = PIN-authenticatie, validatie, command-ingress en atomaire opslag
Pi deadline state = lifecycle, voortgang en latestStart
Pi Planner/API    = planning + deadline-executioncontract
Homey Bridge      = realtime executor guard + canonical Power Intent
EV Adapter/Gate   = vertaling + veiligheidsvalidatie
EV writer         = enige automatische fysieke Easee-write
Easee/Equalizer   = lokale elektrische safety
```

Er is één lokale deadline-commandbron, één planner/deadline-authority (Pi) en één automatische fysieke EV-writer (Homey). Legacy GitHub-commandfetch mag deze bron niet vervangen.

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

Source: merged PR #213, `6b2a2de8da64d542232c1cb42c0658e6eb50fc07`. On 2026-10-09 the Pi deployed the V1.1 Status API, Web Data API, website and private Caddy configuration. The old `ems-ev-deadline-command.timer` and command fetch service were explicitly disabled/stopped. The Pi command file is now the sole runtime source; the existing Homey Bridge/Gate/Actuator are untouched. The initial live website→Pi→Easee test on 2026-10-09 is recorded below; exact per-request Homey Bridge/Gate provenance remains open.

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

**Initial live E2E evidence — 2026-10-09 22:38–22:39 CEST:** User submitted
40% → 60%, `maxA=10`, `goalKWh=12.4`, deadline 23:15 CEST.
- Request `e7f60e72-526f-49b6-b89a-12eb4544dbd6` persisted at
  `2026-10-09T20:38:47.502Z`.
- Existing derived-state builder produced `TRACKING` for the **same requestId**
  at `2026-10-09T20:38:47.595006Z` (~93 ms). Pi `/control/current`
  returned `READY`, `PLANNER`, `deadline.valid=true`,
  `active=true`, `maxA=10` and that same requestId.
- Homey Insights `evcharger_charging` switched `false → true` at
  `2026-10-09T20:39:16.701Z`. Charge-start signal appeared **29.199 s**
  after the server-side request timestamp. Homey device readback showed
  Easee `Charging`, `evcharger_charging=true`, `target_charger_current=10`,
  `measure_current.offered=10`, `measure_power=5467 W`.
  Historic offered-current/power buckets were zero through 20:38 UTC,
  positive in 20:39 UTC. This is strong temporal end-to-end correlation;
  the individual Homey Bridge/Gate events have **not** been correlated to
  this requestId, so full internal provenance remains unverified.
- Compared with the earlier measured 4m39s (~279s) website→charge event,
  observed time is ~89.5% shorter. Clock differences and the use of
  request-created time as the start of timing are explicit measurement limits.
- **Deadline feasibility WARNING:** Pi computed
  `latestStartAt=2026-10-09T19:27:10.434783Z`, i.e. >71 min before the
  new command. At 3×10 A 12.4 kWh requires about 108 min; only ~36 min
  remained at submission. `valid=true` means structurally/execution-valid,
  **not achievable by 23:15**.

**Remaining acceptance:** explicitly correlate the Homey Bridge/Gate events
with the requestId, test cancellation, and independently verify iPhone/cellular
and native SwiftUI ATS/PWA secure-origin behavior.

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
