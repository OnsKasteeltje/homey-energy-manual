# WW Seasonal Source Advisor v0.4 — Pi

Status: production cutover completed 2026-09-07.

## Ownership

The Raspberry Pi is the single owner of the daily seasonal CV-vs-boiler economic advice. The former Homey `WW Seasonal Source Advisor v0.3 SHADOW idempotent` has been disabled manually after successful Pi validation.

The advisor is read-only and advisory. Source switching remains manual; it never writes to the boiler, CV or other physical devices.

## Schedule and runtime

- systemd service: `ems-ww-seasonal-advisor.service`
- systemd timer: `ems-ww-seasonal-advisor.timer`
- cadence: daily at 20:30 Europe/Amsterdam
- runtime: `/home/jeroen/ems/runtime/planner/warm-water/run_seasonal_source_advisor.py`
- canonical history: `/home/jeroen/ems/data/ems-history.sqlite`
- output: `/home/jeroen/ems/data/ww-seasonal-advisor.json`
- state: `/home/jeroen/ems/data/ww-seasonal-advisor-state.json`

The service loads deployment-specific configuration from `/etc/default/ems-ww-seasonal-advisor`. The Homey LAN address is deliberately not committed to Git.

## Decision policy

- last 14 complete local days; current partial day excluded
- minimum 7 valid counterfactual days
- 5 consecutive evaluations in the same direction before confirmed switch advice
- hysteresis: EUR 0.03 per useful kWh
- freshness limit: 36 hours
- boiler simulation: 1.9 kW within 09:30–19:00
- reference boiler demand: up to 30 recent boiler-use days from a 90-day lookback
- minimum reference boiler-use day: 0.5 kWh

The counterfactual removes observed boiler load from P1 and then schedules the reference boiler demand into the cheapest feasible quarter-hours using realized household/PV conditions.

## Contract periods

Contract economics are date-effective in `seasonal_contracts.json`:

1. current pre-ENGIE contract through 2026-10-09;
2. ENGIE fixed contract with saldering from 2026-10-10 through 2026-12-31;
3. ENGIE post-saldering economics from 2027-01-01 through 2029-10-10.

During saldering, PV opportunity cost is conservatively valued at the applicable import tariff. From 2027, the configured net export value is used.

## Notification path

Confirmed switch advice is delivered as:

Pi advisor → local Homey webhook (`ww_seasonal_advice`) → Homey Flow → mobile push notification.

The webhook path was manually validated on 2026-09-07 with a successful mobile push. Notification delivery is idempotent; duplicate confirmed advice is suppressed.

## Cutover validation

On 2026-09-07 the production systemd service completed successfully with Homey mode `BOILER`. The advisor reported `WARMUP_INSUFFICIENT_HISTORY` with 6/7 valid counterfactual days, reference boiler input 5.733 kWh and 10 reference boiler days. No notification was sent, as intended.

The timer was then enabled successfully. Its first scheduled production run after cutover is 2026-09-08 at 20:30 CEST.

The previous Homey v0.3 Seasonal Source Advisor was subsequently disabled manually. The Homey webhook push Flow remains enabled.
