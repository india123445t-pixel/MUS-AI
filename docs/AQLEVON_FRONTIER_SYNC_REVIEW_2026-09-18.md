# AQLEVON Frontier Sync Review — 2026-09-18

Status: REVIEWED / RESEARCH-CONTROL-PLANE SYNC ONLY

## Scope
This branch mirrors the Library-only Frontier V6 / Genome v5-era control-plane files identified by the recovery handoff. It does not modify application runtime, production routing, model weights, or protected evaluation data.

Base GitHub main: `de2e576eec72581efb5f8e0910d2a8ea2e96b8c0`.

## Evidence before sync
- Live GitHub main verified at `de2e576eec72581efb5f8e0910d2a8ea2e96b8c0`.
- Open pull requests: none at review start.
- Vercel Production `dpl_52SvBbq8AWvkGnQG6HogGa45pqWx`: READY and tied to the same Git SHA.
- Production root returned HTTP 200 with the AQLEVON Workspace.
- Commons health returned HTTP 200 with `edge_reachable=true`, `active_workers=0`, `available=false`.
- No NVIDIA GPU was visible in the current execution environment, so G1/R0-A was not attempted.
- No new AQLEVON trained checkpoint is claimed.

## Files mirrored
- `docs/AQLEVON_FRONTIER_WEIGHT_STRATEGY_V6.md`
- `docs/AQLEVON_FRONTIER_METHOD_REGISTRY_V6.json`
- `research/weight_factory/genome/source_registry_v4.json`
- `research/weight_factory/genome/source_registry_v5.json`
- `research/weight_factory/genome/source_registry_v5_additions.json`
- `research/weight_factory/genome/merge_safety_policy_v3.json`
- `research/weight_factory/genome/interference_atlas.py`
- `research/weight_factory/genome/test_interference_atlas.py`
- `research/weight_factory/genome/cross_arch_distillation_policy_v1.json`
- `research/weight_factory/genome/evolutionary_merge_policy_v1.json`
- `research/weight_factory/genome/adaptive_reasoning_policy_v1.json`
- `research/weight_factory/genome/test_frontier_policies.py`

## Local validation
The current Library Genome set was materialized together and executed with:

`python -m unittest -v test_genome_gate.py test_merge_safety_gate.py test_interference_atlas.py test_frontier_policies.py`

Result: **26/26 PASS**.

JSON parsing and Python compilation for the sync candidates also passed.

## Registry / policy audit
- `source_registry_v5.json` remains default-deny.
- Hosted OpenAI / Anthropic / Gemini entries remain denied for competitive-model training harvest under the recorded policy.
- The only unconditional ALLOW in the audited v5 registry is the canonical Qwen3.8-27B base entry.
- `source_registry_v5_additions.json` contains `evogm_recipe_refresh` as a gated recipe (`recipe_allow_after_commit_pin`), not an unconditional source admission.
- Research recipes with unpinned code/data licensing remain research-only or quarantined.

## V2 divergence — intentionally not overwritten
The Library `AQLEVON_FRONTIER_WEIGHT_STRATEGY_V2.md` (Capability Forge) and the current GitHub V2 are materially divergent and each contains accepted research material absent from the other. This sync therefore does **not** overwrite GitHub V2 and does **not** consolidate V2 + V6 into V7. That requires a dedicated preservation/consolidation review so no accepted constraints are lost.

## Truth boundary
This sync proves control-plane consistency only. It does not prove model intelligence, frontier performance, a trained checkpoint, or public AQLEVON inference availability.
