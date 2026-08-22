# Load fingerprints

## Wasmachine

Status: **sequentiële classifier IMPLEMENTED; REFERENCE_ONLY voor vermogensattributie**.

### Bevestigde referentierun 22 augustus 2026

- Geplande start: rond 04:34 lokale tijd.
- Analysevenster: circa 04:20 tot 06:25 lokale tijd.
- Directe AEG-status stond gedurende de run op actief en was uiterlijk rond 06:25 weer inactief.
- Tesla stond tijdens het relevante venster gepauzeerd (`teslaW = 0`), de boiler was uit en de droger was inactief. Daardoor was dit een relatief schoon nachtvenster voor fingerprint-analyse.

Belangrijk: de directe AEG-status geldt als status-ground-truth, niet als directe vermogensmeting. De fase- en vermogensfasen hieronder zijn uit P1/Energy Core afgeleid en blijven daarom `inferred`.

### Waargenomen P1/fase-signatuur

| Lokale tijd | Waarneming | Interpretatie | Bewijsstatus |
|---|---:|---|---|
| ~04:15 | P1 ~401 W; L2 ~271 W | pre-run / huishoudbaseline | gemeten P1/fase |
| ~04:25 | P1 ~2422 W; L2 ~2291 W; L1 ~89 W; L3 ~42 W | sterke kandidaat voor start-/verwarmingspuls | inferred, MEDIUM |
| ~04:35-05:45 | L2 herhaald circa 280-630 W, met tussenliggende lagere blokken | trommel/motor/pomp/wash-agitation patroon | inferred, MEDIUM-HIGH |
| ~05:55-06:15 | L2 circa 147-216 W | staartfase / spoelen-pompen-einde; 5-min resolutie is te grof voor exacte subfase | inferred, MEDIUM |
| uiterlijk ~06:25 | AEG-status inactief; P1 terug rond normale nachtlast | programma-einde | directe status, HIGH |

De duidelijkste hoge gebeurtenis in deze run zit dus op **L2**. De eerdere fase-analyse bevat bovendien een bruikbare, geïsoleerde wasmachinestart op 16 augustus 2026 met een L2-sprong van circa **+1268 W**. Samen maakt dit L2 aanzienlijk waarschijnlijker dan de huidige `laundry-analysis`-modelwaarde L3.

### Confidence

- Totale fingerprint als referentie: **0,82 — MEDIUM-HIGH**.
- Fase = L2: **0,90 — HIGH**.
- Initiële ~2,29 kW L2-puls als wasmachineverwarming/start: **0,75 — MEDIUM**.
- Recurrente L2-werkband ~0,28-0,63 kW: **0,82 — MEDIUM-HIGH**.
- Staartfase ~0,15-0,22 kW: **0,65 — MEDIUM**.
- Programma-einde op basis van AEG-status: **0,95 — HIGH**.

### Belangrijke modelcorrectie

De actuele `laundry-analysis` publiceert voor de wasmachine nog `phase = L3`, maar met `confidence = LOW`, `evidence_count = 5` en `phase_consistency = 0.6`. Deze nieuwe nacht-run plus de eerdere geïsoleerde L2-start spreken die L3-toewijzing tegen. **L3 mag daarom niet als gevalideerde wasmachinefase worden gebruikt.** De referentie voor verdere classifierontwikkeling is vanaf nu L2, totdat meerdere onafhankelijke runs het tegendeel aantonen.

### Sequentiële classifier v1.1.0

`load-fingerprint-classifier-v1.1.0.js` implementeert nu read-only `WASMACHINE_CANDIDATE` met methode `SEQUENTIAL_L2_FINGERPRINT`. De classifier gebruikt bewust een **volgorde van fasen** en nooit één los hoog datapunt:

1. directe AEG-status levert uitsluitend het programma-/startanker; dit is geen vermogensmeter;
2. in de vroege fase zoekt de classifier op L2 naar een mogelijke verwarmingspuls grofweg 1,8-2,6 kW;
3. daarna moeten meerdere L2-werkblokken in de band 0,25-0,70 kW voorkomen;
4. tussen die werkblokken moeten lagere/rustsamples optreden en meerdere werk/rust-overgangen zichtbaar zijn;
5. cyclusduur en een latere L2-staartband rond 0,10-0,26 kW verhogen de confidence;
6. samples met bekende gelijktijdige grote lasten (Tesla, boiler, droger of Quooker) worden uit de sequentiebewijslijn gefilterd.

De classifier houdt maximaal ongeveer drie uur lokale browserhistorie bij zodat een volledige wascyclus over meerdere 5-minuten Core-publicaties kan worden beoordeeld. De output bevat naast confidence ook de afzonderlijke aantallen voor verwarmingssamples, werkblokken, rustsamples, werk/rust-overgangen en staartsamples.

### Veiligheidsgrens / vrijgave

De sequentiële herkenning is **IMPLEMENTED**, maar blijft `validation_status = REFERENCE_ONLY`. Confidence is voorlopig softwarematig begrensd op maximaal 0,84 en `power_w` / `attribution_w` blijven `null`. Daardoor mag deze eerste sequentiële classifier nog geen vermogen automatisch van `Overig` aftrekken.

Vrijgave voor echte vermogensattributie vereist minimaal één extra schone, onafhankelijke wascyclus die dezelfde L2-sequentie bevestigt. Daarna kunnen drempels/confidence opnieuw worden beoordeeld en kan eventueel een hogere productiestatus worden vrijgegeven.

### Overlap en uitsluitingen

- L1 vertoonde tijdens de cyclus kleine periodieke wisselingen en lijkt achtergrondverbruik; niet opnemen in de wasmachinefingerprint.
- L3 bleef grotendeels op lage achtergrondwaarden en ondersteunt geen L3-toewijzing voor deze run.
- Tesla, boiler en droger waren in het relevante venster geen verklarende grootverbruikers.
- Een losse piek rond 2 kW kan ook bij Quooker, waterkoker, oven of een andere weerstandslast horen; daarom is een meerfasige sequentie verplicht.
- Omdat de 5-minuten Core-cadans korte pomp-, motor- en centrifugepieken kan middelen of missen, worden exacte subfasepieken niet als harde vereiste gebruikt.
- Directe AEG-status blijft altijd hoger in bronhiërarchie dan fingerprint-inference. De fingerprint ondersteunt herkenning/plausibiliteit en mag betrouwbare directe status niet overrulen.

## Waterkoker

Status: **ground-truth uitgebreid; herkenning nog conservatief**.

### Bevestigde gebruiksmomenten

- 2026-08-15 rond 14:34 lokale tijd — waterkoker gebruikt.
- 2026-08-16 rond 11:01 lokale tijd — waterkoker gebruikt.
- 2026-08-21 rond 20:47 lokale tijd — waterkoker expliciet AAN gemeld en kort daarna UIT gemeld.

Deze momenten gelden als handmatig bevestigde ground-truth voor verdere fingerprint-validatie.

### Huidige herkenningskarakteristiek

De huidige kandidaatdetectie gebruikt bewust een conservatieve vorm:

- Quooker mag niet actief zijn;
- er moet een sterke, kortdurende stijging in het niet-toegewezen huishoudelijke restvermogen zijn;
- de voorafgaande residual moet relatief laag zijn;
- één enkele hoge piek is onvoldoende om de waterkoker uniek te identificeren.

De huidige runtime-classifier gebruikt daarom nog een lage confidence voor `WATERKOKER_CANDIDATE` en behandelt de detectie als inferred, niet als directe meting.

### Belangrijkste nieuwe inzicht 21 augustus 2026

De derde bevestigde gebruikscyclus versterkt vooral de **tijdsignatuur**: waterkoker = korte aan/uit-belasting, geen cyclisch patroon zoals de ATAG-oven. De exacte vermogensband en fase-signatuur worden nog niet aangescherpt, omdat de Homey Insights-read voor de relevante P1-reeks op dit moment lege/null meetpunten teruggeeft via de connector. Er wordt daarom geen wattage of fase als gevalideerd vastgelegd zonder meetbewijs.

### Consequentie voor detectielogica

De 5-minuten Energy Core-publicatie kan een korte waterkokeractie volledig missen. Voor betrouwbare automatische herkenning is daarom uiteindelijk een fijnmaziger P1-event/phase-observatie nodig, zonder Homey onnodig zwaarder te belasten. Tot die tijd blijft de bestaande `SHORT_HIGH_LOAD_CANDIDATE` een voorzichtige kandidaatdetectie en worden de bovenstaande handmatig bevestigde momenten gebruikt als referentie voor verdere calibratie.
