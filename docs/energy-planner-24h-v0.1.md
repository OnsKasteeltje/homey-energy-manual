# 24h Energy Planner v0.1

## Status

**Flow:** `EM v2 | 45 Planner | 24h Energy Plan v0.1 SHADOW`  
**Homey flow-id:** `dedb7e15-8795-478b-995a-734f85025a74`  
**Status:** actief, SHADOW/read-only, geen actuatorwrites  
**Cadans:** iedere 15 minuten, 30 s na de kwartiertrigger; daarnaast handmatig startbaar.

Deze planner is de voorbereidende planningslaag voor kostenoptimalisatie vóór de Victron-installatie. Hij verandert geen bestaande realtime control-policy en schrijft niet naar Easee, boiler, Quatt of toekomstige Victron-apparatuur.

## Doel

De planner maakt uit reeds beschikbare context één vooruitkijkend energieplan. De eerste versie doet bewust nog **geen batterijdispatch**. Hij rangschikt prijsvensters, legt harde energieverplichtingen vast en controleert of een toekomstig batterijmodel voldoende is geconfigureerd om in een volgende versie simulaties uit te voeren.

De scheiding is bindend:

```text
Realtime control: P1 + bestaande writers
Planning:        24h Energy Planner SHADOW
Toekomstig:      Victron voert snelle batterij-/netregeling uit
```

## Procesflow — exact overeenkomstig v0.1

```text
15-min trigger
     │
     ├── wacht 30 s
     │
     └──────────────┐
                    ▼
             voer planner uit
                    ▲
                    │
handmatige start ───┘
                    │
                    ▼
Lees Logic-state:
EM2_State · EM2_WW_State · EM2_ContractPrice_Context
TEMP_PBTH_JSON_BUFFER · Tesla deadlinevelden · PV Top4h
                    │
                    ▼
Bepaal contracttype en prijscontext
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
    DYNAMIC                    FIXED
max. 96 geldige          statische prijscontext
15-min prijssloten       geen verzonnen tijdreeks
rangschik goedkoop/duur
       └────────────┬────────────┘
                    ▼
Leg harde verplichtingen vast
- Tesla: MUST_BY_DEADLINE indien actief + resterende kWh
- Warm water: MUST_BY_19:00 of MUST_CATCHUP indien dagdoel open
                    │
                    ▼
Lees optionele Victron-batterijparameters
                    │
             volledig geldig?
             ┌──────┴──────┐
             │             │
            NEE           JA
             │             │
READY_NO_BATTERY_MODEL  READY_WITH_BATTERY_MODEL
WAIT_FOR_VICTRON_       SIMULATE_BATTERY_AND_
BATTERY_PARAMETERS      FLEX_ALLOCATION
             └──────┬──────┘
                    ▼
Publiceer uitsluitend Logic-output:
EM2_Energy_Plan_24h
EM2_Energy_Planner_Status
                    │
                    ▼
STOP — geen actuator/device writes
```

## Inputs

De planner hergebruikt uitsluitend reeds beschikbare state/context en introduceert geen aanvullende devicepoller.

- `EM2_State`: Core-state, inclusief Tesla deadlinegegevens.
- `EM2_WW_State`: warmwaterdagstate en catch-upstatus.
- `EM2_ContractPrice_Context`: uniforme FIXED/DYNAMIC prijscontext.
- `TEMP_PBTH_JSON_BUFFER`: bij DYNAMIC de bestaande 15-minuten prijsreeks.
- `M7_PV_Top4h` en `EM2_Context_UpdatedAt`: alleen een samenvattend PV-forecastsignaal in v0.1.

De PV-forecast wordt in v0.1 **niet** omgezet in een kunstmatig 24-uurs productieprofiel. `pvForecast.quality = SUMMARY_ONLY` maakt die beperking expliciet.

## Prijsplanning

Bij `DYNAMIC` accepteert de planner maximaal 96 aaneengesloten, plausibele 15-minutenprijzen. De beschikbare reeks wordt met P25/P75 geclassificeerd als `NEGATIVE`, `CHEAP`, `NORMAL` of `EXPENSIVE`. De acht goedkoopste en acht duurste beschikbare slots worden in het plan gepubliceerd.

Bij `FIXED` gebruikt de planner `STATIC_FIXED`; er wordt geen dynamische prijsreeks verzonnen.

De prijscontext moet vers en `GOOD` zijn. Zonder bruikbare prijscontext degradeert de planner naar `DEGRADED_PRICE_CONTEXT`; dit heeft geen invloed op de bestaande realtime control.

## Harde verplichtingen

De planner registreert verplichtingen, maar voert ze niet uit.

- Tesla: wanneer deadline actief is en `remainingKWh > 0`, wordt een `MUST_BY_DEADLINE`-verplichting opgenomen met resterende kWh en deadline.
- Warm water: zolang het dagdoel niet bereikt is en fallbacktijd resteert, wordt `MUST_BY_19:00` of bij actieve catch-up `MUST_CATCHUP` opgenomen.

Daarmee blijft de bestaande prioriteitsregel intact: veiligheid en comfort/deadlines gaan vóór economische optimalisatie.

## Batterijmodel — bewust nog OPEN

De hardwarebaseline heeft de batterijbank nog niet definitief vastgesteld. Daarom verzint de planner geen capaciteit, SOC-grenzen of laad-/ontlaadvermogen. Hij leest uitsluitend de volgende optionele variabelen wanneer die later expliciet worden geconfigureerd:

```text
EM2_Victron_Battery_Capacity_kWh
EM2_Victron_Min_SOC_pct
EM2_Victron_Target_SOC_pct
EM2_Victron_Max_Charge_W
EM2_Victron_Max_Discharge_W
```

Alle vijf moeten geldig zijn voordat `batteryModel.configured=true` kan worden. Tot die tijd is `READY_NO_BATTERY_MODEL` de bedoelde normale status.

## Outputs

`EM2_Energy_Plan_24h` bevat de volledige shadow-planningstate. `EM2_Energy_Planner_Status` bevat een compacte status voor monitoring.

De eerste handmatige uitvoering na creatie is succesvol gestart en beide outputvariabelen zijn daarna in Homey aanwezig.

## Veiligheidsinvarianten

- `controlMode = SHADOW` en `readOnly = true`.
- Geen devicewrites.
- Geen Easee-writes.
- Geen boilerwrites.
- Geen Victron-writes.
- P1-authoritatieve realtime control blijft ongewijzigd.
- Bestaande actuatorwriters blijven ongewijzigd en eigenaar van hun actuator.
- Geen aanvullende volledige `getDevices()`-polling.

## Volgende versie

v0.2 mag pas batterij- en flexallocatie **simuleren** wanneer de batterijparameters expliciet zijn vastgesteld. Ook v0.2 blijft eerst SHADOW. Fysieke Victron-aansturing wordt pas ontworpen na hardware-installatie/commissioning en blijft ondergeschikt aan Victron ESS- en lokale veiligheidsregels.
