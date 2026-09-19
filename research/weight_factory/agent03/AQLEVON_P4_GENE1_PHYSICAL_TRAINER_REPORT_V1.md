# AQLEVON Worker 03 — P4 Gene #1 Physical Trainer

**Task:** `P4-A03-GENE1-PHYSICAL-TRAINER`  
**Worker:** `03`  
**Date:** 2026-09-19  
**Base:** Worker-03 P3 head `4a7a5fa2c2c4ba5f291564251c290e2c416ce6ec`  
**Status:** implementation/preparation complete; physical surrogate execution **BLOCKED by explicit W01+W02 dependency**.

## Starting truth

G1/R0-A is complete and passed on the canonical base. This P4 lane does not contain a G1 rerun command and treats the G1 source commit as historical evidence only.

Canonical base remains:
- `Qwen/Qwen3.8-27B`
- revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- BF16 adapter-only policy unless Manager explicitly authorizes a different update class.

Same-architecture surrogate remains:
- `Qwen/Qwen3.5-4B-Base`
- revision `daa9c16f371249f9ad1c75a9ed6f956c08ea08f5`.

## Explicit P4 dependency check

P4 states that Worker 03 begins surrogate training only when **Worker 01 method specs + Worker 02 training-visible pack** exist.

Checked twice during this execution:
- `/AQLEVON/Coordination/AGENT_01.md` remains version 10 and contains no `P4-A01-METHOD-TOURNAMENT-DIRECTOR` completion/input;
- `/AQLEVON/Coordination/AGENT_02.md` remains version 8 and contains no `P4-A02-GENE1-DATA-VERIFIER-PACK` completion/input;
- GitHub search found no P4 W01/W02 PRs and expected P4 branch names were absent at the time of the second check.

Therefore Worker 03 must not invent a method winner, method arm list, P4 training shard, or sealed-evaluation boundary. Physical surrogate training has not started.

## Implemented now

### 1. `p4_gene1_trainer.py`
Fail-closed P4 input/freeze/execution contract:
- accepts only `AQLEVON_P4_GENE1_METHOD_TOURNAMENT_SPEC_V1` from Worker 01 / exact P4 task identity;
- enforces 1–3 method arms only;
- supports the P3/P4 frozen method vocabulary but does not select a winner;
- rejects any hidden/sealed/protected-evaluation reference from method parameters or training rows;
- validates the complete P2.1 Training Shard Manifest field surface, P2.1 self-digest, shard byte identity, row count and trainable-row shape;
- freezes exact method spec SHA, manifest SHA, shard bytes SHA, model/revision/precision and arm parameters into `AQLEVON_P4_GENE1_FROZEN_TRAINING_PLAN_V1`;
- freezes `g1_status=ALREADY_PASSED_DO_NOT_RERUN`;
- creates immutable command locks with `automatic_fallback=false` and `g1_rerun=false`;
- paid execution fails closed without an exact Manager authorization bound to plan SHA + command SHA + profile;
- training-run receipt explicitly says `NOT_EVALUATED_BY_WORKER05` and `capability_gain_claim=false`.

### 2. `p4_method_spec.schema.json`
Machine-readable handoff contract for Worker-01 P4 method freeze. It requires:
- Worker 01 P4 authority identity;
- maximum three arms;
- exact supported method identifiers;
- seed/budget/optimizer/stop/runner parameters;
- P2.1 hash profile and self-hash identity.

The Python validator remains authoritative for self-digest and forbidden-evaluation checks.

### 3. `p4_sft_surrogate.py`
Physical SFT/LoRA surrogate control runner ready for the simple control arm:
- exact pinned `Qwen/Qwen3.5-4B-Base` revision;
- exact package profile `transformers 5.17.0 / peft 0.21.0 / accelerate 1.15.0`;
- BF16 only, no QLoRA;
- q/v LoRA discovery, frozen rank from run parameters;
- deterministic seed must be present in frozen W01 spec;
- optimizer-update ceiling comes only from the frozen plan;
- training data comes only from the exact Worker-02 shard bound into the plan;
- nonfinite/zero-gradient/nonzero-delta checks;
- adapter save/reload state SHA equality;
- GPU-seconds and peak VRAM telemetry;
- output status is only `COMPLETED_ARTIFACT_PENDING_WORKER05_EVALUATION`;
- never emits capability/promotion truth.

Non-SFT method arms are deliberately not fabricated before W01 freezes P4 arms. A non-SFT arm passed to this runner fails closed.

## Manager paid-run authorization gate

`AQLEVON_MANAGER_PAID_RUN_AUTHORIZATION_V1` must bind all of:
- P4 task id;
- frozen training-plan SHA;
- exact canonical command SHA;
- exact hardware/profile string;
- Manager authority identity;
- provider;
- max budget;
- max wall time;
- authorization timestamp;
- P2.1-style self digest.

A paid flag without this exact object fails before subprocess launch. This applies both to surrogate paid runs and eventual 27B training. No authorization object was fabricated by Worker 03.

## Tests

Final local CPU/unit suite:
- `14/14 PASS`;
- `py_compile` PASS for both Python modules and tests;
- JSON Schema parse PASS.

Coverage includes:
- valid P4 method spec;
- >3 arms rejection;
- P3/non-P4 Worker-01 authority rejection;
- hidden/sealed eval reference rejection;
- complete Training Shard manifest + exact byte binding;
- shard tamper rejection;
- private-eval leakage in training row rejection;
- frozen plan exact input bindings;
- explicit G1 `DO_NOT_RERUN` lock;
- command lock self-digest;
- paid run without Manager authorization rejection;
- authorization plan/profile/command binding;
- training receipt cannot claim capability gain;
- direct float rejection under canonical hash profile;
- SFT frozen seed/budget enforcement;
- SFT runner rejecting non-SFT methods.

No GPU test was run because the required P4 W01/W02 inputs do not yet exist, and no paid run was authorized for this P4 task.

## Remaining critical path / blocker

Worker 03 can proceed immediately when both exact dependencies appear:
1. Worker-01 P4 machine-readable method spec (<=3 arms) compatible with the contract or accompanied by Manager-approved interface adjustment;
2. Worker-02 P4 training-visible shard + valid P2.1 Training Shard Manifest, without sealed evaluation assets.

Then the legal sequence is:
- freeze exact P4 plan;
- run only the smallest Manager-authorized/free surrogate compute necessary for the frozen arms;
- emit one candidate artifact/report per arm/seed;
- Worker 05 evaluates hidden evidence;
- wait for Worker-05 decision + Manager recipe authorization;
- only then one canonical 27B Gene #1 training run;
- emit nonzero delta/save-reload/hashes/training receipt/Candidate Artifact Manifest;
- Worker 05 reality evaluation;
- Manager alone accepts/rejects capability gain.

There is no legal path to the 27B candidate before surrogate decision + Manager authorization.

## Deliberately not done

- no G1 rerun;
- no surrogate GPU execution using stale P3 method/data inputs;
- no 27B Gene #1 training;
- no paid GPU execution;
- no sealed evaluation access;
- no Worker-05 evaluation claim;
- no capability-gain claim;
- no production mutation;
- no `main` merge;
- no modification of another worker branch.
