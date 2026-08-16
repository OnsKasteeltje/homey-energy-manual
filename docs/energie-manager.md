# Energie Manager PV

## Operationele rollen

De energieregeling is bewust opgesplitst in **observeren/beslissen** en **fysiek aansturen**.

- `Energie Manager PV - Shadow Mode v1.6.6` blijft de actieve read-only Energy Manager voor observatie, boiler-state, Easee/Equalizer-context en shadow-publicatie.
- `Tesla laden v2.0` is de nieuwe fysieke Tesla-controller. Deze flow is ontworpen als **enige automatische schrijver** van de dynamische Easee-laadstroom.
- De Easee Equalizer blijft altijd de harde lokale veiligheids- en load-balancinglaag.

> De omschakeling van de oude Tesla-flow naar v2.0 wordt in Homey gecontroleerd uitgevoerd. Oude automatische Tesla-aansturing en de vaste 17:30-uitschakeling mogen niet tegelijk met v2.0 actief zijn.

## Tesla laden v2.0

### Doel

v2.0 voegt een **deadlinefunctie zonder Tesla-SOC** toe. In plaats van een doelpercentage wordt een minimale hoeveelheid energie gekozen die vóór een datum/tijd aan de auto moet zijn geleverd.

De regeling gebruikt uitsluitend gegevens die Homey/Easee al betrouwbaar beschikbaar stelt:

- P1-netvermogen;
- werkelijk Tesla-laadvermogen;
- Easee lifetime `meter_power` in kWh;
- dynamische laadstroom;
- laad-/aansluitstatus.

Er is dus geen Tesla Fleet API, extern abonnement of veronderstelde SOC nodig.

### Instelvariabelen

De controller gebruikt Homey Logic-variabelen:

| Variabele | Type | Betekenis |
|---|---|---|
| `EV Deadline actief` | Ja/Nee | schakelt deadlinebesturing in of uit |
| `EV Deadline tijd` | tekst | deadline als `YYYY-MM-DD HH:mm` in lokale tijd |
| `EV Doel kWh` | getal | minimaal nog te laden energie voor deze deadline |
| `EV Max laadstroom A` | getal | maximale door Homey gevraagde laadstroom; standaard 11 A |

Afgeleide/statusvariabelen zijn:

- `EV Deadline status`;
- `EV Geladen kWh`;
- `EV Resterend kWh`;
- `EV Latest start`;
- `EV Deadline Runtime State v2.0` (interne persistente status).

### Zonder deadline

Als `EV Deadline actief = nee`, werkt de Tesla als flexibele PV-/exportbuffer. De bestaande opportunistische laadstrategie blijft behouden: tussen **11:00 en 17:30** wordt de beschikbare ruimte berekend als:

```text
PV-ruimte voor Tesla = max(0, -P1 + werkelijk Tesla-vermogen)
```

Daaruit volgt de hoogste passende 3-fase laadstroom vanaf 6 A, begrensd door `EV Max laadstroom A`. Bij onvoldoende overschot wordt de dynamische laadstroom 0 A.

Mogelijke statussen zijn onder meer `OPPORTUNISTISCH` en `WACHT_OP_PV`.

### Met deadline

Als een deadline actief is, houdt de controller bij hoeveel energie sinds het instellen van die deadline werkelijk is geladen. Primair wordt daarvoor de delta van de Easee lifetime-kWh-meter gebruikt. Alleen als die meter niet beschikbaar is, wordt teruggevallen op integratie van werkelijk laadvermogen.

```text
resterend kWh = doel kWh - werkelijk geladen kWh

benodigde tijd = resterend kWh / maximaal laadvermogen

latest start = deadline - benodigde tijd
```

Tot `latest start` blijft de controller opportunistisch laden als er voldoende PV-ruimte is. Vanaf `latest start` wordt **catch-up** actief en vraagt Homey de ingestelde maximale laadstroom, ook wanneer daarvoor netimport nodig is.

Na het bereiken van het kWh-doel vervalt de deadlineprioriteit en mag de Tesla weer opportunistisch laden. Als de deadline al verstreken is terwijl het doel nog niet is gehaald, blijft catch-up actief en wordt dit expliciet als gemiste deadline gemarkeerd.

Belangrijke statussen:

| Status | Betekenis |
|---|---|
| `GEEN_DEADLINE` | geen deadline actief |
| `WACHT_OP_PV` | aangesloten, maar onvoldoende opportuniteit |
| `OPPORTUNISTISCH` | laden uit beschikbaar PV-overschot |
| `DEADLINE_WACHT` | deadline actief; nog voldoende tijd |
| `DEADLINE_OPPORTUNISTISCH` | deadline actief en laden uit PV-overschot |
| `DEADLINE_CATCH_UP` | latest-start bereikt; laden krijgt deadlineprioriteit |
| `DEADLINE_GEMIST_CATCH_UP` | deadline verstreken en doel nog niet gehaald |
| `DOEL_GEHAALD` | minimaal gevraagd aantal kWh bereikt |
| `NIET_AANGESLOTEN` | auto niet beschikbaar voor laden |
| `CONFIG_FOUT` | deadline actief maar tijd/doel ongeldig |

### Wat de deadline wel en niet garandeert

Zonder SOC betekent `EV Doel kWh = 20` letterlijk: **vanaf het moment waarop deze deadlineconfiguratie wordt ingesteld minimaal 20 kWh aan de auto aanbieden/leveren vóór de deadline**. Het betekent niet dat de Tesla bijvoorbeeld 80% SOC zal bereiken.

`EV Latest start` is gebaseerd op het nominale 3-fase vermogen van de ingestelde maximale laadstroom. Als de Easee Equalizer vanwege huisbelasting terugregelt, kan de werkelijke laadsnelheid lager zijn. De Equalizer wordt nooit door Homey overruled.

## Eén eigenaar van automatische Tesla-aansturing

Om conflicten te voorkomen geldt de ownershipregel:

```text
Tesla laden v2.0
      ↓
enige automatische schrijver naar Easee dynamic charger current
      ↓
Easee / Equalizer bepaalt wat veilig werkelijk geleverd wordt
```

De oude flow `Tesla laden` mag daarom niet gelijktijdig actief zijn. Ook de oude dagelijkse flow `Lader uit` (17:30) moet uit staan, omdat een deadline-catch-up juist na 17:30 nodig kan zijn.

De oude handmatige start/stopflows worden vervangen door versies die met v2.0 samenwerken:

- `Handmatig laden starten (8A) v1.1`: schakelt `Tesla laden v2.0` tijdelijk uit en zet de lader handmatig op 8 A;
- `Handmatig laden stoppen v1.1`: zet de laadstroom op 0 A en geeft de automatische regeling daarna weer terug aan `Tesla laden v2.0`.

Daarmee kan handmatig gebruik niet iedere twee minuten door een tweede automatische flow worden overschreven.

## Easee Equalizer als harde veiligheidslaag

De regelhiërarchie blijft:

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer load balancing
          ↓
Victron grid/batterijregeling (later)
          ↓
Homey Energy Manager / Tesla laden v2.0
          ↓
Tesla
```

Homey stuurt dus een **gewenste** laadstroom. De werkelijk geleverde stroom is wat Easee/Equalizer onder de actuele fasebelasting veilig toestaat.

## Shadow Energy Manager v1.6.6

De aparte flow `Energie Manager PV - Shadow Mode v1.6.6` blijft read-only en bestuurt geen Tesla, boiler, wasmachine of droger. Hij observeert onder andere:

- totaal P1-vermogen en P1 L1/L2/L3;
- gevraagd en werkelijk Tesla-vermogen;
- `teslaDeliveryRatio` en afgeleide Equalizer-status;
- boilervermogen, boilerstate en boilercycli;
- wasmachine- en drogerstatus.

De boiler-observer classificeert vermogen boven 1,5 kW als `VERWARMEN`. Na bevestigd verwarmen en vervolgens minder dan 100 W gedurende 10 minuten wordt `OP_TEMPERATUUR` bereikt. Afgeronde cycli worden gepubliceerd naar `docs/data/boiler-cycles.json`.

De shadow-publicatie blijft gescheiden van de fysieke Tesla-controller: meten/beslissen en aansturen zijn daardoor architectonisch traceerbaar.

## Grootverbruikers

Wasmachine en droger leveren in Homey momenteel statusinformatie maar geen afzonderlijk betrouwbaar wattage. Daarom wordt geen individueel vermogen verzonnen. Bekende fasekoppeling:

- Wasmachine: L2;
- Droger: L3.

## Versiebeheer

Voor functionele Homey-wijzigingen wordt een nieuwe subversie aangemaakt en blijft maximaal één versie van dezelfde automatische regelaar actief. Oude versies worden uitgeschakeld en kunnen daarna naar `90 · HISTORISCH / UITGESCHAKELD` worden verplaatst. Tijdelijke omschakelflows horen na succesvolle validatie in `99 · TEMP / OPRUIMKANDIDAAT`.

> Laatste functionele update: 16 augustus 2026 — Tesla SOC-loze kWh-deadline en single-writer-aansturing toegevoegd in `Tesla laden v2.0`.
