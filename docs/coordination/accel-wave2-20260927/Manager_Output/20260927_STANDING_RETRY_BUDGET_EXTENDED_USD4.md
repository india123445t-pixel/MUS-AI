# AQLEVON 27B — Standing Retry Budget Extended to USD 4.00

Timestamp: 2026-09-27
Owner directive: **raise cumulative ceiling to USD 4.00 and continue until success**

## Binding interpretation

- cumulative actual paid GPU spend ceiling: **USD 4.00 total**
- this includes prior paid attempt 05
- each child authorization remains unique and single-use
- per-run hard ceiling remains **USD 1.50**
- max hourly rate remains **USD 1.60/hour**
- no failed/consumed child authorization may be reused
- Manager may issue subsequent fresh child authorizations without asking again while:
  - cumulative actual spend < USD 4.00;
  - scientific recipe remains unchanged;
  - no new safety/scientific blocker requires owner judgment.

## Ledger at extension time

- Authorization 03: USD 0.00 GPU
- Authorization 04: USD 0.00 GPU
- Authorization 05: USD 1.326767 estimated GPU
- cumulative spent: **USD 1.326767**
- remaining ceiling: **USD 2.673233**

## Retry preference

First next attempt:
- bind stopped Pod `v3njg70l4mtazn` explicitly;
- reuse its already-pulled image/machine if RunPod accepts restart;
- controller prechecks exact image/name/EXITED/rate;
- new child authorization required;
- current controller cutoff: 3200 seconds;
- artifact durability gates remain mandatory.

If stopped-Pod restart fails before paid GPU execution, fix/retry free-only or issue another fresh child authorization automatically.

**STATE: STANDING_RETRY_AUTH_ACTIVE_CUMULATIVE_CAP_USD_4**
