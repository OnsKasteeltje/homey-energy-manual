# GitHub-integratie — historische grens

Sinds de lokale Pi EV Deadline Ingress V1.1-cutover op 9 oktober 2026 heeft `services/pi/integrations/github/` **geen actieve Tesla-commandfetcher** meer.

De productie-Invoer V2 schrijft rechtstreeks via de private Pi Status API (`services/pi/api/status/tesla_command_ingest.py`) naar `/home/jeroen/ems/data/tesla-deadline-command.json`. De lokale deadline-statebuilder en Homey-executor blijven ongewijzigd.

Het bestaande Cloudflare/GitHub-kanaal voor **EMS-instellingen** is een afzonderlijke legacy-compatibiliteitsroute en wordt niet door deze opruiming verwijderd. GitHub is bron voor software en documentatie, niet voor de live Homey↔Pi-besturing of Tesla-deadlinecommands.
