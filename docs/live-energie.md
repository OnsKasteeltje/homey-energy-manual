# Live energiestroom

!!! info "Legacy Live-weergave retired"
    De voormalige GitHub Pages/MkDocs Live-weergave is buiten productie gesteld en leest geen GitHub energy-state snapshot meer.

De actuele **Live**-weergave draait uitsluitend op de private Pi-hosted Frontend V2. De operationele keten is:

```text
/home/jeroen/ems/data/energy-state-v2.json
        ↓
Web Data API  GET /web/state/current
        ↓
Caddy / private EMS frontend
        ↓
Frontend V2 · Live
```

GitHub is geen runtime-transport voor actuele energiestatus en er is geen publieke fallback naar `docs/data/energy-state-v2.json`.

Deze legacy documentatiepagina blijft tijdelijk bestaan voor navigatiecompatibiliteit tijdens de verdere GitHub Pages-opruiming. Zij bevat bewust geen live renderer of actuele energiedata.
