# AQLEVON 27B — Authorization 05 Timeout / Retry Path Hardened

Timestamp: 2026-09-27
Reviewer/Executor: AQLEVON Manager
State: **PAID_ATTEMPT_05_STOPPED_SAFE / RETRY_PATH_FREE_PREFLIGHT_PASS / BUDGET_EXTENSION_REQUIRED**

## Paid attempt 05

Authorization:
`P4-AQLEVON-27B-R0-FRESH-20260927-1425-05`

GitHub Actions:
- run: `36326291713`
- execute job: `108639605738`
- conclusion: FAILURE (fail-closed budget timeout)

Provider:
- pod id: `v3njg70l4mtazn`
- pod name: `AQLEVON-27B-R0-BUDGET8`
- image: `ghcr.io/india123445t-pixel/mus-ai@sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec`
- machine id: `diqbvodr0g2c`
- rate: USD 1.59/hour
- current state: EXITED

Exact controller result:
- final_stage: `BUDGET_WINDOW_TIMEOUT`
- billed_seconds_estimate: `3004`
- compute_cost_estimate_usd: `1.326767`
- pod_stopped: true
- pod_stopped_and_deleted: false
- sealed_eval_consumed: false
- durable artifact: none (training did not reach DONE)

## What happened

Timeline from controller evidence:
- provider create: 2026-09-27T14:32:55Z
- image pull/extract consumed most startup time
- container/hardware became ready around 14:59
- model staging completed at ~15:00:58
- training stage began ~15:01:02
- training remained active until control cutoff
- cutoff reached at elapsed ~3003 seconds
- pod stopped at ~15:22:59

There was no observed trainer crash before cutoff.

Historical trainer blob and current trainer blob match:
`9085e692d43110600e7bf214ffdab910f4821f1c`

The stopped pod had:
- containerDiskInGb: 100
- volumeInGb: 0

Therefore its /workspace was not backed by a persistent Pod volume for attempt 05. Partial train.log/candidate bytes are not treated as recoverable evidence.

Authorization 05 is now explicitly marked consumed/invalidated and MUST NOT be reused.

## Free retry-path hardening completed

Operational branch changes after attempt 05:

1. Per-authorization claim ledger
   - future reservation/consumed receipts use:
     `.github/runpod-control/claims/<authorization_id>.reservation.json`
     `.github/runpod-control/claims/<authorization_id>.consumed.json`
   - historical claim evidence no longer blocks a distinct fresh child authorization.

2. Persistent workspace
   - future create path uses:
     - container disk: 100 GB
     - persistent volume disk: 100 GB
     - mount: `/workspace`
   - future stopped runs retain model cache/logs/candidate bytes on the Pod volume until deletion.

3. Live trainer diagnostics
   - the unchanged trainer is executed with `PYTHONUNBUFFERED=1`
   - stdout/stderr is both streamed and persisted through `tee "$ROOT/train.log"`
   - scientific trainer code/blob is unchanged.

4. Runtime budget window
   - MAX_ELAPSED increased from 3000 to 3200 seconds.
   - At USD 1.59/hour, 3200 seconds of GPU compute is ~USD 1.4133, below the per-run USD 1.50 ceiling.

5. Exact trainer binding
   - live pre-create gate now requires current trainer blob:
     `9085e692d43110600e7bf214ffdab910f4821f1c`

6. Explicit stopped-pod retry mode prepared
   - a future fresh authorization may bind `resume_pod_id`.
   - before reservation, the Pod must verify read-only as the exact expected EXITED Pod/image/rate.
   - only after durable single-use reservation may the control plane edit/resume it.
   - this is intended to reuse the same physical machine and avoid unnecessary image-pull work when available.
   - no resume/provider mutation was executed during this free preparation.

## Free validation

Workflow:
`AQLEVON 27B Free Capacity Preflight`

Run:
`36330422992`

Job:
`108651161591`

Conclusion:
**SUCCESS**

Verified:
- paid script syntax: PASS
- bootstrap syntax: PASS
- no active AQLEVON 27B Pod: PASS
- runpodctl: `2.14.0-dd55bcf`
- persistent volume flags supported: PASS
- per-authorization claim ledger synthetic test: PASS
- A100-SXM4-80GB secure capacity: PASS
- live price: USD 1.59/hour
- data center: `US-KS-2`
- stock: Low

Stopped Pod re-check:
- pod id: `v3njg70l4mtazn`
- desiredStatus: EXITED
- machine id: `diqbvodr0g2c`
- image identity unchanged
- costPerHr: 1.59

## Budget ledger

Standing retry directive was recorded with cumulative actual paid GPU spend cap: USD 1.50.

- Auth 03: USD 0.00 GPU
- Auth 04: USD 0.00 GPU
- Auth 05: USD 1.326767 estimated GPU
- cumulative: USD 1.326767
- remaining under current standing cap: **USD 0.173233**

No new paid run may be started under that remaining cumulative cap because it is insufficient for a scientifically complete retry.

## Next execution state

Engineering/control plane: READY.
Provider: no running GPU.
Retained stopped Pod: available for an explicitly bound retry.
Scientific recipe: unchanged.
Historical W05: untouched.
main: not merged.

A single cumulative-budget extension from the owner is the only remaining paid gate.

Recommended next cumulative ceiling:
**USD 2.80 total**, including the USD 1.326767 already spent.

This permits one complete fresh child attempt while preserving the per-run <= USD 1.50 limit.

**FINAL STATE: RETRY_READY_AWAITING_CUMULATIVE_BUDGET_EXTENSION**
