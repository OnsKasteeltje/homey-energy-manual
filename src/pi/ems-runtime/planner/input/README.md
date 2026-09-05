# EMS Pi Planner Input Model

## Purpose

This layer defines the inputs for the 96 x 15-minute EMS planner.

The planner distinguishes strictly between:
- forecast-only, non-controllable loads
- controllable, goal-driven loads
- generation forecast
- contract/economic constraints

## Forecast-only loads

### Baseline house load

baseLoadForecastW

Expected household load excluding separately modelled loads:
- Tesla
- warm-water boiler
- Quatt

### Quatt

quattForecastW

Expected electrical consumption of the Quatt heating system per 15-minute slot.

Quatt is FORECAST ONLY.

The EMS:
- does not control Quatt
- does not change Quatt setpoints
- does not schedule Quatt
- does not create a Quatt actuator
- does not treat indoor temperature as an EMS goal

Weather and historical Quatt behaviour may be used solely to estimate future
Quatt electrical consumption.

## Controllable loads

### Tesla

teslaPlanW

Goal-driven load using remaining energy, deadline, charging constraints,
PV availability and expected non-controllable load.

### Warm water

wwPlanW

Goal-driven load using remaining hot-water requirement, deadline,
boiler power, PV availability and expected non-controllable load.

## Generation

### PV

pvForecastW

Expected total PV generation per 15-minute slot.

## Weather

Weather is forecasting input only.

Current fields:
- temperature_2m_c
- apparent_temperature_c
- cloud_cover_pct
- wind_speed_10m_kmh
- wind_direction_10m_deg
- shortwave_radiation_w_m2

Uses:
- shortwave radiation -> PV forecast
- temperature/wind/solar conditions -> Quatt load forecast

## Planner slot model

Each future 15-minute slot will ultimately contain:
- start
- baseLoadForecastW
- quattForecastW
- pvForecastW
- teslaPlanW
- wwPlanW
- totalLoadForecastW
- gridImportForecastW
- gridExportForecastW

Quatt forecast may influence when controllable loads are planned,
but the EMS must never alter Quatt operation itself.

## Safety boundary

This planner-input layer is SHADOW/READ-ONLY.

It must not perform physical device writes.
