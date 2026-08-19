# Home Energy als app installeren

De website is als **Progressive Web App (PWA)** ingericht. Daardoor kan dezelfde live Energy Manager-interface als zelfstandige app op iPhone en andere ondersteunde apparaten worden geopend, zonder aparte native app-code.

## iPhone / iPad

1. Open de Home Energy-website in **Safari**.
2. Tik op **Deel**.
3. Kies **Zet op beginscherm**.
4. Controleer de naam **Home Energy** en tik op **Voeg toe**.
5. Open daarna het nieuwe Home Energy-icoon vanaf het beginscherm.

De app opent in standalone-weergave. De gewone desktopwebsite blijft ongewijzigd beschikbaar.

## Dataversheid

De service worker mag statische pagina- en vormgevingsbestanden cachen voor snellere heropening en beperkte offline-weergave. Live `.json`-statusfeeds worden bewust **niet** gecachet, zodat Homey-, energie- en shadowdata altijd via het actuele publicatiepad worden opgehaald.

## Onderhoud

De PWA gebruikt één codebase met de bestaande MkDocs-site. Wijzigingen aan live energiestroom, flows, historie en documentatie worden daardoor automatisch onderdeel van zowel website als geïnstalleerde app zodra de nieuwe siteversie is gepubliceerd.
