# PV-surplus absorption backtest V0.1

Status: **READ_ONLY / validation / learning plane**

## Doel

Deze backtest beantwoordt retrospectief hoeveel werkelijk geëxporteerde PV
technisch extra opgenomen had kunnen worden door reeds bekende flexibele
domeinen, zonder de productieplanner of fysieke aansturing te wijzigen.

De analyse staat bewust buiten de control-loop:

```text
canonical history
    -> read-only replay
    -> absorption evidence
    -> later planner-design decision
```

De tool schrijft geen Homey-, device-, planner- of control-state.

## Canonieke bronnen

Primair gebruikt de tool:

- `house_energy_intervals` voor bruto P1 import/export;
- `measurements_15m` voor Tesla-laadenergie;
- `/home/jeroen/ems/data/planner-history.sqlite -> planner_snapshots` als primaire historische bron voor Tesla connected-state;
- `tesla_connection_events` uitsluitend als expliciete fallback wanneer planner-history voor de replayperiode geen bruikbare dekking bevat.

Alleen bronintervallen van maximaal 15 minuten worden voor de
tijdkritische replay gebruikt. Wanneer `house_energy_intervals` niet
beschikbaar is, mag de tool terugvallen op signed P1
`measurements_15m`; die fallback wordt expliciet gemarkeerd omdat bruto
import en export binnen één kwartier dan kunnen worden onderschat.

## Allocation stack V0.1

De replay gebruikt voor de primaire residual-stack deze volgorde:

```text
Huis-baseload (reeds in P1)
    -> EV session shift
    -> WW zero-import technical
    -> heating preheat: niet tellen zolang UNASSESSED
    -> flex huishoudelijke apparaten: nog niet tellen
    -> batterijscenario
    -> resterende export
```

Dit is een analysevolgorde, geen nieuwe productieprioriteit.

Omdat een vaste volgorde het eerste domein automatisch bevoordeelt, publiceert
V0.1 daarnaast:

- standalone technisch absorptiepotentieel voor EV, WW en batterij;
- een tweede flex-volgorde `WW -> EV`;
- marginale bijdrage per domein binnen beide volgordes;
- ordergevoeligheid;
- overlap tussen het standalone EV- en WW-potentieel, benaderd tegen de beste
  gecombineerde uitkomst van beide volgordes.

Hiermee kan een hoog standalone-potentieel worden onderscheiden van werkelijk
additionele kWh die niet al door een ander flexdomein om dezelfde zonnige slots
worden geclaimd.

### EV

EV-energie wordt niet verzonnen. Per geobserveerde Tesla-aansluitsessie wordt
de werkelijk geladen energie als bovengrens gebruikt.

De connected-state wordt primair per kwartier gereconstrueerd uit
`planner_snapshots.tesla_connected`, maar alleen wanneer een snapshot met zijn
eigen `generated_at_utc -> valid_until_utc` werkelijk het replay-slot overlapt.
Ontbrekende planner-dekking blijft `UNKNOWN` en breekt sessiecontinuïteit;
de replay mag een oude connected-state dus niet onbeperkt naar de toekomst
doortrekken. De legacy `tesla_connection_events`-tabel wordt alleen gebruikt
als planner-history voor de hele replayperiode geen bruikbare dekking heeft.

Laadenergie die al plaatsvond terwijl P1 nog exporteerde, geldt al als
exportvermijding en wordt niet opnieuw als extra potentieel geteld. Alleen
energie die binnen dezelfde aangesloten sessie uit niet-exportmomenten naar
resterende exportmomenten had kunnen worden verschoven, telt als additioneel
absorbeerbaar.

Dit is bewust geclassificeerd als een
`TECHNICAL_SESSION_UPPER_BOUND`. Historische gebruikersdeadlines die eerder
vallen dan het feitelijke loskoppelmoment worden in V0.1 nog niet
gereconstrueerd. Er wordt dus geen extra rij-energie verzonnen, maar de exacte
historische deadline kan het praktisch haalbare verschuifvenster kleiner maken.

Het EV-vermogensplafond is configureerbaar; standaard is 11 kW.

Live read-only replay validation op 2026-09-28 bevestigde dat
`planner-history.sqlite` voor de geanalyseerde periode de juiste bron is voor
historische availability: 755 van 756 kwartieren hadden bruikbare
plannerdekking (99,87%), 376 kwartieren waren connected, één kwartier bleef
bewust UNKNOWN en de replay reconstrueerde 10 afzonderlijke sessies. Dit
vervangt de defecte interpretatie via de oude `tesla_connection_events`-tabel,
die na 2026-09-12 geen nieuwe events meer bevatte en daardoor één fictieve
langdurige sessie opleverde.

### Warm water

WW V0.1 gebruikt het gevalideerde weekday-demandmodel:

| Dag | kWh |
| --- | ---: |
| maandag | 5,8 |
| dinsdag | 4,5 |
| woensdag | 6,3 |
| donderdag | 7,0 |
| vrijdag | 5,9 |
| zaterdag | 7,7 |
| zondag | 7,7 |

De technische replay gebruikt de bestaande 1,9-kW boilerkarakteristiek,
09:30–19:00 en minimaal 30 minuten aaneengesloten looptijd.

V0.1 telt alleen boiler-slots die volledig uit resterende export kunnen worden
gevoed. Er wordt dus geen intentionele netimport toegevoegd om een beter
self-consumption-getal te produceren.

De gemodelleerde dagelijkse warmwatervraag is een harde energiebovengrens.
Kwartierdiscretisatie en de minimale aaneengesloten looptijd mogen nooit meer
boilerenergie toewijzen dan het weekday-demandmodel voor die dag vraagt.

Dit is uitsluitend **technische absorptie**. De economische keuze
`BOILER ↔ CV` blijft eigendom van de bestaande WW Seasonal Source Advisor.
De backtest mag dat economische bronbesluit niet dupliceren.

### Ruimteverwarming

Heating Preheat wordt in V0.1 niet naar kWh vertaald.

De huidige Thermal Learning episodes zijn
`UNASSESSED / RAW_EPISODE_EVIDENCE_ONLY`. Zolang geen gevalideerde
thermische capaciteit, nuttige advancement horizon en rebound-/importeffect
bestaan, zou een kWh-waarde schijnprecisie zijn.

De backtest publiceert daarom expliciet:

`HEATING_PREHEAT_NOT_COUNTED_UNTIL_ASSESSED`.

### Flex huishoudelijke apparaten

Wasmachine, droger en vaatwasser worden in V0.1 nog niet als kWh-flex
meegerekend.

De canonieke Pi-history bevat voor wasmachine/droger wel actieve/inactieve
status, maar nog geen gevalideerd per-programma energieprofiel plus
gebruikersdeadline waarmee een counterfactual programma veilig naar een ander
tijdstip kan worden verschoven. Het bestaande laundry P1-model is bovendien een
attributie-/observabilitymodel en niet automatisch een planner-flexcontract.
Voor de vaatwasser ontbreekt dezelfde canonieke replaybasis.

Deze categorie wordt daarom expliciet als
`NOT_COUNTED_DATA_MODEL_INCOMPLETE` gepubliceerd in plaats van met een
verzonnen verbruiksprofiel te worden geschat.

### Batterij

Na EV en WW worden configureerbare batterijcapaciteiten sequentieel over de
historische tijdlijn gesimuleerd.

Standaard:

- 5 kWh;
- 10 kWh;
- 5 kW laad/ontlaadvermogen;
- 95% laadrendement;
- 95% ontlaadrendement;
- begin-SoC = 0 kWh.

De output onderscheidt:

- PV die anders geëxporteerd was maar in de accu kon worden geladen;
- netimport die later door batterijontlading kon worden vermeden;
- conversieverlies;
- resterende export;
- eind-SoC.

Binnen één kwartier worden bruto import/export eerst netto geïnterpreteerd om
fictief gelijktijdig laden en ontladen door intra-slot volgorde te voorkomen.

## Gebruik op de Pi

Na checkout van de branch:

```bash
cd /home/jeroen/ems/repo/homey-energy-manual

python3 tools/validation/pv_surplus_absorption_backtest.py
```

Standaard wordt afgeleid bewijs geschreven naar:

`/home/jeroen/ems/data/pv-surplus-absorption-backtest.json`

Dit bestand is derived analysis state en geen plannerinput.

Voor alleen stdout:

```bash
python3 tools/validation/pv_surplus_absorption_backtest.py --no-write-output
```

Voor een begrensde periode:

```bash
python3 tools/validation/pv_surplus_absorption_backtest.py \
  --start 2026-09-19T00:00:00+02:00 \
  --end   2026-09-29T00:00:00+02:00
```

## Interpretatieregel

De uitkomst moet bovendien zowel standalone-potentieel als marginale
stackbijdrage tonen. Voor EV en WW wordt dezelfde historie minimaal in beide
volgordes `EV -> WW` en `WW -> EV` afgespeeld. Het verschil is
ordergevoeligheid; het verschil tussen de som van standalone-potentialen en de
beste gecombineerde uitkomst is een maat voor overlap.

De uitkomst moet drie begrippen gescheiden houden:

1. **technisch absorbeerbaar** — fysiek/tijdmatig mogelijk onder de
   replay-aannames;
2. **economisch wenselijk** — contract- en bronafhankelijk, bijvoorbeeld WW
   via de Seasonal Source Advisor;
3. **productierijp plannerbeleid** — pas na validatie van replay, overlap,
   comfort, deadlines en eventuele learned parameters.

Een hoge technische absorptie is dus niet automatisch een opdracht om die
load in productie hoger te prioriteren.
