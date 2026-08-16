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
Homey — Tesla laden v2.3
   ↓             ↑
Easee ← besluit  M7 prijs/PV-context (read-only)
```

## Waarom deze architectuur?

De website draait publiek op GitHub Pages. Een Homey-token of GitHub-token mag daarom nooit in JavaScript op de website terechtkomen. De Cloudflare Worker bewaart uitsluitend een beperkt GitHub-token als secret. Homey blijft zelf de enige partij die apparaten aanstuurt.

## Worker-code en SOC-kalibratie

De bron staat in `cloudflare/tesla-deadline-worker.js`. De Worker accepteert alleen requests vanaf `https://onskasteeltje.github.io`, vereist de header `X-Tesla-Control-Pin` en valideert deadline, huidige SOC, doel-SOC en maximale laadstroom van 6–16 A.

De eerste praktijkkalibratie is `71% → 90% · 3×10 A · circa 7,1 kW · Tesla ETA 1u35`. Daaruit volgt voorlopig **0,59 kWh per procentpunt**. Het command-JSON bewaart zowel `currentSoc` en `targetSoc` als het intern afgeleide `goalKWh`.

## Benodigde Cloudflare secrets

- `GITHUB_TOKEN` — fine-grained GitHub token met alleen **Contents: Read and write** voor repository `OnsKasteeltje/homey-energy-manual`.
- `WRITE_PIN` — eigen, niet hergebruikte PIN/wachtwoordzin voor wijzigingen vanaf de website.

De PIN wordt niet in GitHub opgeslagen. De website vraagt hem alleen op het moment dat een wijziging wordt opgeslagen.

## Homey v2.3

`Tesla laden v2.3` leest iedere 2 minuten het command-JSON. Alleen een nieuwe `requestId` wordt als nieuwe gebruikersopdracht verwerkt. Bij iedere nieuwe `requestId` wordt de energieteller expliciet opnieuw gebaselineerd op de actuele Easee `meter_power`; daardoor hoort de voortgang altijd bij de SOC-momentopname waarmee de deadline is opgeslagen. Bij netwerk- of JSON-fouten blijft de bestaande Homey-instelling ongemoeid. v2.1 en v2.2 zijn uitgeschakeld zodat er slechts één automatische Easee-writer actief is.

De deadline is een harde constraint. Vóór het berekende `EV Latest start` gebruikt v2.3 aanvullend de read-only M7-variabelen:

- `M7_Price_Negative` — huidige prijs is negatief;
- `M7_Price_Cheap_Next4h` — huidige prijs is lager dan de volgende vier uur;
- `M7_Price_Expensive_Next4h` — huidige prijs is hoger dan de volgende vier uur;
- `M7_PV_Top4h` — het huidige uur is één van de vier uren met de hoogste zonne-forecast tussen 09:00 en 18:00.

Actueel PV-overschot heeft voorrang. Een gunstige prijs nu kan een actieve deadline versnellen met maximaal de ingestelde laadstroom. Als het huidige uur volgens de forecast tot de beste PV-uren behoort en de prijs niet ongunstig is, mag v2.3 met 6 A laden wanneer het actuele overschot nog niet voldoende is voor 6 A. **Vanaf Latest start wordt altijd catch-up gestart op de ingestelde maximale laadstroom**, ongeacht prijs of forecast.

Zonder deadline blijft de Tesla alleen opportunistisch/exportbuffer laden; een lage of negatieve prijs veroorzaakt dan op zichzelf geen netladen. De Easee Equalizer blijft de harde lokale veiligheidslaag en kan de werkelijk geleverde laadstroom zelfstandig begrenzen.
