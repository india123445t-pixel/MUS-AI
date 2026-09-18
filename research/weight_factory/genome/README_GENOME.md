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