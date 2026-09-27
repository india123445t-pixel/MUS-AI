# AQLEVON Auth08 Final Public Eval — Attempt 01 Pre-Inference Failure / Fixed

Timestamp: 2026-09-27
Manager state: **ATTEMPT_01_STOPPED_SAFE / NO_MODEL_DISPATCH / ROOT_CAUSE_FIXED / FRESH_AUTH_REQUIRED**

## Owner authorization consumed

Owner authorized one final AQLEVON-27B unified public evaluation with max USD 1.50.

Operational authorization:
`AQLEVON-AUTH08-PUBLIC-EVAL-20260927-01`

GitHub Actions:
- paid control run: `36339275953`
- execute job: `108676038243`
- source SHA: `f2da8599886703a9b389d109a1e7c7304746c199`
- final GitHub run conclusion: `cancelled` after explicit cleanup

Provider:
- pod id: `a6hxcy4h40l5gd`
- name: `AQLEVON-AUTH08-EVAL`
- A100-SXM4-80GB
- rate: USD 1.59/hour
- created: 2026-09-27T18:04:32.748Z
- stopped: 2026-09-27T18:09:47Z
- billed-window estimate: ~315 seconds
- estimated GPU cost: **USD 0.139125**
- current state: **EXITED**

## What failed

The encrypted bundle transfer succeeded:
- candidate adapter + evaluation manifests reached the container.

Failure occurred immediately during bundle extraction on the persistent volume.

Observed error:
`tar: ... Cannot change ownership to uid 1001, gid 1001: Operation not permitted`

The archive preserved source ownership metadata. Extraction on the mounted workspace attempted ownership restoration and failed.

Important:
- base-model staging had NOT started;
- generalization inference had NOT started;
- paired-public inference had NOT started;
- model dispatches executed: **0 / 352**;
- no evaluation score exists from this attempt;
- no sealed/private W05 material was used.

## Fail-closed cleanup

Manager detected the error through a read-only Pod log monitor.

Emergency cleanup:
- Pod stop sent and verified;
- Pod state confirmed `EXITED`;
- paid workflow explicitly cancelled to avoid useless GitHub waiting;
- command restored to read-only `status`;
- authorization marked consumed/invalidated and MUST NOT be reused.

## Root-cause repair

Bootstrap changed from:

`tar -xzf "$BUNDLE" -C "$ROOT/bundle"`

to:

`tar --no-same-owner -xzf "$BUNDLE" -C "$ROOT/bundle"`

No model, prompt, seed, threshold, candidate identity, scoring rule, or scientific evaluation protocol changed.

## Free verification

First post-fix full free preflight:
- run `36339668211`
- conclusion: SUCCESS

Dedicated ownership-defect reproduction:
- run `36339909281`
- job `108677837713`
- conclusion: **SUCCESS**

Passed step:
`Reproduce and close bundle ownership extraction defect`

The test:
1. creates an archive whose entries claim uid/gid 1001;
2. extracts using the exact `--no-same-owner` behavior;
3. verifies payload bytes;
4. verifies the production bootstrap contains the corrected command.

All other frozen checks also passed:
- Agent04 challenge/harness tests;
- Agent03 scientific contract;
- Python/shell syntax;
- Auth08 candidate hash bindings;
- unified 352-dispatch static contract.

## Current paid state

- no active Auth08 evaluation GPU;
- failed Pod is stopped;
- command is read-only status;
- authorization 01 is consumed/invalidated;
- no paid retry is currently authorized.

## Next gate

Because authorization 01 was single-use and provider-create occurred, it cannot be reused even though inference never started.

A new explicit fresh paid authorization is required for another provider start.

Recommended wording:
**أصرح بمحاولة جديدة لتقييم AQLEVON-27B النهائي بحد أقصى 1.50 دولار، واستمر حتى تظهر النتيجة ضمن هذا التصريح.**

**FINAL STATE: RETRY_PATH_FIXED_AND_FREE_VERIFIED / FRESH_PAID_AUTH_REQUIRED**
