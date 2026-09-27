# AQLEVON 27B — Fresh Authorization 03 Pre-Create Failure + Capacity Fix

Timestamp: 2026-09-27
Manager status: **FAILED_PRECREATE_NO_GPU_COST / FIXED_FREE_PREFLIGHT_PASS**

## Failed authorization

Authorization ID:
`P4-AQLEVON-27B-R0-FRESH-20260927-141120-03`

Owner cap:
USD 1.50 maximum total.

Paid workflow run:
`36325059613`

Execute job:
`108636150683`

Observed sequence:
- fresh authorization V2: PASS
- scientific contract pre-create: PASS
- no active AQLEVON 27B pod: PASS
- failure occurred before reservation/consumption and before provider create
- artifact upload/finalizer then failed closed because no evidence archive existed

Durable post-failure evidence:
- reservation file: ABSENT
- consumption file: ABSENT
- fresh result file: ABSENT
- provider status: pod_count=0
- GPU compute cost for this attempt: USD 0.00

The authorization was explicitly invalidated and MUST NOT be reused.

## Root cause and repair

Failure boundary was the runpodctl install/capacity stage.

Old installer:
`curl -sSL https://cli.runpod.net | sudo bash`

Production path repaired to use:
`https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64`

The failed authorization was disabled:
- command restored to `status`
- fresh_authorization=false
- training_authorized=false
- invalidated_after_failed_attempt=true

## Free live capacity verification

Workflow:
`AQLEVON 27B Free Capacity Preflight`

Run:
`36325355655`

Job:
`108636959411`

Conclusion:
**SUCCESS**

Live evidence:
- no active AQLEVON 27B pod: PASS
- runpodctl: `2.14.0-dd55bcf`
- GPU: `NVIDIA A100-SXM4-80GB`
- secure price: `1.59 USD/hour`
- data center: `US-KS-2`
- stock: `Low`
- price ceiling <= 1.60 USD/hour: PASS

## Current next gate

A new fresh single-use owner authorization is required before any paid execution.

Recommended cap remains:
**USD 1.50 maximum total**.

Do not reuse Authorization 03.

**STATE: READY_FOR_NEW_FRESH_AUTH_AFTER_FREE_CAPACITY_FIX**
