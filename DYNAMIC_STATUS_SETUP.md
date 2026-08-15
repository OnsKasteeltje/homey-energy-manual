# Dynamische Homey-status instellen

Deze websiteversie toont flowstatus dynamisch vanuit `docs/data/homey-status.json`.

## 1. GitHub Secrets

Ga in de repository naar:

**Settings → Secrets and variables → Actions → New repository secret**

Maak:

- `HOMEY_ID`
- `HOMEY_TOKEN`

Zet Homey-inloggegevens of tokens **nooit** in Markdown, JavaScript of een publiek repositorybestand.

## 2. Eerste test

Ga naar **Actions → Sync Homey status → Run workflow**.

Als de workflow slaagt, wordt `docs/data/homey-status.json` automatisch bijgewerkt en gecommit.

## 3. Automatisch

De workflow staat op iedere 15 minuten. GitHub scheduled workflows kunnen wat vertraging hebben; het dashboard toont daarom altijd de laatst bekende synchronisatietijd.

## 4. Shadow-status

`status-config.json` markeert `Energie Manager PV - Shadow Mode` bewust als `shadow`, ook al is de Homey-flow technisch enabled.

## 5. Beveiliging

De site zelf leest uitsluitend een publiek JSON-statusbestand. De Homey-token wordt alleen door GitHub Actions gebruikt via GitHub Secrets.
