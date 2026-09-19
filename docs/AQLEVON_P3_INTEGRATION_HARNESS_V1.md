# AQLEVON P3 Integration Harness V1

**Worker:** 04  
**Task:** `P3-A04-INTEGRATION-HARNESS`  
**Boundary:** generic dry-run infrastructure only. No real AQLEVON gene is merged, distilled, routed, quantized, trained, or promoted by this harness.

## Purpose

Remove setup latency from the future Integration Tournament while preserving P2.1 identity/evaluation authority. Real integration remains blocked until at least two independently `PROMOTION_ELIGIBLE` Capability Genes exist and Manager authorizes an execution wave.

## Source admission

`bind_promoted_gene()` consumes one Candidate Artifact Manifest plus its Evaluation Decision Receipt and, by default, calls the accepted P2.1 `validate_candidate()` / `validate_eval()` implementation. It additionally requires:
- `artifact_type=adapter`;
- not `probe_only`;
- exact evaluation-to-candidate binding;
- `final_status=PROMOTION_ELIGIBLE`;
- SHA-256 identities for candidate, evaluation receipt and adapter state.

`canonicalize_gene_bank()` then requires >=2 unique genes and exact equality of base repository, base revision, base-manifest identity, parameter-layout identity and topology class. It canonicalizes source order lexicographically by Candidate Artifact Manifest SHA-256.

No adapter bytes are loaded by the P3 harness.

## Tournament interfaces

Prepared dry-run adapters/interfaces:
- `ties` — static control interface;
- `dare` — static control interface;
- `della` — static control interface;
- `ctm` — Compress-then-Merge interface;
- `HardTop1Router` — deterministic top-1 routing over integer route scores;
- `OracleRouteCeiling` — evaluation-only expert ceiling using clean verified outcome scores;
- `MOPDExperimentStub` — multi-teacher on-policy distillation experiment contract with teacher/student cost hooks.

Every plan emits `execution_authorized=false` and truth boundary `DRY_RUN_ONLY_NO_REAL_GENE_INTEGRATION_OR_CAPABILITY_CLAIM`. The module contains no tensor merge/training invocation.

## Exact cost-accounting hooks

`CostAccounting` uses integer units only:
- teacher GPU milliseconds;
- student GPU milliseconds;
- merge GPU milliseconds;
- CPU and wall milliseconds;
- teacher/student/rollout tokens;
- peak train VRAM bytes;
- peak serving VRAM bytes.

`total_gpu_millis` is recomputed from teacher + student + merge components. Negative or non-integer values fail closed. This makes MOPD teacher cost visible instead of hiding it inside student training cost.

## Result schema

`AQLEVON_INTEGRATION_TOURNAMENT_RESULT_V1` records:
- method + canonical source identities;
- per-domain specialist/candidate scores and retention in integer ppm;
- explicit weakest-domain retention;
- interference-report identity + catastrophic regression count;
- TTFT/token p50/p95 latency in microseconds;
- serving/train VRAM in bytes;
- quantization-survival status and evidence identity;
- exact compute/token cost receipt;
- deterministic self-digest.

Floats are deliberately rejected by the Python harness; experiment producers must use integer fixed-point units. This avoids platform-dependent canonicalization and keeps future result receipts auditable.

## Router/oracle interpretation

The hard router and oracle are deliberately separate. The oracle is not deployable routing; it measures the ceiling available from the existing frozen experts. Future routing error is therefore measurable as the gap between hard-router behavior and oracle behavior rather than being confused with weak specialists.

Dynamic routing is intentionally absent from P3-A04 because P2.2/P3 policy says it is only justified after hard routing demonstrates a real compositional/oracle gap.

## Tests

Synthetic/dummy identities only. Tests cover promotion binding, source-order invariance, lineage mismatch, duplicate rejection, all four static interfaces, float rejection, hard-route determinism, oracle selection, exact MOPD cost accounting, result self-digest/tamper detection, quantization-evidence requirements and cost-total integrity.

## Truth boundary

This harness proves control-plane readiness only. It does not prove TIES/DARE/DELLA/CtM quality, router quality on real prompts, MOPD consolidation quality, quantization survival, or any model-capability gain. Those require real promoted genes plus Manager-authorized execution and Worker-05/06 evidence.
