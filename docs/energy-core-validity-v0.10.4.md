# Energy Core v0.10.4 — gescheiden meetvaliditeit

_Status: actief; semantiek verduidelijkt op 19 september 2026. Oorspronkelijke runtimevalidatie: 20 augustus 2026._

## Doel

Vanaf `EM v2 | 00 Core Tick | v0.10.4 (split grid/derived validity)` worden twee verschillende soorten geldigheid expliciet gescheiden:

- `gridMeasurementValid`: geldigheid van de actuele P1/netmeting. Dit is de autoritatieve gate voor netimport, netexport en het flex-exportbudget.
- `derivedHouseBalanceValid`: geldigheid van de legacy afgeleide load-reconstructie op basis van P1 plus inverterbronnen. Dit bestuurt uitsluitend reconstructievelden zoals residual/Overig en bijbehorende diagnostiek; het definieert niet de KPI `Huis`.

`balanceValid` blijft tijdelijk bestaan als backward-compatible alias van `derivedHouseBalanceValid`.

De canonieke gebruikersgerichte KPI **`Huis` = P1 netto (`grid.power_w`)** zolang de P1-meting geldig is. PV is een afzonderlijke stroom en PV-freshness mag `Huis` niet onderdrukken.

## Harde invariant

```text
P1 vers/geldig
    -> netimport/netexport bruikbaar
    -> flex_export_budget mag uit P1 worden berekend
    -> ook wanneer een PV/inverterbron SOURCE_SKEW heeft

P1 niet geldig
    -> flex_export_budget = 0 W (fail-closed)

Legacy load-reconstructie ongeldig
    -> reconstructievelden zoals house_load/residual/Overig niet als betrouwbaar publiceren
    -> canonieke KPI Huis blijft P1 netto zolang P1 geldig is
    -> P1-gebaseerde flexbesluiten NIET blokkeren
```

De kernformule blijft:

```text
flex_export_budget
 = max(0,
       P1_export
       - grid_safety_reserve
       - quatt_ramp_reserve)
```

maar wordt alleen vrijgegeven wanneer `gridMeasurementValid=true`.

## Publicatiecontract schema 2.10

`balance.control_gate` bevat vanaf schema `2.10`:

```json
{
  "p1_fresh": true,
  "grid_measurement_valid": true,
  "derived_house_balance_valid": false,
  "flex_budget_source": "P1_NET_EXPORT"
}
```

`balance.fail_closed_flex_budget` volgt uitsluitend `!grid_measurement_valid`.

`energy_budget` publiceert beide nieuwe velden eveneens. `balance_valid` blijft daar als compatibility-alias van `derived_house_balance_valid` aanwezig.

Warmwater-Control, Decision en Shadow publiceren beide validiteiten zodat downstream diagnostiek niet langer één generieke `balanceValid` hoeft te interpreteren.

Manager constraints gebruiken voortaan:

- `GRID_MEASUREMENT_INVALID_P1_STALE` wanneer de P1/netmeting niet bruikbaar is;
- `DERIVED_BALANCE_INVALID_<reason>` wanneer alleen de legacy load-reconstructie ongeldig is.

## Validatie 20 augustus 2026

De eerste handmatige tick van v0.10.4 publiceerde:

- `schema_version = 2.10`;
- `publisher_version = EM2_CORE_PUBLISH_V0.10.4`;
- `p1_fresh = true`;
- `grid_measurement_valid = true`;
- `derived_house_balance_valid = false`;
- `balance.reason = SOURCE_SKEW` door vertraagde inverterdata;
- `fail_closed_flex_budget = false`;
- `flex_budget_source = P1_NET_EXPORT`;
- manager constraint `DERIVED_BALANCE_INVALID_SOURCE_SKEW`;
- geen fysieke boiler-, Tesla- of Quatt-write; Control blijft `SHADOW`.

Dit is het gewenste bewijsgeval: een vertraagde PV-bron degradeert uitsluitend de legacy load-reconstructie, maar blokkeert een verse en betrouwbare P1-netmeting, de P1-gebaseerde KPI `Huis` of P1-gebaseerde control niet.

## Rollback

Voor de migratie is de vorige Core-flow als uitgeschakelde rollback-kopie bewaard:

`EM v2 | 00 Core Tick | v0.10.3 [rollback backup]`

De migratiehelper is na succesvolle uitvoering uitgeschakeld.
