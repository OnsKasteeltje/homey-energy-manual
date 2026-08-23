# 24h Energy Planner v0.2 SHADOW

## Doel

`EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW` simuleert vóór installatie hoe het toekomstige Victron-systeem, Tesla en warm water economisch over beschikbare prijsvensters zouden kunnen worden gepland. De flow is uitsluitend SHADOW/advies en verricht **geen fysieke actuatorwrites**.

Actieve flow-id: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`.

Voorganger `EM v2 | 45 Planner | 24h Energy Plan v0.1 [ROLLBACK]` is uitgeschakeld.

## SHADOW-hardwaremodel

Het expliciete simulatiescenario is:

- Victron MultiPlus-II 48/5000/70-50;
- Cerbo GX MK2;
- VM-3P75CT;
- 3 × Pylontech US5000;
- 14,4 kWh nominale batterijcapaciteit;
- maximaal 3,3 kW AC laden en 3,3 kW AC ontladen in de simulatie;
- SOC-band 20–90% uitsluitend als SHADOW-aanname;
- 95% laad-efficiëntie en 95% ontlaad-efficiëntie uitsluitend als SHADOW-aanname;
- 90,25% roundtrip-efficiëntie als afgeleide simulatie-aanname;
- bruikbaar simulatievenster: 10,08 kWh.

Deze SOC- en efficiëntiewaarden zijn **geen commissioninginstellingen**. Definitieve Victron/Pylontech-limieten worden pas bij installatie en commissioning vastgesteld.

## Beschikbare brondata

De planner hergebruikt uitsluitend bestaande Logic-state/context:

- `EM2_State` voor Core-state en Tesla-deadlinecontext;
- `EM2_WW_State` voor warmwaterdoel/catch-up;
- `EM2_ContractPrice_Context` en `TEMP_PBTH_JSON_BUFFER` voor contract- en kwartierprijzen;
- `M7_PV_Top4h` en `EM2_Context_UpdatedAt` als samenvattende PV-context.

Er wordt geen nieuwe Homey-devicepoll geïntroduceerd.

Belangrijke beperking: er is nog geen actuele batterij-SOC, geen gedetailleerde 15-minuten huishoudlastforecast en geen gedetailleerde 15-minuten PV-forecast. Daarom publiceert v0.2 **geen voorspelde gerealiseerde besparing** en geen fysiek uitvoerbaar batterijdispatchplan.

## Actuele procesflow

```text
15-min trigger ──► 45 s stagger ──┐
                                  ▼
manual start ─────────────────► planner
                                  │
                                  ▼
Lees EM2_State + WW-state + uniforme prijscontext
+ PBTH kwartierprijzen + Tesla deadline + PV Top4h
                                  │
                                  ▼
                         Contracttype?
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
               DYNAMIC                           FIXED
      max. 96 geldige 15-min slots          statische context
      P25/P75 classificatie                 geen verzonnen slots
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                     Harde verplichtingen
            Tesla deadline + WW vóór 19:00/catch-up
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
       Tesla prijsvensters   WW kwartierallocatie   Batterij
       rangschikken vóór     op 1,9 kW bestaand     charge/discharge
       deadline; geen        boilermodel             candidates
       kWh/slot verzinnen                            op prijs
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  ▼
                 Bouw kwartier-SHADOW-acties
                 HOLD / kandidaat / preferred
                                  │
                                  ▼
       Theoretische arbitragekansen + upper bound
       alleen indien prijsparen economisch positief zijn
                                  │
                                  ▼
Publiceer EM2_Energy_Plan_24h + EM2_Energy_Planner_Status
                                  │
                                  ▼
STOP — geen Victron/Easee/boiler/device writes
```

## Tesla

Bij een actieve Tesla-deadline gebruikt de planner de bestaande deadline en resterende kWh als harde verplichting. De beschikbare kwartierprijzen vóór de deadline worden gerangschikt. v0.2 **neemt bewust geen Tesla-kWh-per-slot of vast laadvermogen aan**, omdat dit niet uit de huidige plannerinput volgt. De realtime/deadline-writer blijft ongewijzigd en is geen onderdeel van deze planner.

## Warm water

Voor warm water wordt het reeds in de actuele Decision-laag gebruikte boilermodel van ongeveer 1,9 kW hergebruikt. Daardoor mag de resterende looptijd voor SHADOW-planning worden omgerekend naar energie en 0,475 kWh per kwartier. Catch-up blijft MUST; anders wordt vóór 19:00 op goedkope vensters gerangschikt. Dit verandert de bestaande warmwaterwriter niet.

## Batterij

De batterijsectie is `THEORETICAL_ARBITRAGE_CANDIDATES_ONLY`.

Per kwartier is de maximale gesimuleerde AC-energie 0,825 kWh bij 3,3 kW. Goedkope slots worden als `CHARGE_CANDIDATE` gemarkeerd en dure slots als `DISCHARGE_CANDIDATE`. Alleen een goedkope slot vóór een dure slot kan een economisch prijs-paar vormen. De economische vergelijking houdt rekening met de aangenomen roundtrip-efficiëntie van 90,25%.

`theoreticalUpperBoundEuro` is nadrukkelijk **geen besparingsforecast**. Realisatie is afhankelijk van werkelijke SOC, huishoudlast, PV, deadlines, hardwarelimieten en Victron/ESS-regels.

## Output en status

De twee writer-outputs blijven:

- `EM2_Energy_Plan_24h`
- `EM2_Energy_Planner_Status`

Normale status bij bruikbare prijscontext: `READY_SHADOW_SCENARIO`.

Bij stale/onvoldoende prijscontext: `DEGRADED_PRICE_CONTEXT`.

Horizonclassificatie voor DYNAMIC:

- `FULL_24H`: ten minste 24 uur aaneengesloten kwartierprijzen;
- `PARTIAL`: ten minste 6 uur maar minder dan 24 uur;
- `DIAGNOSTIC`: minder dan 6 uur.

Ontbrekende toekomstige prijzen worden nooit ingevuld of geschat.

## Veiligheidsinvarianten

De output bevat expliciet:

```text
noDeviceWrites = true
noVictronWrites = true
noEaseeWrites = true
noBoilerWrites = true
existingWritersUnchanged = true
p1ControlPolicyUnchanged = true
simulationOnly = true
commissioningValuesUnchanged = true
```

Victron blijft na installatie eigenaar van de snelle batterij/SOC/netregelkring. Homey blijft hogere-horizon huishoudelijke orchestratie doen. De huidige P1-gebaseerde realtime control wordt door deze flow niet gewijzigd.

## Versiebeheer

- actief: `EM v2 | 45 Planner | 24h Energy Plan v0.2 SHADOW`;
- rollback: `EM v2 | 45 Planner | 24h Energy Plan v0.1 [ROLLBACK]`, disabled;
- maximaal één automatische writer voor `EM2_Energy_Plan_24h` is actief.

> Runtimevalidatie 23 augustus 2026: v0.2 aangemaakt, handmatig gestart en daarna opnieuw opgehaald als `enabled=true` en `broken=false`; v0.1 vervolgens uitgeschakeld als `[ROLLBACK]`.