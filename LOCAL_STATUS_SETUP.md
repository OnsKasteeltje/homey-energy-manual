# Lokale Homey → GitHub status-sync

## Architectuur

```text
Homey
  │  lokaal: leest Flow-status
  │
  └── elke 15 minuten HTTPS PUT
             │
             ▼
GitHub repository
docs/data/homey-status.json
             │
             ▼
Homey Energy Dashboard
```

GitHub maakt **geen verbinding naar Homey**. Alleen Homey maakt een uitgaande HTTPS-verbinding naar GitHub.

## Homey-flow

De Advanced Flow `GitHub status sync - Homey lokaal` is aangemaakt maar staat aanvankelijk uit.

Hij publiceert onder andere:

- enabled/broken/status van de relevante energieflows;
- `WW_Boilermodus`;
- indien beschikbaar `EM Shadow Status`;
- synchronisatietijd.

## Vereiste GitHub-token

Maak een **fine-grained Personal Access Token** voor uitsluitend:

- eigenaar: `OnsKasteeltje`;
- repository: `homey-energy-manual`;
- repository permission: **Contents — Read and write**.

Geef geen bredere rechten dan nodig.

## Token lokaal in Homey plaatsen

Maak in Homey bij Logic een **Tekst**-variabele:

`GH_Status_Token`

Plak daar de fine-grained GitHub-token in.

Let op: een Homey Logic-variabele is geen echte secret vault. Gebruikers met voldoende toegang tot jouw Homey/Logic kunnen de waarde zien. De token is daarom bewust beperkt tot één repository en alleen Contents read/write.

## Eerste test

1. Vul `GH_Status_Token`.
2. Activeer `GitHub status sync - Homey lokaal`.
3. Wacht op de eerstvolgende 15-minutentrigger.
4. Controleer in GitHub `docs/data/homey-status.json`.
5. Controleer dat `generated_at` actueel is en `source` `Homey lokaal via HomeyScript` vermeldt.
6. Open de Pages-site en ververs de homepage.

## Oude GitHub-sync verwijderen

De oude workflow `.github/workflows/sync-homey-status.yml` hoort niet meer in de repository. Deze websiteversie bevat hem daarom niet.

## Geen Pages-build per statusupdate

De homepage leest het live JSON-bestand rechtstreeks uit de `main` branch. De Pages-workflow negeert commits die alleen `docs/data/homey-status.json` wijzigen. Daardoor veroorzaakt een 15-minuten statusupdate geen volledige MkDocs-build.
