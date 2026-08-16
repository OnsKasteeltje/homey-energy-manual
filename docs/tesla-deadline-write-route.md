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
Homey — Tesla laden v2.1
   ↓
EV Deadline actief / tijd / intern kWh-doel / max A
   ↓
Easee dynamische laadstroom
```

## Waarom deze architectuur?

De website draait publiek op GitHub Pages. Een Homey-token of GitHub-token mag daarom nooit in JavaScript op de website terechtkomen. De Cloudflare Worker bewaart uitsluitend een beperkt GitHub-token als secret. Homey blijft zelf de enige partij die apparaten aanstuurt.

## Worker-code

De bron staat in:

`cloudflare/tesla-deadline-worker.js`

De Worker accepteert alleen requests vanaf `https://onskasteeltje.github.io`, vereist daarnaast de header `X-Tesla-Control-Pin` en valideert:

- lokale deadline-datum/tijd;
- huidige SOC: 0–100%;
- doel-SOC: 1–100% en hoger dan huidige SOC;
- maximale laadstroom: 6–16 A.

De Worker zet daarna het SOC-verschil intern om naar benodigde laadenergie en schrijft `docs/data/tesla-deadline-command.json`.

## SOC-kalibratie

De eerste praktijkkalibratie is:

`71% → 90% · 3×10 A · circa 7,1 kW · Tesla ETA 1u35`

Daaruit volgt voorlopig ongeveer **0,59 kWh per procentpunt**. Deze factor staat centraal in de Worker, zodat toekomstige kalibraties kunnen worden verfijnd zonder de Homey-flow of gebruikersinterface opnieuw te ontwerpen.

Het command-JSON bewaart zowel `currentSoc` en `targetSoc` als het intern afgeleide `goalKWh`. Daardoor blijft `Tesla laden v2.1` compatibel met de bestaande deadline- en catch-upberekening.

## Benodigde Cloudflare secrets

- `GITHUB_TOKEN` — fine-grained GitHub token met alleen **Contents: Read and write** voor repository `OnsKasteeltje/homey-energy-manual`.
- `WRITE_PIN` — eigen, niet hergebruikte PIN/wachtwoordzin voor wijzigingen vanaf de website.

De PIN wordt niet in GitHub opgeslagen. De website vraagt hem alleen op het moment dat een wijziging wordt opgeslagen.

## Homey

`Tesla laden v2.1` leest iedere 2 minuten het command-JSON. Alleen een nieuwe `requestId` wordt verwerkt. Bij netwerk- of JSON-fouten blijft de bestaande Homey-instelling ongemoeid.

De gebruiker stuurt voortaan op **huidige SOC → doel-SOC**. Homey zelf blijft intern op afgeleide laadenergie werken. De Easee Equalizer blijft de harde lokale veiligheidslaag en kan de werkelijk geleverde laadstroom zelfstandig begrenzen.
