# Publisher Probe v0.1 result

## Runtime observation

The one-shot Logic snapshot probe created:

`TEMP_PUBDIAG_F510_M22_A2992_L22_P2582`

Interpretation:

- `F510`: the standalone HomeyScript action `EM v2 - Publish ShadowData` returned an **action-card error** to Advanced Flow.
- `M22`: the mirrored internal `EM2_Publisher_Diag_Code` was `22`.
- `A2992`: v1.0.6 preflight reached source revision `2992`.
- `L22`: the legacy publisher diagnostic remained `22`.
- `P2582`: `EM2_Last_Published_Revision` remained `2582`.

## Conclusion

The v1.0.6 preflight passed far enough to invoke the existing standalone publisher, but that HomeyScript action itself failed. The public GitHub revision therefore remained stale. The former PBTH Export dependency is not the active failure point for this run.

The exact semantic meaning of legacy diagnostic code `22` is **not documented in the repository and the current Homey connector does not expose the standalone HomeyScript source**. Do not infer a meaning for code 22 without recovering that script source or replacing it with a GitHub-controlled publisher implementation.

## Safety

The probe performs one Logic-variable enumeration and creates one temporary numeric Logic variable. It performs no physical device reads or actuator writes.
