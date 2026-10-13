# Tesla-deadline — actuele commandroute

**LIVE sinds 9 oktober 2026: lokale Pi-ingress V1.1.**

```text
Invoer V2 (private Tailscale-site)
  → POST /web/commands/tesla + control-PIN
  → Caddy → Pi Status API /commands/tesla
  → /home/jeroen/ems/data/tesla-deadline-command.json
  → lokale deadline-statebuilder /control/current
  → Homey PI Dynamic Planner Bridge v1.5.9
  → EV Adapter v0.2.0 → EV Gate v0.3.0
  → EV Power writer v0.4.6 [LIVE] → Easee
```

De Pi valideert de gebruikersintentie en schrijft de command atomair. `GET /web/commands/current` leest hetzelfde lokale commandbestand. De fysieke Easee-aansturing blijft uitsluitend onder de bestaande Homey-writer/safety-laag.

De oude Cloudflare → GitHub → Pi-fetchroute is **uitgefaseerd**. `docs/data/tesla-deadline-command.json` is niet meer de productiecommandbron. De Cloudflare Worker kan nog worden gebruikt voor een afzonderlijke EMS-instellingenroute; die is buiten deze Tesla-cutover gebleven. Een tweede deadline-ingress of automatische GitHub-fetcher is verboden.

Voor historische transportvertraging, details van de beveiliging, de productiecutover en realtime validatie, zie [Tesla deadline — end-to-end keten](architecture/tesla-deadline-end-to-end.md), vooral sectie 12.
