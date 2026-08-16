# Energie Manager PV

## Operationele rollen

De energieregeling is bewust opgesplitst in **meten**, **observeren/beslissen**, **publiceren** en **fysiek aansturen**.

De actuele kern bestaat uit:

| Rol | Actieve flow | Ritme | Schrijft apparaten? |
|---|---|---:|---|
| Centrale meetlaag | `Energy Manager State Collector v1.0` | 2 min | nee |
| Shadow Energy Manager | `Energie Manager PV - Shadow Mode v1.6.7` | 5 min | nee |
| Centrale allocator-shadow | `Energy Manager Allocator - Shadow v0.2.4` | 5 min | nee |
| Tesla-controller | `Tesla laden v2.6` | 2 min | ja, Easee laadstroom |
| Live websitepublisher | `Live energie publicatie v1.2` | 5 min | nee |
| Algemene statuspublisher | `GitHub status sync - Homey lokaal v1.4` | 30 min | nee |
| Prijs/PV-context | `M7 - Prijs en PV forecast context - read only` | 15 min | nee |

De Easee Equalizer blijft altijd de harde lokale veiligheids- en load-balancinglaag.

## Centrale state collector v1.0

`Energy Manager State Collector v1.0` is de centrale read-laag. Iedere twee minuten wordt in één HomeyScript-run één consistente runtime-snapshot opgebouwd uit de relevante apparaten en Logic-variabelen.

De collector leest onder andere:

- P1 totaal en L1/L2/L3;
- Tesla/Easee vermogen, laadstatus, doelstroom en kWh-meter;
- Equalizer fasebelasting;
- boilervermogen en aan/uit;
- drie PV-omvormers;
- wasmachine- en drogerstatus;
- relevante deadline-, warmwater- en M7-context.

De snapshot wordt gedeeld als:

```text
EM_Runtime_State
```

Doel is dat meerdere consumers niet ieder afzonderlijk opnieuw alle Homey-devices hoeven op te vragen.

```text
Homey devices + Logic
        ↓
Energy Manager State Collector v1.0
        ↓
EM_Runtime_State
        ├─→ Allocator Shadow v0.2.4
        └─→ Live energie publicatie v1.2
```

De Tesla-controller blijft bewust rechtstreeks meten, omdat veilige laadbesturing niet afhankelijk mag worden van een mogelijk enkele minuten oude centrale snapshot.

## Tesla laden v2.6

`Tesla laden v2.6` is de **enige automatische Easee-writer**. De flow evalueert iedere twee minuten en combineert:

- actuele P1-balans;
- werkelijk Tesla-laadvermogen;
- Easee lifetime kWh-meter;
- deadline en resterende laadenergie;
- M7 prijs-/PV-context;
- Equalizer-fasebelasting;
- werkelijk gevraagde versus werkelijk geleverde laadstroom.

### Zonder deadline

Wanneer geen deadline actief is, fungeert de Tesla als flexibele PV-/exportbuffer. Tussen 11:00 en 17:30 wordt de beschikbare laadruimte bepaald uit de actuele netbalans en het reeds geleverde Tesla-vermogen.

Een laadstart vereist minimaal ongeveer:

```text
3 × 6 A ≈ 4,14 kW
```

Bij onvoldoende overschot wacht de regeling.

### Met deadline

Bij een deadline wordt de werkelijk geladen energie bepaald vanaf een vaste Easee-meterbaseline die bij de nieuwe opdracht wordt opgeslagen. De regelaar bewaakt:

```text
resterend kWh
benodigde laadtijd
latest start
deadline
```

Vanaf `EV Latest start` krijgt de deadline prioriteit boven opportunistische optimalisatie.

### Equalizer-classificatie vanaf v2.6

v2.6 voorkomt dat 0 W automatisch als een Equalizer-ingreep wordt geïnterpreteerd. Een actief laadverzoek met vrijwel 0 W wordt eerst geclassificeerd als **laden geblokkeerd**. Alleen wanneer tegelijkertijd voldoende hoge Equalizer-fasebelasting wordt gezien, wordt de blokkade specifiek aan de Equalizer toegeschreven.

Daarmee onderscheiden we onder andere:

- normaal laden;
- beperkt laden;
- korte nulvermogenspauze in bevestiging;
- blokkade met Equalizer-evidence;
- blokkade met onbekende oorzaak.

De Equalizer wordt nooit door Homey overruled.

## Shadow Energy Manager v1.6.7

`Energie Manager PV - Shadow Mode v1.6.7` is read-only en bestuurt geen Tesla, boiler, wasmachine of droger.

Hij observeert onder andere:

- totaal P1-vermogen en P1 L1/L2/L3;
- gevraagd en werkelijk Tesla-vermogen;
- afgeleide Equalizer-status;
- boilervermogen, boilerstate en boilercycli;
- wasmachine- en drogerstatus.

De vorige versie v1.6.6 draaide iedere twee minuten én had daarnaast een aparte 15-minutentrigger naar hetzelfde zware script. Vanaf v1.6.7 is dit vereenvoudigd naar **één 5-minutentrigger**. De GitHub-publicatie wordt nog steeds intern ongeveer iedere 15 minuten bepaald.

Dit verlaagt de Homey-belasting zonder de shadowfunctie op te heffen.

De boiler-observer gebruikt de semantische keten:

```text
VERWARMEN → AFKOELEN_WACHT → OP_TEMPERATUUR
```

Afgeronde cycli blijven naar `docs/data/boiler-cycles.json` worden gepubliceerd.

## Allocator Shadow v0.2.4

`Energy Manager Allocator - Shadow v0.2.4` is de centrale beslis-/validatielaag in shadow mode.

Vanaf v0.2.4 leest deze flow **geen volledige devicelijst meer**. Hij gebruikt `EM_Runtime_State` en vult die aan met de noodzakelijke Flow Tags en warmwaterstatus. De flow:

- bepaalt MUST / SHOULD / MAY-prioriteit;
- vergelijkt de allocatorrichting met observeerbaar bestaand gedrag;
- publiceert state, decision, validation, stats en beperkte historie;
- voert geen device-writes uit.

De runtime-snapshot moet jonger zijn dan vijf minuten; anders faalt de allocator bewust fail-safe.

## Live energie publicatie v1.2

De live websitepublisher draait iedere vijf minuten. Vanaf v1.2 leest hij `EM_Runtime_State` in plaats van zelf opnieuw alle apparaten op te vragen.

De GitHub-write blijft één snapshot per vijf minuten, maar de Homey-readbelasting wordt daardoor lager.

## GitHub status sync v1.4

De algemene flowstatus verandert veel minder vaak dan live energie. Daarom is de cadence vanaf v1.4 verlaagd van 15 naar **30 minuten**.

De sync blijft publiceren naar onder andere:

- `docs/data/homey-status.json`;
- `docs/data/shadow-status.json`.

Dit heeft geen invloed op de regelcycli zelf.

## M7 prijs- en PV-context

M7 blijft read-only en vernieuwt iedere 15 minuten de gedeelde context:

- `M7_Price_Negative`;
- `M7_Price_Cheap_Next4h`;
- `M7_Price_Expensive_Next4h`;
- `M7_PV_Top4h`.

Tesla v2.6 gebruikt deze signalen alleen zolang de deadlineveiligheid dit toestaat.

## Veiligheids- en regelhiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer load balancing
          ↓
Victron grid/batterijregeling (later)
          ↓
Homey Energy Manager
          ↓
Tesla / boiler
```

Homey stuurt een gewenste laadstroom. De werkelijk geleverde stroom is wat Easee/Equalizer onder de actuele fasebelasting veilig toestaat.

## Grootverbruikers

Wasmachine en droger leveren in Homey momenteel statusinformatie maar geen afzonderlijk betrouwbaar wattage. Daarom wordt geen individueel vermogen verzonnen.

Bekende fasekoppeling:

- Wasmachine: L2;
- Droger: L3.

## Homey-load ontwerpprincipe

De optimalisatie van 16 augustus 2026 introduceert expliciet het principe:

> **één keer meten, meerdere keren gebruiken.**

Waar praktisch veilig worden device- en Logic-reads gecentraliseerd. Frequente fysieke besturing blijft rechtstreeks meten wanneer actuele data veiligheidskritisch is.

Analyse, historie en websitepublicatie worden zoveel mogelijk buiten de kritische besturingsroute gehouden.

## Versiebeheer

Voor functionele Homey-wijzigingen wordt een nieuwe subversie aangemaakt en blijft maximaal één versie van dezelfde automatische regelaar actief. Oude versies worden uitgeschakeld en blijven beschikbaar als rollback-/referentiepunt.

Actuele opvolging na de load-optimalisatie:

```text
Shadow v1.6.6          → UIT
Shadow v1.6.7          → ACTIEF

Allocator v0.2.3       → UIT
Allocator v0.2.4       → ACTIEF

Live energie v1.1      → UIT
Live energie v1.2      → ACTIEF

GitHub status sync v1.3 → UIT
GitHub status sync v1.4 → ACTIEF
```

> Laatste functionele update: **16 augustus 2026** — Homey-load geoptimaliseerd met centrale state collector, 5-minuten shadowcadence, centrale-state consumers en 30-minuten status-sync. Tesla v2.6 blijft de enige automatische Easee-writer.
