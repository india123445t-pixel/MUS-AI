# AQLEVON Capability Genome V2

This directory converts the Frontier Weight Strategy into fail-closed metadata and admission rules.

## Active control files

- `source_registry_v3.json`: default-deny model/data/recipe registry. Separates trainable sources, recipe-only research, conditional sources, quarantine and denied hosted training harvest.
- `genome_manifest_v2.json`: two-scale foundry manifest: 27B laboratory base + future 2.4T-A95B frontier transfer target, plus capability genes R0-A through R0-L.
- `capability_acquisition_matrix_v2.json`: maps each capability to teacher-specific branches, recipes, training modes and objective verifiers.
- `self_evolution_policy_v1.json`: challenger/solver/verifier admission policy for R0-L self-evolution.
- `merge_safety_policy_v2.json`: exact Qwen3.8 base/revision, hybrid-topology coverage classes, safe PEFT merge families, rank-pattern restrictions and required numerical integrity evidence.
- `merge_tournament_v1.json`: staged static consolidation tournament.
- `expert_mesh_v1.json`: trusted runtime specialist-selection research contract.
- `genome_gate.py`: fail-closed registry/genome/promotion validator.
- `merge_safety_gate.py`: fail-closed adapter/merge candidate validator.
- `test_genome_gate.py`, `test_merge_safety_gate.py`: regression gates.

Legacy V1/V2 metadata remains for lineage only and is not the active source of truth when V3/V2 files above exist.

## Two-scale foundry

### Laboratory / cost-efficient line
`Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

Use this line to discover and falsify:
- training data recipes;
- teacher choice;
- reward functions;
- verifier design;
- self-evolution curriculum;
- merge/interference methods;
- hyperparameter ranges.

### Frontier transfer line
`Qwen/Qwen3.8-2.4T-A95B`

This is a future frontier-scale transfer target, **not** a tensor-compatible destination for 27B LoRAs. Only validated recipes/data/rewards/curricula/verifiers may transfer. Frontier topology, license compliance, baseline and compute budget must be revalidated before any training.

Law: **cheap discovery, expensive confirmation**.

## Capability Genome

AQLEVON does not create a monolithic training soup first. Each capability is trained and evaluated as an independently traceable gene.

Current gene set:
- R0-A coding/agentic
- R0-B tools/function calling
- R0-C research/citations
- R0-D Arabic/Moroccan Darija
- R0-E adaptive reasoning
- R0-F factuality/calibration
- R0-G long-horizon state
- R0-H minimal intervention
- R0-I multi-teacher/adversarial
- R0-J long-context evidence
- R0-K environment world model
- R0-L self-evolving curriculum

No gene becomes merge-eligible merely because training completed. Promotion requires reproducible target gain, bounded global regression, exact lineage, artifact hash, license/provenance/contamination pass and reload proof.

## R0-L Self-Evolution

Self-evolution is objective-verifier gated, not free-form self-training.

Roles:
1. Challenger proposes tasks near the current capability frontier.
2. Solver attempts them.
3. Deterministic or externally grounded Verifier decides admission.

Required protections:
- objective verifier;
- solvability/difficulty band;
- novelty scan;
- benchmark-distance/decontamination scan;
- replayable environment where applicable;
- untouched regression holdout.

Pure LLM-judge approval, hidden-chain-of-thought reward, benchmark-near-duplicate generation and unverifiable examples are rejected.

Current recipe references:
- Agent0: permissive recipe reference.
- R-Zero: research reference until licensing is explicitly cleared.
- Dr. Zero: concept/research only under current non-commercial code terms.
- EvoGM: permissive evolutionary merge-search recipe.

## Community-weight law

A public checkpoint is not a donor merely because it scores well.

Direct admission requires:
- exact compatible ancestral base/revision;
- complete license chain;
- dataset provenance;
- teacher provenance;
- topology/target coverage;
- contamination scan;
- reproducible artifact;
- measurable standalone gain and regression vector.

Incomplete-provenance community releases are quarantined and may be used only as recipe/evidence references.

## Merge Safety + Expert Mesh

Current toolchain decisions:
- First real 27B parameter-change proof: BF16 LoRA preferred.
- QLoRA remains experimental until AQLEVON measures its quality regression.
- Primary merge backend: PEFT-native composition with mandatory save/reload and numerical delta-integrity checks.
- `mergekit` is not trusted as the production Qwen3_5/Qwen3.8 merge backend until exact architecture round-trip support is independently demonstrated.
- Dynamic LoRA load/unload is admin/control-plane only.
- A successful merge command is not evidence: the artifact must differ numerically from base in expected modules and reload successfully.
- Search methods such as EvoGM / mergekit-evolve are research optimizers only and may tune on private development data, never release benchmarks.

## Gates

Run:
```bash
python genome_gate.py
python -m unittest -v test_genome_gate.py
python -m unittest -v test_merge_safety_gate.py
```

Expected current G0.2 evidence:
- `GENOME_GATE_PASS sources=19 genes=12`
- genome tests: 11/11 PASS
- merge-safety tests: must remain PASS before merge research

## Truth boundary

These controls do **not** constitute a trained AQLEVON checkpoint.

The first genuine AQLEVON weight artifact exists only after:
1. parameters change in a real training run;
2. the adapter/checkpoint is saved;
3. it reloads;
4. non-zero expected parameter deltas are numerically proven;
5. artifact SHA256 and exact lineage are recorded;
6. frozen evaluation and regression gates pass.
