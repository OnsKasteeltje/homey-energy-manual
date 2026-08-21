# Load fingerprints

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
