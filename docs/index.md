# Homey Energy Manual

Centrale technische documentatie van de Homey-energieautomatisering.

## Status

| Onderdeel | Status | Rol |
|---|---|---|
| Warm water optimalisatie | 🟢 Actief | Stuurt de elektrische boiler en bewaakt CV/boiler-advies |
| Energie Manager PV | 🟡 Shadow mode | Simuleert centrale prioriteit zonder apparaten aan te sturen |
| Tesla PV-laden | 🟢 Bestaande regeling | Blijft actief tijdens shadow-validatie |
| Oude boilerflows | ⚫ Uit | Vervangen door warmwateroptimalisatie |

## Ontwerpprincipe

**huishoudelijk verbruik → Tesla → boiler → teruglevering**
