# Energiecontracten: FIXED en DYNAMIC

_Status: kandidaatarchitectuur — stappen 1 en 2 gebouwd op 19 augustus 2026; stap 3 shadow-validatie gestart op 19 augustus 2026._

## Doel

De Energy Manager ondersteunt structureel twee contracttypes:

- `FIXED`: vaste afname- en teruglevertarieven, eventueel normaal/dal.
- `DYNAMIC`: actuele en toekomstige markt-/leveranciersprijzen via PBTH.

De contractkeuze mag niet door alle beslisflows heen lekken. Beide routes worden daarom eerst genormaliseerd naar één uniforme prijscontext. Tesla-, warmwater- en toekomstige Victron-logica lezen daarna alleen die context.

## Productiebaseline

De bestaande productieflows blijven ongewijzigd en actief:

- `EM v2 | 30 Context | Price + PV v0.5`
- `EM v2 | 00 Core Tick | v0.9.8`

De nieuwe contractflows draaien tijdens stap 3 parallel naast deze baseline, uitsluitend in shadow en zonder actuatorwrites.

## Stap 1 — contractconfiguratie en Price Adapter

Kandidaatflow:

- `EM v2 | 30 Context | Contract Price Adapter v0.7`
- Homey flow-id: `b1c495cb-6ccd-4fb8-b4bf-365845dbb6e7`
- status: `enabled=true`, `broken=false`, `SHADOW_CANDIDATE`

Centrale configuratie:

| Variabele | Type | Initiële waarde | Betekenis |
|---|---|---:|---|
| `EM2_Contract_Type` | string | `DYNAMIC` | `FIXED` of `DYNAMIC` |
| `EM2_Contract_EndDate` | string | `2026-09-25` | einddatum huidig vaste contract |
| `EM2_Fixed_Import_Normal` | number | `0.23790` | vaste afnameprijs normaal in EUR/kWh |
| `EM2_Fixed_Import_Offpeak` | number | `0.23548` | vaste afnameprijs dal in EUR/kWh |
| `EM2_Fixed_Export` | number | `0.15000` | waarde teruglevering in EUR/kWh |
| `EM2_Fixed_Offpeak_Active` | boolean | `false` | expliciete input die aangeeft of daltarief geldt |
| `EM2_Contract_Config_Schema` | string | `EM2_CONTRACT_CONFIG_V0.2` | configuratieschema |

De vaste dagelijkse contractkosten zijn bewust geen optimalisatie-input: ze veranderen niet door een verbruiksactie te verschuiven.

### FIXED-pad

Bij `FIXED` wordt PBTH volledig overgeslagen. De adapter kiest normaal/dal via `EM2_Fixed_Offpeak_Active`, stelt de actuele import- en exportwaarde vast en berekent het actuele voordeel van directe zelfconsumptie:

`selfUseGainNow = importPriceNow - exportPriceNow`

De precieze normaal/dal-kalender is nog niet hardcoded. Dat voorkomt een onbevestigde aanname en wordt bij de selector/tariefregeling aangesloten.

### DYNAMIC-pad

Bij `DYNAMIC` vraagt de adapter PBTH `next_hours` op en analyseert de 15-minutenreeks rechtstreeks. M7-prijsclassificaties zijn niet langer nodig.

De adapter berekent:

- actuele import- en exportprijs;
- minimum, maximum en gemiddelde prijs voor de komende 4 uur;
- P25 en P75 over de beschikbare prijshorizon;
- `negativeNow` direct uit `price_now < 0`;
- `cheapNow` en `expensiveNow` op basis van P25/P75 en een minimale economische drempel van EUR 0,02/kWh ten opzichte van het gemiddelde van de komende 4 uur;
- `cheapNext4h` en `expensiveNext4h` op basis van het gemiddelde van de komende 4 uur versus P25/P75;
- kwaliteit en bruikbare horizon (`FULL`, `INTRADAY` of `DIAGNOSTIC`).

Hierdoor bevat de kandidaatprijsadapter geen reads meer van `M7_Price_Negative`, `M7_Price_Cheap_Next4h` of `M7_Price_Expensive_Next4h`.

### Geïsoleerde uniforme prijsinterface

Om parallelle shadow-validatie veilig te maken schrijft de kandidaatadapter niet over de bestaande `EM2_Price_*` productievariabelen. De kandidaatinterface gebruikt onder meer:

- `EM2_ContractPrice_Context`
- `EM2_ContractPrice_Import_Now`
- `EM2_ContractPrice_Export_Now`
- `EM2_ContractPrice_SelfUse_Gain`
- `EM2_ContractPrice_Negative`
- `EM2_ContractPrice_Cheap_Now`
- `EM2_ContractPrice_Expensive_Now`
- `EM2_ContractPrice_Cheap_Next4h`
- `EM2_ContractPrice_Expensive_Next4h`
- `EM2_ContractPrice_Min_Next4h`
- `EM2_ContractPrice_Max_Next4h`
- `EM2_ContractPrice_Avg_Next4h`
- `EM2_ContractPrice_P25`
- `EM2_ContractPrice_P75`
- `EM2_ContractPrice_Source`
- `EM2_ContractPrice_Quality`
- `EM2_ContractPrice_Horizon`
- `EM2_ContractPrice_HorizonHours`
- `EM2_ContractPrice_UpdatedAt`

De context heeft schema `EM2_UNIFORM_PRICE_CONTEXT_V0.2` en bevat contracttype, contracteinddatum, bron, kwaliteit, actuele importprijs, exportwaarde, zelfconsumptiewaarde, prijsstatistiek en prijshorizon.

## Stap 2 — contract-onafhankelijke beslislaag

Kandidaatflow:

- `EM v2 | 40 Decision | Contract-aware v0.1`
- Homey flow-id: `56b87a5c-645c-4a95-9744-880c4d0353bd`
- status: `enabled=true`, `broken=false`, `SHADOW_CANDIDATE`

Deze flow gebruikt de bestaande `EM2_State` en `EM2_WW_State`, zodat geen extra apparaatpolling nodig is. Voor prijsbesluiten leest hij uitsluitend `EM2_ContractPrice_*`.

De flow maakt read-only kandidaatbesluiten voor:

- Tesla: deadline, beschikbare export, prijsopportunity en importbudget.
- Warm water: dagdoel, deadline/catch-up, export, PV-opportunity, prijsopportunity en importbudget.

Outputs:

- `EM2_Decision_ContractCandidate`
- `EM2_Control_WW_ContractCandidate`
- `EM2_ContractDecision_Status`

Alle outputs staan op `SHADOW_CANDIDATE`. Er zijn geen writes naar Tesla, boiler of Quatt.

## Veiligheidsinvarianten

1. De huidige actieve v0.5/v0.9.8-route wordt door stappen 1 en 2 niet gewijzigd.
2. Beide nieuwe flows draaien in stap 3 uitsluitend parallel in shadow.
3. De kandidaatprijscontext heeft een eigen namespace en kan daardoor parallel naast productie draaien.
4. `FIXED` heeft geen externe PBTH-afhankelijkheid.
5. `DYNAMIC` classificeert prijs volledig binnen de adapter; downstream bestaat geen M7-prijsafhankelijkheid meer.
6. Ontbrekende of verouderde prijscontext maakt prijsoptimalisatie onbruikbaar; deadline-, comfort-, PV- en veiligheidslogica blijven de fallback.
7. Er zijn geen fysieke actuatorwrites in deze kandidaatflows.

## Stap 3 — shadow-validatie

_Status: gestart op 19 augustus 2026._

Uitgevoerd:

- kandidaatadapter gecontroleerd geactiveerd;
- kandidaatbeslisflow gecontroleerd geactiveerd;
- beide flows handmatig gestart zonder startfout;
- safety-check bevestigd: `broken=false`, geïsoleerde kandidaatnamespace en geen actuatorwrites.

Nog te valideren:

- `DYNAMIC` kandidaatbesluiten vergelijken met de huidige v0.5/v0.9.8-besluiten;
- de nieuwe P25/P75-classificaties observeren op verschillende prijsprofielen;
- daarna dezelfde situaties met `FIXED` simuleren;
- verschillen classificeren als verwacht contracteffect, logische verbetering of fout;
- PBTH-callbelasting bewaken wanneer de kandidaatadapter parallel draait.

Observatiebeperking: de Homey Insights-connector levert voor de nieuw aangemaakte kandidaatvariabelen momenteel historische `null`-punten terug en kan die reeks daardoor niet correct parseren. Dit verhindert op dit moment een betrouwbare externe readback van de kandidaatwaarden; daarom is nog geen FIXED-simulatie gestart.

## Stap 4 — selector en cut-over

Na succesvolle shadow-validatie:

- website-instelling `FIXED | DYNAMIC` toevoegen;
- normaal/dal-regeling voor FIXED expliciet aan de configuratie koppelen;
- kandidaatinterface promoveren tot canonieke prijsinterface;
- actieve beslislaag op de uniforme prijsinterface laten draaien;
- actieve flowversies gecontroleerd vervangen en oude versies uitschakelen.
