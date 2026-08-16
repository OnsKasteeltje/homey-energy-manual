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
   ↓  iedere 2 minuten lezen
Homey — Tesla laden v2.5
   ↓             ↑
Easee ← besluit  M7 prijs/PV-context (read-only)
   ↓
Equalizer bewaakt 3×25 A en mag begrenzen of volledig pauzeren
```

## Waarom deze architectuur?

De website draait publiek op GitHub Pages. Een Homey-token of GitHub-token mag daarom nooit in JavaScript op de website terechtkomen. De Cloudflare Worker bewaart uitsluitend een beperkt GitHub-token als secret. Homey blijft de enige centrale energieregelaar; Easee/Equalizer blijft onafhankelijk de lokale installatiebeveiliging uitvoeren.

## Worker-code en SOC-kalibratie

De bron staat in `cloudflare/tesla-deadline-worker.js`. De Worker accepteert alleen requests vanaf `https://onskasteeltje.github.io`, vereist de header `X-Tesla-Control-Pin` en valideert deadline, huidige SOC, doel-SOC en maximale laadstroom van 6–16 A.

De eerste praktijkkalibratie is `71% → 90% · 3×10 A · circa 7,1 kW · Tesla ETA 1u35`. Daaruit volgt voorlopig **0,59 kWh per procentpunt**. Het command-JSON bewaart zowel `currentSoc` en `targetSoc` als het intern afgeleide `goalKWh`.

## Benodigde Cloudflare secrets

- `GITHUB_TOKEN` — fine-grained GitHub token met alleen **Contents: Read and write** voor repository `OnsKasteeltje/homey-energy-manual`.
- `WRITE_PIN` — eigen, niet hergebruikte PIN/wachtwoordzin voor wijzigingen vanaf de website.

De PIN wordt niet in GitHub opgeslagen. De website vraagt hem alleen op het moment dat een wijziging wordt opgeslagen.

## Homey v2.5

`Tesla laden v2.5` leest iedere 2 minuten het command-JSON. Alleen een nieuwe `requestId` wordt als nieuwe gebruikersopdracht verwerkt. In dezelfde Homey-run wordt eerst de actuele Easee `meter_power` gelezen en daarna exact één **meetbaseline** voor die requestId opgeslagen. De baseline bevat minimaal:

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
```

De runtimepublicatie v1.2 geeft de volledige audit naar de website door. Daardoor zijn SOC-moment, meterbasis, actuele meterstand en gemeten delta achteraf rechtstreeks controleerbaar.

### Fail-safe bij baseline- of kalibratieproblemen

Als een actieve deadline geen geldige baseline voor de actieve requestId heeft, publiceert v2.5 **`BASELINE_FOUT`** en vraagt Homey 0 A. De gebruiker kan dit herstellen door de actuele SOC en deadline opnieuw op te slaan, waardoor een nieuwe requestId en exacte baseline ontstaan.

Daarnaast geldt een sanity-check op de gemeten energie. Wanneer de Easee-delta meer wordt dan **1,5× het berekende doel plus 0,25 kWh**, publiceert v2.5 **`KALIBRATIE_AFWIJKING`** en stopt de automatische aanvraag voor die afwijkende sessie. De software verandert de kalibratiefactor van 0,59 kWh/% daarbij nooit automatisch; eerst moet de sessie inhoudelijk worden beoordeeld.

Bij de overgang van v2.4 naar v2.5 wordt een bestaande meterbasis bewust niet opnieuw gezet. Als zo'n oude basis beschikbaar is, wordt hij alleen als **`legacy-unverified`** geïmporteerd. Daarmee blijft de oude rekensom reproduceerbaar, maar geldt de sessie niet als betrouwbare kalibratiemeting.

## Deadline, prijs en PV

De deadline is een harde constraint. Vóór het berekende `EV Latest start` gebruikt v2.5 aanvullend de read-only M7-variabelen:

- `M7_Price_Negative` — huidige prijs is negatief;
- `M7_Price_Cheap_Next4h` — huidige prijs is lager dan de volgende vier uur;
- `M7_Price_Expensive_Next4h` — huidige prijs is hoger dan de volgende vier uur;
- `M7_PV_Top4h` — het huidige uur is één van de vier uren met de hoogste zonne-forecast tussen 09:00 en 18:00.

Actueel PV-overschot heeft voorrang. Een gunstige prijs nu kan een actieve deadline versnellen met maximaal de ingestelde laadstroom. Als het huidige uur volgens de forecast tot de beste PV-uren behoort en de prijs niet ongunstig is, mag v2.5 met 6 A laden wanneer het actuele overschot nog niet voldoende is voor 6 A. **Vanaf Latest start blijft Homey maximaal de ingestelde laadstroom vragen**, ongeacht prijs of forecast.

### Equalizer begrenzen en volledig blokkeren

De werkelijk geleverde Tesla-kWh is leidend voor de voortgang. `Tesla laden v2.5` vergelijkt daarom het Homey-verzoek met het werkelijke Tesla-vermogen en publiceert in de runtime één van vier Equalizer-modi:

- `normal` — geen zichtbare beperking;
- `limited` — de Tesla laadt, maar aantoonbaar onder het gevraagde ampèrage;
- `blocked_pending` — Homey vraagt minimaal 6 A maar werkelijk vermogen is vrijwel 0 W; bevestiging loopt;
- `blocked` — dezelfde toestand houdt circa vier minuten aan en wordt als volledige Equalizer-blokkade beschouwd.

Bij `blocked` wordt **het Homey-laadverzoek niet verlaagd naar 0 A**. De Equalizer mag de lader lokaal gepauzeerd houden en Easee kan de sessie weer zelfstandig hervatten zodra andere grote verbruikers verdwijnen. Daardoor ontstaat geen conflict tussen Homey en de veiligheidslaag.

Een langdurige beperking of blokkade verhoogt de resterende energie niet kunstmatig: alleen de gemeten Easee-delta sinds de opgeslagen baseline telt. Daardoor wordt `EV Latest start` iedere twee minuten opnieuw uit de resterende kWh berekend. Een bevestigde blokkade krijgt vóór latest-start status `DEADLINE_EQUALIZER_BLOKKEERT`, na latest-start `DEADLINE_ONDER_DRUK_EQUALIZER` en na de deadline met resterende energie `DEADLINE_NIET_HAALBAAR_EQUALIZER`.

Zonder deadline blijft de Tesla alleen opportunistisch/exportbuffer laden; een lage of negatieve prijs veroorzaakt dan op zichzelf geen netladen.
