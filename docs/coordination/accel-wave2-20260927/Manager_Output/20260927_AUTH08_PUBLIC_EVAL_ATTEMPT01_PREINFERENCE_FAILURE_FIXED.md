# AQLEVON Auth08 Public Eval Attempt 01 — Failed Before Inference / Fixed

Timestamp: 2026-09-27
Manager state: **ATTEMPT_01_CONSUMED_AND_CLOSED / ZERO_MODEL_DISPATCH / FIX_READY_FOR_FREE_PREFLIGHT**

Authorization:
`AQLEVON-AUTH08-PUBLIC-EVAL-20260927-01`

Run:
`36339275953`

Pod:
`a6hxcy4h40l5gd`

Provider timing:
- created: 2026-09-27T18:04:32.748Z
- stopped: 2026-09-27T18:09:47Z
- approximate billed duration: 315 seconds
- rate: USD 1.59/hour
- approximate compute cost: USD 0.139125

Observed failure:
- image downloaded successfully
- transfer bundle received successfully
- failure occurred during bundle extraction on persistent /workspace volume
- GNU tar attempted to restore archive uid/gid 1001 and the mounted volume rejected chown
- error: `Cannot change ownership to uid 1001, gid 1001: Operation not permitted`
- no base model staging completed
- no inference began
- model dispatches executed: 0

Fail-closed response:
- emergency pod stop succeeded
- pod state verified EXITED
- workflow run cancelled after pod stop
- authorization 01 marked consumed/invalidated and MUST NEVER be reused
- command restored to read-only status

Fix:
- bootstrap extraction changed from:
  `tar -xzf "$BUNDLE" -C "$ROOT/bundle"`
- to:
  `tar --no-same-owner -xzf "$BUNDLE" -C "$ROOT/bundle"`

Scientific evaluation matrices, candidate hashes, prompts, seeds, and scoring contracts were not changed.

A fresh paid authorization is required for any retry.

**STATE: FREE_PREFLIGHT_AFTER_TAR_FIX_PENDING**
