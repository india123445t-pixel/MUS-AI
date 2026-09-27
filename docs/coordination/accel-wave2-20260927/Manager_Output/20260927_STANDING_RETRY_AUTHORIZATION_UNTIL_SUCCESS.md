# AQLEVON 27B — Standing Retry Authorization Until Success

Timestamp: 2026-09-27
Owner directive: explicit in chat after repeated pre-create failures.

## Authorization semantics

The owner authorizes the AQLEVON Manager to continue issuing **new, unique, single-use paid authorizations** for AQLEVON-27B retry attempts without asking again after every failed attempt.

Hard limits:

- cumulative actual paid GPU spend across retries from this standing directive: **USD 1.50 maximum total**
- each child authorization remains single-use and fresh
- a failed or consumed child authorization is NEVER reused
- retries stop automatically when:
  1. the target run succeeds; or
  2. cumulative paid spend reaches USD 1.50; or
  3. a new safety/scientific blocker appears that cannot be resolved free-only
- no merge to main
- sealed/private historical W05 remains forbidden
- artifact preservation remains mandatory
- automatic cleanup remains mandatory

## Current spend ledger

- Authorization 03: failed before provider create — GPU spend USD 0.00
- Authorization 04: failed before provider create — GPU spend USD 0.00
- cumulative paid GPU spend so far: **USD 0.00**
- remaining standing budget: **USD 1.50**

## Operational rule

This standing directive is NOT itself an operational authorization file.

For every retry the Manager must still create a distinct:
`AQLEVON_MANAGER_PAID_AUTHORIZATION_V2`

with a new authorization_id and then invalidate/consume it according to the control-plane law.

**STATE: STANDING_RETRY_AUTH_ACTIVE**
