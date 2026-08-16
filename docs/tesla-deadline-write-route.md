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
Homey — Tesla laden v2.2
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

## Homey v2.2

`Tesla laden v2.2` leest iedere 2 minuten het command-JSON. Alleen een nieuwe `requestId` wordt verwerkt. Bij netwerk- of JSON-fouten blijft de bestaande Homey-instelling ongemoeid. `Tesla laden v2.1` is uitgeschakeld zodat er slechts één automatische Easee-writer actief is.

De deadline is een harde constraint. Vóór het berekende `EV Latest start` gebruikt v2.2 aanvullend de read-only M7-variabelen:

- `M7_Price_Negative`;
- `M7_Price_Cheap_Next4h`;
- `M7_Price_Expensive_Next4h`;
- `M7_PV_Top4h`.

Actueel PV-overschot, negatieve prijs, PV-forecast en goedkoop/duur prijsvenster mogen het laadmoment optimaliseren. **Vanaf Latest start wordt altijd catch-up gestart op de ingestelde maximale laadstroom**, ongeacht de forecast. Zonder deadline blijft de Tesla alleen opportunistisch/exportbuffer laden en veroorzaakt een lage prijs op zichzelf geen netladen.

De Easee Equalizer blijft de harde lokale veiligheidslaag en kan de werkelijk geleverde laadstroom zelfstandig begrenzen.
