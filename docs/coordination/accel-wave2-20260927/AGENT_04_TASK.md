# AGENT 04 — FROZEN GENERALIZATION INFERENCE HARNESS OWNER

Mode: FREE-ONLY.
Exclusive mutation lane: execution/scoring harness for the already frozen public Agent 04 challenge.

Mission:
Make PR #53's frozen challenge executable immediately once durable candidate bytes exist, without running model inference now.

Required:
1. Use the already frozen challenge/protocol exactly; do not change prompts, seeds, task set, retry rules, scoring, or thresholds.
2. Build an inference-result ingestion + deterministic scoring harness for:
   - canonical base;
   - candidate adapter on same base;
   - four common seeds;
   - 64 attempts/system.
3. The harness must reject:
   - missing task/seed pairs;
   - duplicate pairs;
   - extra pairs;
   - wrong model identity;
   - wrong challenge/freeze hash;
   - malformed outputs.
4. Compute the frozen primary delta, discordant-pair exact one-sided sign/binomial p-value, and robust-task secondary metric.
5. Add synthetic CPU tests for pass/fail edge cases.
6. Produce a no-GPU run manifest/template for a future authorized inference executor.
7. No actual inference, GPU, paid API, or main merge.

Completion verdict:
GENERALIZATION_HARNESS_READY
or
GENERALIZATION_HARNESS_BLOCKED_<reason>
