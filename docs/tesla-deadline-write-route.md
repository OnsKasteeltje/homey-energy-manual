# Tesla deadline write-route

De website schrijft **niet rechtstreeks naar Homey**. De veilige keten is:

```text
Live energiestroom
   ↓  POST + persoonlijke control-PIN
Cloudflare Worker
   ↓  GitHub Contents API
Tesla deadline command JSON
   ↓  iedere 2 minuten lezen
Homey — Tesla laden v2.1
   ↓
EV Deadline actief / tijd / kWh / max A
   ↓
Easee dynamische laadstroom
```

## Waarom deze architectuur?

De website draait publiek op GitHub Pages. Een Homey-token of GitHub-token mag daarom nooit in JavaScript op de website terechtkomen. De Cloudflare Worker bewaart uitsluitend een beperkt GitHub-token als secret. Homey blijft zelf de enige partij die apparaten aanstuurt.

## Worker-code

De bron staat in:

`cloudflare/tesla-deadline-worker.js`

De Worker accepteert alleen requests vanaf `https://onskasteeltje.github.io`, vereist daarnaast de header `X-Tesla-Control-Pin`, valideert datum/tijd, kWh-doel en maximale laadstroom en schrijft daarna `docs/data/tesla-deadline-command.json`.

## Benodigde Cloudflare secrets

- `GITHUB_TOKEN` — fine-grained GitHub token met alleen **Contents: Read and write** voor repository `OnsKasteeltje/homey-energy-manual`.
- `WRITE_PIN` — eigen, niet hergebruikte PIN/wachtwoordzin voor wijzigingen vanaf de website.

De PIN wordt niet in GitHub opgeslagen. De website vraagt hem alleen op het moment dat een wijziging wordt opgeslagen.

## Eenmalige activatie

1. Maak in Cloudflare Workers & Pages een nieuwe Worker.
2. Plak de inhoud van `cloudflare/tesla-deadline-worker.js` en deploy.
3. Voeg onder Worker Settings → Variables and Secrets de secrets `GITHUB_TOKEN` en `WRITE_PIN` toe.
4. Kopieer de publieke Worker-URL, bijvoorbeeld `https://tesla-deadline.<account>.workers.dev`.
5. Zet die URL in `docs/data/tesla-control-config.json` bij `worker_url`.
6. Na de volgende GitHub Pages-deploy wordt **Instelling opslaan** op Live energiestroom actief.

## Homey

`Tesla laden v2.1` leest iedere 2 minuten het command-JSON. Alleen een nieuwe `requestId` wordt verwerkt. Bij netwerk- of JSON-fouten blijft de bestaande Homey-instelling ongemoeid.

De opdracht ondersteunt:

- deadline uit: `active=false`;
- deadline aan: lokale datum/tijd `YYYY-MM-DDTHH:mm`;
- minimaal te laden energie: 1–75 kWh;
- maximale laadstroom: 6–16 A.

De Easee Equalizer blijft de harde lokale veiligheidslaag en kan de werkelijk geleverde laadstroom zelfstandig begrenzen.
