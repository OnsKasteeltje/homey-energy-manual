# Planner Shadow — historische architectuurnotitie

De voormalige GitHub Pages Planner Shadow UI is op **26 september 2026** retired. De operationele Planner is verhuisd naar de private Pi-hosted Frontend V2 en gebruikt geen GitHub-runtime JSON meer.

## Timeline-invariant

De volgende ontwerpregel blijft geldig voor de huidige en toekomstige Planner-UI:

- alle tijdgebaseerde visualisaties gebruiken dezelfde **96 × 15 minuten** horizontale slotgeometrie;
- slot *i* beslaat in iedere timeline exact hetzelfde horizontale interval;
- forecast, prijs, EV-, warm-water-, batterij- en toekomstige actierijen delen dezelfde plotorigin en schaal;
- labels, assen, margins en wrappers staan buiten die gedeelde plotgeometrie;
- er is één eigenaar voor axis-wrapping/decoratie;
- een asset heeft één primaire actierij; decorators mogen geen tweede concurrerende timeline maken.

Wijzigingen aan assen, wrappers, labels, responsive layout of actierijen blijven daarom een expliciet timeline-sync regressierisico.

Deze pagina bevat bewust geen CSS-links, plannerdata-fetch of runtime-renderer meer.
