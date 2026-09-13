# EMS Architecture Governance

**Status:** Verplicht architectuurbeleid  
**Geldig vanaf:** 13 september 2026  
**Canonical architecture baseline:** `docs/architecture/ems-software-architecture-live.md`

## Regel

Het document `ems-software-architecture-live.md` is de canonical architectural baseline voor het EMS.

### 1. Probleemanalyse begint bij de architectuurbaseline

Iedere analyse van een EMS-probleem begint met verificatie van de actuele situatie tegen het canonical architectuurdocument.

De verplichte volgorde is:

```text
Architectuurdocument
  -> live Pi-code/runtime
  -> live Homey-configuratie
  -> runtime-state/logs
  -> diagnose
```

Afwijkingen tussen het architectuurdocument en de live implementatie moeten expliciet worden vastgesteld voordat conclusies over de oorzaak van een probleem worden getrokken.

Oude projectdocumentatie, historische flows, shadowimplementaties of eerdere architectuurbeschrijvingen mogen niet stilzwijgend als actuele waarheid worden gebruikt wanneer zij afwijken van deze baseline of van de live code.

### 2. Wijzigingen aan EMS-logica vereisen documentatie-update

Iedere wijziging die de EMS-architectuur, verantwoordelijkheden, control flow, planning, safety, interfaces of ownership beïnvloedt, moet ook in `ems-software-architecture-live.md` worden verwerkt.

Een logica-wijziging is architectonisch pas afgerond wanneer:

1. de implementatie is aangepast en gevalideerd;
2. de canonical software source in GitHub overeenkomt met de gevalideerde productie-implementatie;
3. `ems-software-architecture-live.md` de nieuwe situatie correct beschrijft.

### 3. Geen dubbele ownership

Bij iedere wijziging moet expliciet worden gecontroleerd dat geen nieuwe dubbele verantwoordelijkheid ontstaat tussen Pi, Homey, website of andere componenten.

De leidende verantwoordelijkheden zijn:

```text
Pi Dynamic Planner = planning / optimization owner
Homey              = realtime state, safety and execution owner
Device adapters    = translation only
Actuators          = physical writes only
Website            = command input and presentation; no EMS optimization
GitHub             = canonical software/documentation source; not runtime-state transport
```

Een afwijking hiervan moet bewust worden ontworpen, gevalideerd en in het canonical architectuurdocument worden vastgelegd.

### 4. Architecture documentation is onderdeel van Definition of Done

Een EMS-wijziging die de architectuur beïnvloedt maar niet in het canonical architectuurdocument is verwerkt, geldt als **niet volledig afgerond**.

Bij afronding van een architectuurrelevante wijziging moet daarom expliciet worden gecontroleerd:

```text
IMPLEMENTATION PASS
RUNTIME VALIDATION PASS
GITHUB SOURCE SYNC PASS
ARCHITECTURE DOCUMENTATION PASS
```

Pas wanneer alle toepasselijke controles PASS zijn, is de wijziging architectonisch DONE.
