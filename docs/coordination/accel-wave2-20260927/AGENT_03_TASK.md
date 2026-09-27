# AGENT 03 — 27B REPRODUCIBILITY + DUAL-EVAL CONTRACT OWNER

Mode: FREE-ONLY.
Exclusive mutation lane: 27B scientific run contract and public evaluation reproducibility.

Mission:
Freeze a machine-verifiable contract for the next 27B candidate WITHOUT changing the historical training recipe merely to improve metrics.

Required:
1. Freeze exact base/revision, BF16, LoRA topology, trainable-param expectation, optimizer, LR schedule, update count, data generator identity, source blobs, and training indices.
2. Preserve the historical public metric path for comparability.
3. Add a second preregistered public evaluation path using SAME seeds for base and candidate, so the historical label-derived seed confound cannot recur.
4. The new paired evaluation must be additional evidence, not a rewrite of historical R0.
5. Bind exact seeds, sampling parameters, tasks, verifier, retry rules, and thresholds before any new candidate answers.
6. Add static/CPU tests proving:
   - training recipe constants match frozen contract;
   - base/candidate paired evaluation uses identical seeds;
   - no task/seed dropping;
   - no sealed/private W05 source is referenced.
7. Produce a machine-readable run contract/hash that Agent 01 can require before future paid execution.
8. No GPU, no inference, no paid action, no main merge.

Completion verdict:
RERUN_SCIENTIFIC_CONTRACT_READY
or
RERUN_SCIENTIFIC_CONTRACT_BLOCKED_<reason>
