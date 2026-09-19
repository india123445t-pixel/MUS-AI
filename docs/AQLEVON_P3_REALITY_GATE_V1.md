# AQLEVON P3 Reality Gate V1

**Worker:** 05 — Evaluation / Truth / Red-Team  
**Task:** `P3-A05-REALITY-GATE`  
**Status:** execution-preparation implementation; no model gain claimed  
**Authority:** evidence-only. Model promotion remains `AQLEVON_EVALUATION_DECISION_RECEIPT_V1` + Manager review.

## Purpose

The P3 Reality Gate detects cases where training appears to improve reward or benchmark success while real, transferable, integrity-clean capability does not improve. It is designed for the first coding/tool capability gene and later matched-compute method tournaments.

The gate never upgrades a model by itself. `REALITY_PASS` means only that the supplied candidate evidence survived the P3 reality checks. A promotion or release claim still requires the authoritative Worker-05 Evaluation Decision Receipt path and Manager review.

## Evidence chain

All new self-hashed P3 objects use the Manager-frozen P2.1 profile:

`AQLEVON_CANONICAL_JSON_SHA256_V1`

The chain is:

`frozen reality policy -> baseline/candidate outcome packs -> metrics + checkpoint curve + optional seed-null -> AQLEVON_REALITY_GATE_EVIDENCE_V1 -> authoritative Evaluation Decision Receipt / Manager`

The Reality Gate does not replace P1 contamination/provenance/red-team evidence, P2.1 preregistration chronology, or Worker-06 runtime attempt truth.

## Outcome pack

`AQLEVON_REALITY_OUTCOME_PACK_V1` is a self-hashed evidence bundle. It binds:

- Candidate Artifact Manifest SHA-256;
- evaluation harness SHA-256;
- Worker-02 task-factory manifest SHA-256;
- hidden-canary manifest SHA-256;
- raw outcome-log SHA-256;
- opaque task IDs, domain IDs and split labels;
- ordered sampling outcomes;
- metamorphic/isomorphic group and variant identities;
- opaque hidden-canary IDs only.

It deliberately rejects prompt/answer/solution/output plaintext. Hidden canaries are represented by opaque SHA-256 identities and outcomes, not by secret content.

## RawPass@k / CleanPass@k / HackGap

For each task and requested `k`:

- `RawPass@k`: at least one of the first `k` samples receives the raw environment/reward success signal.
- `CleanPass@k`: at least one of the first `k` samples passes objective clean truth **and** has no integrity violation.
- `HackGap@k`: `RawPass@k - CleanPass@k` over the same task population.

The evidence retains exact task counts plus canonical decimal display rates. Gate comparisons use exact integer/Fraction arithmetic and frozen basis-point thresholds, not binary floating point.

A candidate can therefore improve RawPass while being rejected because CleanPass fails to improve or HackGap grows.

## TransferPass@k

Tasks marked `split=transfer` form a sealed transfer population. The candidate must beat the frozen baseline by the policy's explicit minimum transfer delta. Training/task-generation code does not receive these items through this evidence schema.

## Hidden canaries

Tasks marked `split=canary` must:

- carry `is_hidden_canary=true`;
- carry a unique opaque `canary_id_sha256`;
- bind the frozen `hidden_canary_manifest_sha256`;
- contain no canary prompt/answer/solution plaintext.

A policy freezes the minimum CleanPass@1 floor for this population before candidate inspection.

## Metamorphic / isomorphic invariance

Primary/transfer tasks may carry `metamorphic_group_id` + `variant_id`. Every group must have at least two variants.

Two complementary invariance metrics are emitted:

1. **CleanPass group invariance by k** — whether all semantics-preserving variants agree on task-level CleanPass@k.
2. **Paired-slot invariance** — whether the ordered sampling slot has the same clean-success state across variants.

Both have independent hard floors. This catches models that win only under one surface form even if aggregate pass rate looks acceptable.

## Seed-vs-resampling null

`AQLEVON_SEED_VS_RESAMPLING_NULL_V1` compares union task coverage from independently trained seeds with equal-count repeated-resampling groups from one frozen model/seed.

The utility is deterministic: callers supply the frozen resampling groups; no RNG occurs inside the gate. The result self-hashes:

- task universe;
- independent-seed success sets;
- null resampling groups;
- observed union coverage;
- null union distribution summary;
- finite-sample one-sided p-value with +1 correction.

Method-level robustness claims can be configured to require this test. Artifact-level candidate evaluation can remain separate from method-level reproducibility claims.

## Weakest-domain floors

The policy must explicitly list every required domain and a CleanPass@1 floor in basis points. Missing domains or a candidate below any frozen floor cause rejection even if mean capability improves.

No numeric domain floor is silently invented by the code. The Manager/evaluation owner must freeze the policy before candidate outputs are inspected.

## Proxy reward vs clean truth checkpoint curve

Each evaluated checkpoint carries integer basis-point values for:

- proxy/environment reward success;
- clean objective truth success.

The baseline is the first checkpoint. If any later checkpoint improves proxy reward while clean truth does **not** improve over baseline, the gate records a divergence onset and rejects the candidate/method under V1. A later recovery does not erase the fact that the optimization entered a reward-divergent regime; this is deliberately conservative so expensive RL runs can stop early.

## Integrity / anti-laundering controls

The implementation binds:

- P2.1 self-digest on policy;
- P2.1 self-digest on baseline and candidate outcome packs;
- P2.1 self-digest on seed-null result;
- SHA-256 of the exact `reality_gate_v1.py` code used to emit the evidence;
- supporting task/harness/canary/raw-log hashes;
- final P2.1 evidence self-digest.

`validate_reality_gate_evidence()` can optionally receive the policy, baseline pack, candidate pack, checkpoint curve and seed-null result. When supplied, it rebuilds the expected evidence and requires byte-equivalent semantic content. Rehashing a forged metric block therefore does not make it valid.

## Authority boundary

Every P3 evidence object carries:

- `authoritative_for_model_promotion = false`;
- `authoritative_for_arbitrary_runtime_attempts = false`;
- promotion requirement = `VALID_AQLEVON_EVALUATION_DECISION_RECEIPT_V1_PLUS_MANAGER_REVIEW`.

`REALITY_PASS` is not `PROMOTION_ELIGIBLE`. It is one required evidence layer for the future physical-capability path.

## CLI

Build evidence:

```bash
python reality_gate_v1.py build-evidence \
  --baseline baseline_pack.json \
  --candidate candidate_pack.json \
  --policy reality_policy.json \
  --curve checkpoint_curve.json \
  --seed-null seed_null.json \
  --method-level-claim
```

Validate structurally and semantically:

```bash
python reality_gate_v1.py validate-evidence \
  --evidence reality_evidence.json \
  --policy reality_policy.json \
  --baseline baseline_pack.json \
  --candidate candidate_pack.json \
  --curve checkpoint_curve.json \
  --seed-null seed_null.json
```

## Validation evidence for P3 implementation

Final local exact-source suite:

- P1 truth gate: 23/23 PASS;
- P2/P2.1 Evaluation Decision Receipt: 45/45 PASS;
- P3 Reality Gate: 34/34 PASS;
- combined: **102/102 PASS**;
- Python compilation: PASS;
- P1 policy JSON parse: PASS.

P3 regression coverage includes:

- RawPass/CleanPass/HackGap/TransferPass calculation;
- clean-gain floor;
- transfer-gain floor;
- hard hidden-canary floor;
- hard weakest-domain floor;
- HackGap absolute cap and non-worsening cap;
- metamorphic group invariance;
- paired-slot invariance;
- exact proxy-reward/clean-truth divergence rejection;
- recovered-later divergence still rejected;
- seed-vs-resampling null significance;
- missing/non-significant method-level seed evidence;
- outcome-pack tamper detection;
- seed-null tamper detection;
- forbidden plaintext rejection;
- duplicate canary identity;
- insufficient pass@k samples;
- malformed metamorphic groups;
- baseline/candidate binding mismatch;
- candidate identity collision;
- checkpoint basis-point/step validation;
- evidence self-digest tamper;
- policy-binding mismatch;
- promotion-authority laundering attempt;
- no direct floats in authoritative evidence;
- semantic metric laundering after outer rehash;
- CLI build + semantic validation end-to-end.

## Non-claims

This implementation used no GPU and performed no model training. Synthetic fixtures can produce `REALITY_PASS` only to test gate behavior. They are not AQLEVON capability evidence. No production system, model weights, canonical Manager file, or `main` branch is modified by this implementation.