# AQLEVON B07-E0 — Capability Update Prediction Falsifier

**Task:** `B07-02-BUILD-THE-BREAKTHROUGH-FALSIFIER`  
**Purpose:** test whether a tiny compiler can predict a useful weight update for capability families it never saw during compiler fitting.  
**Truth boundary:** this harness is a falsification experiment. A positive result is evidence to replicate, **not** a breakthrough or AQLEVON capability claim.

## What this experiment is designed to kill

ACC is killed if its compiled update does not behaviorally beat all mandatory controls on enough wholly held-out capability families:

- `zero_update`
- `random_same_norm`
- `nearest_adapter`
- `mean_delta`
- `basis_pc1_same_norm`

The decision is made from hidden behavioral pass rates, not adapter reconstruction error. The held-out families are absent from compiler fitting. Their direct LoRA adapters are loaded only as an upper anchor during final evaluation.

If ACC is killed, `decide` emits `apa_followup_spec.json` for the next Plasticity Atlas/support-reuse experiment. The harness does not escalate to a bigger hypernetwork.

## Frozen experimental choices

- Base: `Qwen/Qwen3.5-0.8B-Base`
- Revision: `dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`
- License recorded at freeze: Apache-2.0
- Size class recorded at freeze: 0.8B; runtime uses the checkpoint text submodel through `AutoModelForCausalLM`.
- Architecture relevance: `qwen3_5`, 24 text layers with a 3:1 linear-attention/full-attention pattern, matching the architectural family used by AQLEVON’s larger Qwen3.8 target.
- LoRA: rank 2, alpha 2, `q_proj` + `v_proj`
- 12 AQLEVON-owned deterministic micro-capability families
- 8 compiler-training families / 4 completely held-out families
- no protected benchmark prompts or templates
- no closed-model outputs
- no Worker-02 private/protected verifier assets

The micro-capabilities are deliberately simple modular arithmetic protocols. This makes B07-E0 a generous, cheap test of whether reusable update structure exists at all. Failure here is strong evidence against spending on a more complex compiler. Success only earns replication on a stronger same-family surrogate.

## Why raw LoRA A/B factors are never the compiler target

LoRA factors are non-unique: `A -> kA`, `B -> B/k` leaves the actual operator unchanged. Training a compiler against raw factors could therefore create false structure.

B07-E0 works in the canonical operator geometry without materializing full dense deltas. For two LoRA updates it computes the exact Frobenius inner product:

`<B1 A1, B2 A2>_F = tr((B1^T B2)(A2 A1^T))`

This produces a gauge-invariant Gram matrix over actual `ΔW` operators. Kernel PCA/SVD-like coordinates are derived from that Gram matrix. A ridge regression maps a sealed capability capsule feature into those coordinates. Every compiled/control update is then represented as a linear combination of the eight real training-family deltas and applied to the base model for behavioral evaluation.

## Leakage controls

For every family, data is deterministically split into:

1. `capsule`: support I/O pairs visible to the compiler;
2. `train`: examples used only to train that family's direct LoRA teacher;
3. `hidden`: sealed behavioral evaluation prompts;
4. `semantic_hidden`: prompt-rephrased hidden variants.

The partitions use disjoint `(x,y)` inputs. Evaluation prompts contain neither capability ID nor rule coefficients. Entire family IDs `cap_08`–`cap_11` are absent from compiler fitting.

Every dataset manifest, family file, capability feature, adapter receipt, frozen compiler, and result object is content-bound by SHA-256 and exact base revision. Tamper/mismatch paths fail closed.

## Decision law

A valid GO requires all of the following after direct-LoRA learnability is established:

- four held-out families evaluated;
- compiled delta beats the strongest mandatory control by at least 0.02 on at least 3/4 families;
- median lift recovery >= 0.40 relative to direct LoRA;
- semantic-hidden variants preserve positive direction;
- worst-family regression stays within the configured bound;
- all mandatory controls are present.

If direct LoRA itself fails to gain at least 0.20 over base, the family set/model budget is declared `INCONCLUSIVE_DIRECT_LORA_PRECONDITION`; ACC is neither rescued nor killed from an unlearnable teacher target.

## CPU-only preparation and tests

From repository root:

```bash
python -m unittest -v research.weight_factory.agent07.test_b07_e0
python -m compileall -q research/weight_factory/agent07
python -m research.weight_factory.agent07.cli preflight
python -m research.weight_factory.agent07.cli prepare --artifact-dir artifacts/b07_e0
python -m research.weight_factory.agent07.cli train --artifact-dir artifacts/b07_e0 --family-set train --runner dry_run --device cpu
```

`dry_run` never produces fake adapters and cannot be used by `run-all`; it only validates orchestration.

## Real run when Manager-authorized GPU compute exists

Install a CUDA-compatible PyTorch build for the host first, then install the experiment requirements. Torch is intentionally not pinned in `requirements-b07e0.txt` because the correct wheel is CUDA/driver specific.

Every CUDA run must declare both its compute origin and the stable reference for the exact Manager authorization. Paid compute is represented explicitly as `paid_manager_authorized`; free/donated compute uses `free_or_donated`.

```bash
python -m pip install -r research/weight_factory/agent07/requirements-b07e0.txt
python -m research.weight_factory.agent07.cli run-all \
  --artifact-dir artifacts/b07_e0 \
  --device cuda:0 \
  --compute-origin paid_manager_authorized \
  --manager-authorization-ref P4-B07-03-A40-20260919
```

These fields are deliberate fail-closed guards and are written into training/evaluation receipts. They record external authorization; the code does not grant spending authority.

The real run performs:

1. deterministic data preparation;
2. eight train-family direct rank-2 LoRAs;
3. compiler fit using only those eight adapter deltas;
4. four held-out direct LoRAs solely for learnability/upper-anchor evaluation;
5. behavioral evaluation of base, compiled update, all five mandatory controls, an oracle-span diagnostic, and direct LoRA on hidden + semantic-hidden surfaces;
6. automatic GO/KILL decision;
7. automatic Plasticity Atlas follow-up specification if ACC is killed.

## Artifact tree

Expected important outputs under `artifacts/b07_e0/`:

- `dataset_manifest.json`
- `data/<family>/{capsule.json,train.jsonl,hidden.jsonl,semantic_hidden.jsonl}`
- `adapters/<family>/adapter_model.safetensors`
- `adapters/<family>/b07_train_receipt.json`
- `compiler.json`
- `fit_diagnostics.json`
- `behavioral_results.json`
- `decision.json`
- `apa_followup_spec.json` only on ACC kill

## Interpretation

- `GO_QWEN3_5_4B_REPLICATION`: B07-E0 found enough unseen-family behavioral signal to justify a stricter same-architecture 4B replication. It is not permission for 27B and is not a capability breakthrough claim.
- `KILL_ACC_PREPARE_APA`: stop ACC complexity escalation. Run the emitted Plasticity Atlas support-reuse falsifier next.
- `INCONCLUSIVE_DIRECT_LORA_PRECONDITION`: the teacher/budget failed to establish that the held-out micro-capabilities were learnable; repair the experimental substrate, not the compiler architecture.

## Scope and safety

This branch contains only the Worker-07 research harness. It does not modify production, canonical Manager policy, existing worker branches, model checkpoints, or `main`. No paid compute is authorized by this code.
