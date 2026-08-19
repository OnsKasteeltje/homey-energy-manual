# Home Energy als app installeren

De website is als **Progressive Web App (PWA)** ingericht. Daardoor kan dezelfde live Energy Manager-interface als zelfstandige app op iPhone en andere ondersteunde apparaten worden geopend, zonder aparte native app-code.

## iPhone / iPad

1. Open de Home Energy-website in **Safari**.
2. Tik op **Deel**.
3. Kies **Zet op beginscherm**.
4. Controleer de naam **Home Energy** en tik op **Voeg toe**.
5. Open daarna het nieuwe Home Energy-icoon vanaf het beginscherm.

De app opent in standalone-weergave. De gewone desktopwebsite blijft ongewijzigd beschikbaar.

## Refresharchitectuur

Vanaf `app-shell-v2.0.17` gebruikt de app één centrale refreshroute. De actieve datacomponenten worden opnieuw aangestuurd bij:

- openen/starten van de app;
- terugkeer uit de achtergrond (`visibilitychange` / foreground-resume);
- `pageshow` en opnieuw focus krijgen;
- opnieuw online komen;
- pull-to-refresh;
- periodiek iedere **5 minuten**.

De bedoeling is nadrukkelijk niet alleen de bestaande DOM opnieuw te tekenen: componenten halen hun relevante JSON-feed opnieuw op. Dynamische statusfeeds gebruiken `cache: no-store` en/of een unieke timestamp om een oude browsercache te vermijden.

De architectuur blijft:

```text
Homey / Energy Core
       ↓ bestaande publishers
GitHub JSON-feeds
       ↓ centrale app refresh-trigger
schermcomponenten → nieuwe fetch → render
```

De app-refresh veroorzaakt daarmee **geen nieuwe Homey-devicepolls**. Homey blijft via de bestaande Energy Core/publisherarchitectuur data produceren; de app leest uitsluitend de reeds gepubliceerde feeds opnieuw.

## Dataversheid

De service worker mag statische pagina- en vormgevingsbestanden cachen voor snellere heropening en beperkte offline-weergave. Live `.json`-statusfeeds worden bewust niet als statische waarheid gebruikt.

Voor schermen met freshnessinformatie geldt hetzelfde model als bij Energiehistorie:

- **< 15 minuten:** actueel;
- **15–30 minuten:** vertraagd;
- **> 30 minuten:** data verouderd.

Waar beschikbaar toont de UI zowel de leeftijd van de publicatie als de leeftijd van de onderliggende bronstate. Daarmee is onderscheid mogelijk tussen een werkelijk achterlopende Homey/GitHub-feed en een app die alleen nog een oudere schermweergave toont.

## Acceptatietest

De structurele refreshimplementatie is gereed. De resterende praktijkcontrole is:

1. open de app en noteer actuele waarden/tijd;
2. zet de app 20–30 minuten op de achtergrond terwijl de energiegegevens veranderen;
3. open de app opnieuw;
4. controleer dat Home/Live/Historie zonder handmatige reload binnen enkele seconden nieuwe data/freshness tonen;
5. controleer aanvullend dat de periodieke 5-minutenrefresh blijft functioneren.

## Onderhoud

De PWA gebruikt één codebase met de bestaande MkDocs-site. Wijzigingen aan live energiestroom, flows, historie en documentatie worden daardoor onderdeel van zowel website als geïnstalleerde app zodra de nieuwe siteversie is gepubliceerd.

> Laatste update: **19 augustus 2026** — centrale app-refresh via `app-shell-v2.0.17`, expliciete no-cache data-refresh en uniform freshnessmodel, zonder extra Homey-device-reads.
