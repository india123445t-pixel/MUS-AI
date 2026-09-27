# AQLEVON 27B — Fresh Authorization 04 Pre-Create Failure / Root Cause Fixed

Timestamp: 2026-09-27
Manager state: **READY_FOR_NEW_FRESH_AUTH**

## Authorization 04

Authorization:
`P4-AQLEVON-27B-R0-FRESH-20260927-1420-04`

Paid workflow:
- run: `36325557889`
- execute job: `108637561658`

Observed:
- Fresh Authorization V2: PASS
- Scientific contract pre-create: PASS
- No active AQLEVON 27B pod: PASS
- failure before reservation/consumption
- failure before provider create
- no evidence archive existed, so upload/finalizer failed closed
- reservation file: ABSENT
- consumption file: ABSENT
- provider pod created: NO
- GPU compute cost: **USD 0.00**

Authorization 04 was invalidated and MUST NOT be reused.

## Root cause

The previous installer patch accidentally wrote a literal backslash-n sequence inside the paid shell script:

`.../runpodctl\nsudo chmod ...`

rather than two shell lines.

This corrupted the wget command and caused pre-create failure.

## Repair

Paid script repaired at the operational branch:
- literal newline corruption removed
- robust curl installer added
- retries enabled
- downloaded binary size verified
- `sudo install -m 0755` used
- `runpodctl version` required

Free preflight was also changed to mirror the same robust installer and explicitly:
- runs `bash -n` against the paid script
- rejects any literal `\n` sequence
- verifies no active AQLEVON 27B pod
- installs runpodctl
- checks secure A100-SXM4-80GB capacity <= USD 1.60/hour

## Free verification after repair

Workflow:
`AQLEVON 27B Free Capacity Preflight`

Run:
`36325720184`

Job:
`108637992262`

Conclusion:
**SUCCESS**

Evidence:
- `AQLEVON_27B_PAID_SCRIPT_SYNTAX_PASS`
- `AQLEVON_27B_FREE_PREFLIGHT_NO_ACTIVE_POD_PASS`
- runpodctl `2.14.0-dd55bcf`
- `AQLEVON_27B_FREE_CAPACITY_PASS 1.59 US-KS-2 Low`

## Next gate

A brand-new explicit owner authorization is required.
Do not reuse Authorization 03 or 04.

Recommended cap:
**USD 1.50 maximum total**

**FINAL: READY_FOR_NEW_FRESH_AUTH_AFTER_EXACT_PAID_PATH_FIX**
