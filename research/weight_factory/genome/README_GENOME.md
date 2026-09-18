# AQLEVON Capability Genome V1

This directory converts the Frontier Weight Strategy into fail-closed metadata and admission rules.

Files:
- `source_registry_v2.json`: source/model/data policy. Default deny.
- `genome_manifest_v1.json`: canonical base, adapter target policy, capability genes, promotion contract.
- `merge_tournament_v1.json`: staged merge candidates from simple baselines to 2026 conflict/evolution methods.
- `genome_gate.py`: validates immutable project invariants and promotion metadata.
- `test_genome_gate.py`: unit tests for legal/provenance/promotion gates.

This is **not** a trained checkpoint. It is the control layer that prevents unverified community weights, incompatible tensors, hosted-model distillation, or contaminated data from entering AQLEVON's weight factory.

Run:
```bash
python genome_gate.py
python -m unittest -v test_genome_gate.py
```

## G0.1 — Merge Safety + Expert Mesh

Additional fail-closed controls:
- `merge_safety_policy_v2.json`: exact Qwen3.8 base/revision, hybrid-topology coverage classes, safe PEFT merge families, blocked Qwen3_5 mergekit path, rank-pattern restrictions, and integrity/promotion evidence.
- `merge_safety_gate.py`: validates adapter/merge candidate manifests before any promotion claim.
- `test_merge_safety_gate.py`: regression tests for wrong base revision, incomplete DeltaNet coverage, unsafe rank-pattern merges, blocked mergekit usage, unproven QLoRA, missing delta proof, and forbidden scopes.
- `expert_mesh_v1.json`: research contract for static and dynamic capability-gene serving.

Current toolchain decisions:
- First real 27B training proof: BF16 LoRA preferred; QLoRA is experimental until AQLEVON measures the regression.
- First merge backend: PEFT-native composition with mandatory save/reload and numerical delta-integrity checks.
- `mergekit` is not trusted for Qwen3_5/Qwen3.8 until exact architecture round-trip support is independently demonstrated.
- Dynamic LoRA load/unload is control-plane/admin-only. Untrusted users may never supply runtime adapter paths.
- A successful merge command is not evidence: the merged artifact must differ numerically from base in the expected modules and reload successfully.

Run G0/G0.1 gates:
```bash
python genome_gate.py
python -m unittest -v test_genome_gate.py
python -m unittest -v test_merge_safety_gate.py
```
