# Tesla deadline write-route

De website schrijft **niet rechtstreeks naar Homey**. De veilige keten is:

```text
Live energiestroom
   ↓  POST + persoonlijke control-PIN
Cloudflare Worker
   ↓  valideert SOC/deadline + rekent SOC-verschil om naar kWh
GitHub Contents API
   ↓
Tesla deadline command JSON
   ↓  iedere minuut lezen
Homey — Tesla laden v2.7.4
   ↓             ↑
Easee ← besluit  M7 prijs/PV-context (read-only)
   ↓
Equalizer bewaakt 3×25 A en mag begrenzen of volledig pauzeren
```

## Waarom deze architectuur?

De website draait publiek op GitHub Pages. Een Homey-token of GitHub-token mag daarom nooit in JavaScript op de website terechtkomen. De Cloudflare Worker bewaart uitsluitend een beperkt GitHub-token als secret. Homey blijft de enige centrale Tesla-writer; Easee/Equalizer blijft onafhankelijk de lokale installatiebeveiliging uitvoeren.

## Worker-code en SOC-kalibratie

De bron staat in `cloudflare/tesla-deadline-worker.js`. De Worker accepteert alleen requests vanaf `https://onskasteeltje.github.io`, vereist de header `X-Tesla-Control-Pin` en valideert deadline, huidige SOC, doel-SOC en maximale laadstroom van 6–16 A.

De eerste praktijkkalibratie is `71% → 90% · 3×10 A · circa 7,1 kW · Tesla ETA 1u35`. Daaruit volgt voorlopig **0,59 kWh per procentpunt**. Het command-JSON bewaart zowel `currentSoc` en `targetSoc` als het intern afgeleide `goalKWh`.

## Benodigde Cloudflare secrets

- `GITHUB_TOKEN` — fine-grained GitHub token met alleen **Contents: Read and write** voor repository `OnsKasteeltje/homey-energy-manual`.
- `WRITE_PIN` — eigen, niet hergebruikte PIN/wachtwoordzin voor wijzigingen vanaf de website.

De PIN wordt niet in GitHub opgeslagen. De website vraagt hem alleen op het moment dat een wijziging wordt opgeslagen.

## Homey v2.7.4

`Tesla laden v2.7.4` is de enige automatische Easee-writer voor deze deadline-route en draait iedere minuut. Alleen een nieuwe `requestId` wordt als nieuwe gebruikersopdracht verwerkt. In dezelfde Homey-run wordt eerst de actuele Easee `meter_power` gelezen en daarna exact één **meetbaseline** voor die requestId opgeslagen. De baseline bevat minimaal:

- requestId;
- huidige SOC en doel-SOC;
- `socEnteredAt` uit de website-opdracht;
- gebruikte `calibrationKWhPerPercent`;
- afgeleid `goalKWh`;
- Easee `baseMeterKWh`;
- exact `baselineCapturedAt`-tijdstip.

De baseline is **immutable voor dezelfde requestId**. Een Homey-reboot, nieuwe flowversie, wijziging van prijs/PV-context of Equalizerstatus mag geen nieuwe meterbasis maken. Alleen een nieuwe website-opdracht met een nieuwe requestId maakt een nieuwe baseline.

De voortgang wordt daarna uitsluitend bepaald uit:

```text
deliveredSinceBaselineKWh = currentMeterKWh - baselineMeterKWh
remainingKWh = max(0, goalKWh - deliveredSinceBaselineKWh)
```

De deadline-lifecycle en het resterende energiedoel zijn vanaf v2.7.4 bewust van elkaar gescheiden. `EV Deadline actief` betekent uitsluitend dat de harde deadline nog loopt. Een na de deadline nog openstaand expliciet energiedoel wordt afzonderlijk in de runtime-state bijgehouden via `postDeadlineTargetOpen`.

### Fail-safe bij baseline- of kalibratieproblemen

Als een actieve deadline geen geldige baseline voor de actieve requestId heeft, publiceert v2.7.4 **`BASELINE_FOUT`** en vraagt Homey 0 A. De gebruiker kan dit herstellen door de actuele SOC en deadline opnieuw op te slaan, waardoor een nieuwe requestId en exacte baseline ontstaan.

Daarnaast geldt een sanity-check op de gemeten energie. Wanneer de Easee-delta meer wordt dan **1,5× het berekende doel plus 0,25 kWh**, publiceert v2.7.4 **`KALIBRATIE_AFWIJKING`** en stopt de automatische aanvraag voor die afwijkende sessie. De software verandert de kalibratiefactor van 0,59 kWh/% daarbij nooit automatisch; eerst moet de sessie inhoudelijk worden beoordeeld.

## Deadline, prijs en PV

De deadline is een harde constraint. Vóór het berekende `EV Latest start` gebruikt v2.7.4 aanvullend de read-only M7-variabelen:

- `M7_Price_Negative` — huidige prijs is negatief;
- `M7_Price_Cheap_Next4h` — huidige prijs is lager dan de volgende vier uur;
- `M7_Price_Expensive_Next4h` — huidige prijs is hoger dan de volgende vier uur;
- `M7_PV_Top4h` — het huidige uur is één van de vier uren met de hoogste zonne-forecast tussen 09:00 en 18:00.

Actueel PV-overschot heeft voorrang. Een gunstige prijs nu kan een actieve deadline versnellen met maximaal de ingestelde laadstroom. Als het huidige uur volgens de forecast tot de beste PV-uren behoort en de prijs niet ongunstig is, mag v2.7.4 met 6 A laden wanneer het actuele overschot nog niet voldoende is voor 6 A. **Vanaf Latest start blijft Homey maximaal de ingestelde laadstroom vragen**, ongeacht prijs of forecast.

## Deadline-lifecycle

De deadline-state machine kent conceptueel de volgende toestanden:

```text
NO_DEADLINE
    ↓ nieuwe opdracht
DEADLINE_ACTIVE
    ├─ doel vóór/op deadline bereikt → DEADLINE_REACHED
    └─ deadline verstreken + doel open → DEADLINE_MISSED
                                         ↓
                              postDeadlineTargetOpen=true
                                         ↓
                           doorladen op ingestelde maxA
                                         ↓
                           doel bereikt → normale policy
```

### Deadline bereikt

Als `remainingKWh <= 0,01` terwijl de deadline nog actief is:

- wordt de lifecycle `DEADLINE_REACHED`;
- wordt `EV Deadline actief = false`;
- wordt `postDeadlineTargetOpen = false`;
- wordt het bereiken van het doel met tijdstip in de runtime-state gelogd;
- hervat daarna de normale Tesla/PV-policy.

### Deadline gemist

Als het deadline-tijdstip is verstreken terwijl `remainingKWh > 0,01`:

- wordt de lifecycle `DEADLINE_MISSED`;
- wordt **direct** `EV Deadline actief = false`;
- wordt `postDeadlineTargetOpen = true` zolang het expliciete energiedoel nog openstaat;
- blijft Tesla laden op de **ingestelde `EV Max laadstroom A`**;
- prijs- en PV-optimalisatie verlagen dit post-deadline laadverzoek niet;
- Easee Equalizer blijft de harde veiligheidslaag en mag fysiek begrenzen of pauzeren;
- zodra het energiedoel is bereikt, wordt `postDeadlineTargetOpen = false` en hervat de normale Tesla-policy;
- de oude deadline wordt **nooit automatisch naar morgen doorgeschoven**. Een nieuwe harde deadline vereist een expliciete nieuwe gebruikersopdracht.

De normale post-deadline status bij een nog open doel is `DEADLINE_MISSED_DOORLADEN`. Als de Equalizer het daadwerkelijke laden aantoonbaar blokkeert, wordt dit als aparte blokkadestatus gepubliceerd zonder het ingestelde Homey-laadverzoek kunstmatig naar 0 A te verlagen.

## Equalizer begrenzen en volledig blokkeren

De werkelijk geleverde Tesla-kWh is leidend voor de voortgang. `Tesla laden v2.7.4` vergelijkt daarom het Homey-verzoek met het werkelijke Tesla-vermogen en bewaakt onder andere:

- `normal` — geen zichtbare beperking;
- `limited` — de Tesla laadt, maar aantoonbaar onder het gevraagde ampèrage;
- `zero_pending` — Homey vraagt minimaal 6 A maar werkelijk vermogen is vrijwel 0 W; bevestiging loopt;
- `blocked` / `blocked_unknown` — dezelfde toestand houdt circa vier minuten aan en geldt als blokkade.

Bij een blokkade wordt **het Homey-laadverzoek niet verlaagd naar 0 A**. De Equalizer mag de lader lokaal gepauzeerd houden en Easee kan de sessie weer zelfstandig hervatten zodra andere grote verbruikers verdwijnen. Daardoor ontstaat geen conflict tussen Homey en de veiligheidslaag.

Een langdurige beperking of blokkade verhoogt de resterende energie niet kunstmatig: alleen de gemeten Easee-delta sinds de opgeslagen baseline telt. Daardoor wordt `EV Latest start` tijdens de actieve deadline telkens opnieuw uit de resterende kWh berekend.

## Gevalideerde post-deadline smoke test — 21 augustus 2026

De praktijkdeadline van **21 augustus 2026 21:15** werd gemist met circa **2,74 kWh** resterend. Na activering van v2.7.4 is dezelfde sessie gebruikt als smoke test.

Gevalideerd resultaat na Core/publicatie om circa 21:25:

- `deadline_active = false`;
- Tesla bleef fysiek laden;
- werkelijk Tesla-vermogen circa **7,11 kW**;
- ingestelde laadstroom **10 A**;
- `remaining_kwh = 2,74` in de betreffende Core-snapshot;
- de Core gaf niet langer `TESLA_CHARGE_DEADLINE` als actieve MUST-intent;
- Easee/Equalizer bleef de fysieke veiligheidslaag.

Daarmee is het afgesproken einde-deadlinegedrag functioneel aangetoond: **een gemiste deadline eindigt als deadline, maar een nog open expliciet energiedoel blijft op het ingestelde laadvermogen doorladen.**
