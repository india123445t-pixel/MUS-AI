# AQLEVON Evolution Loop V1

**Status:** IMPLEMENTATION BLUEPRINT  
**Date:** 2026-09-18

## Mission
Turn AQLEVON model development into a repeatable autonomous research loop that converts measured failures into verified training signal and retains only reproducible parameter improvements.

## Controller state
Each cycle stores:
- base/checkpoint SHA;
- benchmark snapshot hashes;
- defect clusters;
- selected training lane;
- source/data licenses;
- generated shard hashes;
- verifier versions;
- training config;
- trainable parameter list;
- resulting adapter/checkpoint hash;
- target metrics;
- global regressions;
- compute/time cost;
- keep/reject decision.

## Cycle
1. Evaluate untouched/current checkpoint.
2. Cluster failures by root cause.
3. Select highest-value defect cluster.
4. Generate candidate curriculum using one or more:
   - public admissible data;
   - open-weight Teacher Council;
   - Self-Verified Distillation;
   - SPADE-style executable self-play;
   - EnvFactory-style tool worlds;
   - adversarial mutation of prior failures.
5. Validate tasks and solutions.
6. Decontaminate against external/private release gates.
7. Train a specialist adapter/delta.
8. Evaluate target suite + global regression suite.
9. Reject unless Pareto-positive or explicitly justified.
10. Add successful specialist to Expert Bank.
11. Periodically test specialist composition.
12. Use merge-conflict failures to create CoMerge-style preference data.
13. Consolidate winning composition.
14. Re-evaluate full checkpoint.
15. Quantize and re-evaluate only after full-precision approval.
16. Feed new failures to next cycle.

## Automatic stop conditions
Stop/reject an experiment when:
- protected benchmark contamination found;
- license/provenance uncertain;
- loss/gradients numerically invalid;
- target score does not improve after defined budget;
- global regression exceeds threshold;
- latency/VRAM cost exceeds value budget;
- verifier integrity fails;
- checkpoint cannot reload reproducibly.

## Expert Bank
Initial expert IDs:
- coding_agentic
- tools_function_calling
- research_citations
- arabic_darija
- adaptive_reasoning
- factuality_calibration
- long_context_grounding
- long_horizon_state
- minimal_intervention
- multimodal_ui_document

Each expert has lineage to the exact same canonical base.

## Merge lab
For every selected expert subset run:
1. weighted average baseline;
2. task arithmetic;
3. TIES;
4. DARE/TIES;
5. conflict data extraction;
6. learned coefficient merge / CoMerge-style optimization;
7. short consolidation;
8. full evaluation.

Never keep a merge because it "looks plausible".

## Verifier bank
- code unit/integration tests;
- build/lint/type checks;
- exact math solvers;
- JSON/schema validators;
- tool execution checks;
- source/citation entailment checks;
- context chunk grounding verifier;
- plan constraint solver;
- security/scope verifier;
- Arabic/Darija native-review sample gate;
- learned verifier only when deterministic ground truth is unavailable.

## Experiment search policy
Use low-cost surrogate runs to search recipes, then confirm winners at 27B.

Do not infer 27B gains from small models without a confirmatory run.

## Output of every cycle
A machine-readable research record and one of:
- REJECTED
- DIAGNOSTIC
- SPECIALIST_ACCEPTED
- MERGE_CANDIDATE
- CONSOLIDATED_CANDIDATE
- PROMOTION_ELIGIBLE
- AQLEVON_RELEASE_EVIDENCE