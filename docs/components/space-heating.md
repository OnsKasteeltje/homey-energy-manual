# Ruimteverwarming

Status: **DESIGN / READ-ONLY / SHADOW**  
Functionele domeinnaam: **Ruimteverwarming**  
Optimalisatiefunctie: **PV-voorverwarming** (`heating-preheat`)

## Doel

Ruimteverwarming is het overkoepelende EMS-domein voor de Honeywell comfortbaseline, PV-voorverwarming en toekomstige thermische leerfuncties. Honeywell/Resideo blijft de baseline- en comfortauthority. Het EMS creëert geen nieuwe warmtevraag en wijzigt de normale Honeywell-planning niet wanneer geen bruikbare PV-opportunity bestaat.

De begrippenhiërarchie is:

```text
Ruimteverwarming
  ├─ Honeywell Baseline
  ├─ PV-voorverwarming / heating-preheat
  └─ Heating Thermal Learning
```

## Scope PV-voorverwarming V0.x

De expliciete initiële scope voor PV-voorverwarming bestaat uit vier zones:

- `woonkamer` — Woonkamer;
- `eetkamer` — Eetkamer;
- `keuken` — Keuken;
- `serre` — Serre.

`douwe_slaapkamer`, `erker_douwe`, `master_bedroom` en `krijn_slaapkamer` blijven normale Honeywell baseline-/comfortzones, maar zijn voorlopig uitgesloten van PV-gebaseerde vervroeging.

Woonkamer en Eetkamer worden afzonderlijk gemeten en aangestuurd, maar mogen door de planner als gekoppelde opportunity worden geëvalueerd omdat de ruimten functioneel/open met elkaar verbonden zijn. Keuken en Serre blijven aanvankelijk afzonderlijke kandidaten. Deze groepering is expliciete configuratie en mag niet uit kamernamen worden afgeleid.

## Kerninvariant

**Alle ruimteverwarming is baseline-/comfortvraag. Alleen het tijdstip van reeds geplande toekomstige Honeywell-warmtevraag mag naar voren worden geschoven wanneer daardoor anders geëxporteerde PV kan worden benut.**

Daaruit volgen de volgende regels:

1. Honeywell blijft baseline- en comfortauthority.
2. Alleen een toekomstige Honeywell `UP` kan voor vervroeging worden overwogen; `DOWN` en `NONE` nooit.
3. Het EMS mag nooit boven het latere Honeywell-comforttarget verwarmen.
4. Zonder bruikbare voorspelde PV-export blijft het Honeywell-schema ongewijzigd.
5. PV-voorverwarming mag niet doelbewust netimport veroorzaken.
6. Alleen de door vervroeging veroorzaakte incrementele warmtevraag concurreert met andere flexibele vraag zoals WW en EV.
7. WW, heating-preheat en EV gebruiken dezelfde resterende PV-export opportunity in de Dynamic Pi Planner; er is geen afzonderlijke heating-PV-pot en geen starre opportuniteitsprioriteit.

## Actuele temperatuur is beslissend

Een toekomstige Honeywell-UP is op zichzelf geen heating opportunity. De actuele gemeten ruimtetemperatuur moet aantonen dat er richting het toekomstige Honeywell-target nog warmtevraag bestaat.

Conceptueel:

```text
future Honeywell UP
  + binnen toegestane vervroegingshorizon
  + actual room temperature < relevant future Honeywell target
  + forecast remaining PV-export potential > 0
  -> mogelijke PV-preheat candidate
```

Wanneer de actuele ruimtetemperatuur al op of boven het relevante toekomstige target ligt, is de ruimte geen preheat-kandidaat, ongeacht de hoeveelheid PV-export.

## Voorlopige vervroegingshorizon

Voor V0.x geldt **circa 3 uur als voorlopige maximale zoekhorizon** voor vervroeging. Dit is een guidance/safety bound, geen bewezen thermische constante en geen doel om standaard drie uur eerder te verwarmen.

Onderbouwing: geaggregeerde Homey Insights over najaar 2025 tot voorjaar 2026 laten zien dat de woonkamer in koude perioden relatief snel warmte kan verliezen. De beschikbare jaarhistorie is echter naar zes-uursblokken geaggregeerd en is daarom onvoldoende om een betrouwbare responstijd per 0,5 °C-stap af te leiden. De 3-uursgrens blijft daarom voorlopig en moet met nieuwe fijnmazige stookdata worden gevalideerd.

## Temperatuurstappen

De bestaande kleine Honeywell-UP-stappen zijn geschikte bouwstenen voor geleidelijke voorverwarming, mede om de Quatt de gelegenheid te geven de warmtevraag zonder onnodige CV-inschakeling te verwerken.

- Bestaande Honeywell-UP-stappen van maximaal `+0.5 °C` blijven de natuurlijke bouwstenen.
- Een grotere Honeywell-UP mag **alleen wanneer het EMS die vraag daadwerkelijk vervroegt voor PV-preheat** worden gedecomposeerd in stappen van maximaal `+0.5 °C`.
- Het EMS herschrijft of splitst de normale Honeywell-baseline niet op dagen zonder PV-opportunity.
- De actuele gemeten temperatuur wordt bij iedere toekomstige beslissing opnieuw betrokken; een geplande stap impliceert niet automatisch resterende warmtevraag.
- De optimale tijd tussen stappen wordt niet vooraf verzonnen maar later uit meetdata geleerd.

## Geen onbewezen thermisch vermogensmodel

V0.x introduceert nog geen aangenomen thermisch vermogen, COP, opwarmsnelheid, gebouwverliescoëfficiënt of vaste room-response curve. Er wordt evenmin een fictieve `heatingPlanW` gecreëerd voordat de relatie tussen ruimtevraag, Quatt-bedrijf en elektrisch vermogen voldoende is gevalideerd.

Dit voorkomt dat de Dynamic Pi Planner schijnprecisie gebruikt bij de gezamenlijke allocatie van PV-surplus.

## Rebound-validatie

PV-voorverwarming is pas werkelijk thermische buffering wanneer vroegere warmte-inbreng latere warmtevraag rond het oorspronkelijke Honeywell-comfortmoment aantoonbaar vermindert.

Validatie moet daarom niet alleen meten hoeveel PV-export tijdens preheat werd geabsorbeerd, maar ook:

- ruimtetemperatuur na de preheat;
- gedrag rond het oorspronkelijke Honeywell-UP-moment;
- latere Quatt-/verwarmingsvraag;
- of latere verwarming daadwerkelijk is vermeden of verminderd.

Vroeger én later extra verwarmen mag niet als succesvolle PV-buffering worden geteld.

## Shadow-first en Thermal Learning

De eerste fase blijft volledig **READ_ONLY / SHADOW**. Er worden geen Honeywell-setpoints geschreven en geen fysieke verwarmingscommando's uitgevoerd.

Zodra de actieve stookperiode begint, wordt fijnmazige data verzameld voordat Homey Insights deze verder aggregeert. Voor thermisch leren zijn ten minste relevant:

- Honeywell baseline target en daadwerkelijke target/setpoint;
- gemeten ruimtetemperatuur;
- tijdstip en grootte van target-UP's;
- Quatt activiteit en, waar beschikbaar, elektrisch vermogen;
- P1-/energiecontext;
- buitentemperatuur als verklarende variabele.

De eerste empirische vraag is hoe lang een ruimte onder relevante omstandigheden reageert op een `+0.5 °C` target-UP. Woonkamer en Eetkamer zijn geschikte eerste leerzones; parameters worden daarna tegen Keuken en Serre getoetst.

Historische geaggregeerde Homey Insights blijven bruikbaar voor grove seizoens- en afkoelpatronen, maar niet voor het betrouwbaar kalibreren van de timing tussen individuele `0.5 °C`-stappen.

## Visualisatie

De plannerwebsite is onderdeel van de validatie. Voor de vier zones in scope moet de visualisatie uiteindelijk op dezelfde tijdas onderscheid maken tussen:

- oorspronkelijke Honeywell baseline;
- EMS SHADOW-vervroeging;
- actuele gemeten ruimtetemperatuur;
- relevante PV-export opportunity;
- gezamenlijke WW/heating-preheat/EV allocatie en resterende grid-export.

De oorspronkelijke Honeywell-curve blijft altijd zichtbaar en wordt nooit visueel vervangen door de EMS-kandidaat. De visualisatie moet de beslisketen uitlegbaar maken:

```text
baseline
  -> actuele temperatuur
  -> toekomstige UP
  -> mogelijke advancement window
  -> resterende PV-export opportunity
  -> geselecteerde shadow advancement + reden
  -> achteraf rebound/resultaat
```

## Architectuurgrenzen

De bestaande technische lagen blijven leidend:

```text
services/pi/integrations/honeywell/
  -> services/pi/state/heating/
  -> services/pi/planner/heating/
  -> future: services/pi/control/heating/
```

Bestaande schema's bij start van dit document:

- `EMS_HONEYWELL_SCHEDULE_V0.2`;
- `EMS_HONEYWELL_STATE_V0.2`;
- `EMS_HEATING_ROOM_MODEL_V0.1`;
- `EMS_HEATING_PREHEAT_PLAN_V0.1`.

De volgende plannerincrement mag deze ontwerpregels modelleren, maar blijft SHADOW. Een toekomstige LIVE-fase vereist afzonderlijk gevalideerde adapter/gate/actuator-grenzen en expliciete commissioning.

## Vervolg

1. Heating Preheat V0.2 shadow-beslisoutput modelleren voor de vier zones.
2. Maximaal circa drie uur advancement als voorlopige bound opnemen.
3. Actuele ruimtetemperatuur als harde eligibility-input opnemen.
4. Grote vervroegde UP's alleen binnen de preheat-kandidaat opdelen in stappen van maximaal 0,5 °C.
5. Woonkamer + Eetkamer als expliciete opportunitygroep ondersteunen zonder hun afzonderlijke meet-/targetstatus te verliezen.
6. Planner-/websitevisualisatie uitbreiden voor baseline versus shadow advancement.
7. Vanaf hervatting van de stookperiode fijnmazige thermal-learning data archiveren.
8. Met die data 3-uursgrens, stapafstand en rebound empirisch valideren voordat fysieke Honeywell-control wordt overwogen.
