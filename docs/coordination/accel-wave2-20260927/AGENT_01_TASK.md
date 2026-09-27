# AGENT 01 — CONTROL-PLANE CONSOLIDATION OWNER

Mode: FREE-ONLY.
Exclusive mutation lane: RunPod/27B control-plane and preservation workflow.

Mission:
Produce one consolidated future-run control path that combines the already accepted PR #54 artifact-preservation design with the remaining Agent 03 hardening requirements.

Required:
1. Start from the latest Agent 01 durability branch / PR #54 state.
2. Add workflow-level single-flight serialization (fixed concurrency group, cancel-in-progress false) and/or a durable pre-create reservation/lease that closes the provider-create race.
3. Make authorization consumption/reservation fail closed before duplicate paid pod creation can occur.
4. Preserve exact runtime package versions durably in the final result/evidence receipt.
5. Keep upload-before-delete fail-closed artifact ordering intact.
6. Add FREE-only tests for:
   - two concurrent logical starts cannot both pass reservation;
   - missing/invalid reservation blocks provider create path;
   - artifact upload failure still prevents deletion;
   - runtime version receipt is required and durable;
   - no scientific training constants changed.
7. Do not trigger provider API mutations in tests.
8. Leave a Draft PR or update the existing Draft PR only if collision-free. Do not merge.

Completion verdict must be:
CONTROL_PLANE_READY_FOR_FRESH_AUTH
or
CONTROL_PLANE_BLOCKED_<reason>
