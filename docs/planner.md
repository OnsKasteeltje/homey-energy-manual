# Planner — retired op GitHub Pages

De operationele Planner-weergave op GitHub Pages is op **26 september 2026** buiten gebruik gesteld.

De actuele Planner draait uitsluitend in de **private Pi-hosted Frontend V2** en leest daar via de lokale Web Data API, waaronder:

```text
GET /web/planner/pv-forecast
GET /web/planner/ev-requirement
```

GitHub Pages is geen runtime-transport meer voor Planner-data. Deze pagina bevat daarom bewust geen live renderer, raw-GitHub fetch of planner-actielogica.

Voor architectuur en contracten blijft de documentatie in deze repository leidend.
