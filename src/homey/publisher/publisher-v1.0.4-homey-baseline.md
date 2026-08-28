# Homey Publisher baseline — v1.0.4/current runtime

Captured from Homey before repair on 2026-08-28.

- Flow ID: `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd`
- Homey name: `EM v2 | 40 Data | Publisher`
- Enabled: `false`
- Broken: `false`
- Folder: `55e9b32f-3735-4010-be99-c6d5a0375679`

## Exact card chain

1. Manual start card `11111111-1111-4111-8111-111111111111`
2. Programmatic trigger `22222222-2222-4222-8222-222222222222`
   - target flow ID: `a18bcd77-7b79-40bf-8d31-f1ed3880fca8`
   - target name stored in card: `EM v2 | 40 Data | PBTH Export`
3. Delay `33333333-3333-4333-8333-333333333333`
   - 90 seconds
4. HomeyScript action `44444444-4444-4444-8444-444444444444`
   - script ID: `83a93b0f-4ca5-49c9-8c43-03c24e3d9b1d`
   - script name: `EM v2 - Publish ShadowData`

## Defect

The referenced `PBTH Export` target flow is no longer present in the current Homey flow inventory. Because the next card is connected only to the trigger card's success output, that missing dependency can block the publication chain before `Publish ShadowData` executes.

This file is an immutable repair baseline. Functional repair is versioned separately.
