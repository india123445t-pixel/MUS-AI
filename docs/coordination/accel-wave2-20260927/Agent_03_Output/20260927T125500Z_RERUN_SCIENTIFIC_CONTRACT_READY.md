# Agent 03 Final — Wave 2 27B Reproducibility + Dual-Eval Contract

Timestamp: 2026-09-27T12:55:00Z
Role: AQLEVON Agent 03
Wave: accel-wave2-20260927
Lane: 27B scientific run contract + public evaluation reproducibility
Mode: FREE-ONLY
Status: COMPLETE / RERUN_SCIENTIFIC_CONTRACT_READY

## Verdict

**RERUN_SCIENTIFIC_CONTRACT_READY**

A machine-verifiable scientific contract now freezes the next 27B candidate's historical training recipe and preserves the historical public metric path exactly, while adding a second preregistered same-seed public evaluation path.

No historical metric was rewritten and no training constant was changed to improve observed results.

## Dedicated branch

`agent/03-wave2-27b-scientific-contract-v1`

Base:
`agent/03-27b-control-audit-20260927 @ 3518705224e0ce536aad7fc8b5cdaf77f7916f78`

Final verified head:
`4ddb508ea0dc99ab7e02588e19915915fc67976c`

Commits:
1. `72f872d926c4bde9d071f447511db0732aaf3556` — frozen machine-readable scientific contract
2. `c4596065741951fa9b4956146ffd0abe49f41a17` — contract verifier / paired-public planner + deterministic scorer
3. `5f2b45588c8037e8680046cb0b9a07d7471f218d` — CPU tests
4. `4ddb508ea0dc99ab7e02588e19915915fc67976c` — FREE-only GitHub Actions verification

Files added:
- `research/weight_factory/agent03/aqlevon_27b_rerun_scientific_contract_v1.json`
- `research/weight_factory/agent03/aqlevon_27b_rerun_contract_v1.py`
- `tests/test_aqlevon_27b_rerun_contract_v1.py`
- `.github/workflows/agent03-wave2-27b-rerun-contract.yml`

## Frozen contract identity

Canonical contract SHA256:

`484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`

Future run binding is explicitly fail-closed:
- contract self-hash must match;
- historical trainer/W02 Git blobs must match;
- frozen training constants must match;
- contract hash must be written into the future authorization-consumption/reservation record;
- the same contract hash must be written into the final run result receipt;
- all checks are required before provider create.

This is the exact hash Agent 01 should require in its future paid-run control path.

## Historical recipe frozen without modification

Historical source:
`4e3f1b03cfe77ac4355907ec692574f30d180252`

Frozen trainer:
- path: `research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py`
- Git blob: `9085e692d43110600e7bf214ffdab910f4821f1c`

Frozen public W02 generator/verifier:
- commit: `abb94ef134e2e97036b6959dbc9db4278d3736b6`
- Git blob: `bcdf1326a891dc082a6843f764c052f9192187b8`

Frozen scientific constants:
- base: `Qwen/Qwen3.8-27B`
- base revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- architecture: `Qwen3_5ForConditionalGeneration`
- precision: BF16
- seed: 1701
- sequence cap: 1024
- thinking: disabled
- LoRA r=4, alpha=8, dropout=0, bias=none
- q/v self-attention targets only
- expected target modules: 32
- expected trainable parameters: 1,507,328
- AdamW
- LR: 1e-5
- minimum LR: 1e-6
- weight decay: 0.05
- gradient clip: 1.0
- cosine per-step schedule
- max optimizer updates: 672
- early-stop check every 112 updates
- training indices: 4..19
- 14 frozen families
- prompt perturbations: 0,1,2
- expected training rows: 672
- prompt loss mask: -100
- target: compact oracle JSON + EOS

## Historical public metric path preserved

The contract keeps the old public path exactly for R0 comparability:
- dev indices: 0,1
- shadow indices: 2,3
- prompt perturbation: 0
- sampling: temperature 0.7, top-p 0.8, top-k 20
- max new tokens: 256
- one sampled return
- historical label-derived seed formula preserved
- historical nonregression PASS rule preserved

The contract explicitly labels this path as historical/comparability evidence with the known seed confound. It is not silently repaired or substituted.

## New paired public evaluation — preregistered before future candidate answers

The additional paired path uses the same public W02 objective verifier and the same dev/shadow task derivation, but freezes common seeds that are identical for base and candidate.

Common seeds:
- `1701`
- `271828`

Task structure:
- 14 public families
- dev indices 0,1 = 28 tasks
- shadow indices 2,3 = 28 tasks
- total unique tasks/system = 56
- 2 seeds/task
- attempts/system = 112
- systems = base + candidate
- exact total attempts = 224

Frozen task-catalog SHA256:

`1ec78429ca5dc681361be281f94d945c0671f16328c983bd7494480ec4205388`

Frozen exact system/task/seed matrix SHA256:

`60e2653de2aaee2dae86414d5e69f5adf5dd2973a67056774ae7db3209f403a8`

Sampling stays aligned with the historical public path:
- do_sample=true
- temperature=0.7
- top_p=0.8
- top_k=20
- max_new_tokens=256
- num_return_sequences=1
- use_cache=true
- thinking disabled

The same exact seed is required for base and candidate for each task.

## Retry / completeness rules frozen

Model sampling:
- exactly one dispatched model attempt per system/task/seed;
- no retry after model dispatch;
- no retry for malformed output;
- no retry for verifier failure;
- no retry if dispatch state is UNKNOWN;
- UNKNOWN dispatch state aborts the evaluation fail-closed.

Only pre-dispatch setup may be retried once, and only with proof that no model request was sent.

Completeness gate:
- missing task/seed pair: reject;
- duplicate pair: reject;
- extra pair: reject;
- substituted/wrong seed: reject;
- unequal base/candidate seed sets: reject.

## Paired evidence thresholds frozen

The new paired path is additional evidence and does not redefine historical R0.

PASS requires:
- exact complete matrix;
- candidate dev successes - base dev successes >= 0;
- candidate shadow successes - base shadow successes >= 0;
- candidate total successes - base total successes >= 0.

Strict total gain is reported separately but is not retrospectively inserted into the historical R0 PASS rule.

## Private/sealed boundary

Evaluation source allow-list contains exactly one source:
the pinned public W02 generator/verifier blob above.

Contract verification reports:
- `private_or_sealed_source_count = 0`
- `future_private_evaluation_authority = false`

No historical W05 material is referenced as an evaluation source, accessed, regenerated, or substituted.

This paired public path does not replace Agent 04's structural-generalization challenge and does not replace any future properly preregistered private W05-style evaluation.

## FREE CI evidence

Workflow:
`Agent03 Wave2 27B Scientific Contract`

Run:
`36320384194`

Job:
`108622960765`

Head:
`4ddb508ea0dc99ab7e02588e19915915fc67976c`

Conclusion:
**SUCCESS**

All steps passed:
- exact historical commits available;
- Python syntax checks for new contract tooling;
- exact historical trainer + W02 syntax checks;
- frozen contract verification;
- CPU unit tests;
- preregistered no-inference execution-plan generation.

CPU tests:
**5/5 PASS**

Verified output:
- `training_recipe_match=true`
- `source_blobs_match=true`
- `same_seed_pairing=true`
- `private_or_sealed_source_count=0`
- exact contract hash matched
- exact task catalog hash matched
- exact pair matrix hash matched
- generated plan contained exactly 224 rows

Tests prove:
1. historical recipe/constants and source blobs match contract;
2. base/candidate seed sets are identical for all 56 tasks;
3. task/seed drop is rejected;
4. duplicate task/seed is rejected;
5. substituted seed/extra pair is rejected;
6. paired deterministic scoring enforces frozen nonregression thresholds;
7. generated execution plan contains no oracle program;
8. only the allowed public source derives prompts.

## Repository-wide workflow side effect

As on the previous Agent 03 branch, three legacy workflows with broad push configuration reported failures on Agent 03 pushes:
- `runpod-runtime-probe.yml`
- `aqlevon-runpod-capacity-scan.yml`
- `runpod-retry18h-diagnose.yml`

The latest inspected failures returned **zero jobs**. No provider mutation body ran and no paid resource was launched from those failed runs.

The Agent 03 workflow itself used only GitHub-hosted CPU runners.

## Concurrent-lane reconciliation

Agent 01 control-plane branch moved independently to:
`d024534c1a3a72592546d2015e6ed1249944795e`

Agent 01 is actively implementing the single-flight reservation/runtime-version/preservation lane. Agent 03 did not modify those control-plane files.

Integration requirement for Agent 01:
require scientific contract hash
`484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`
before any future provider-create action, and preserve it in reservation/consumption + final result receipt.

Agent 04 remains owner of the structurally different frozen generalization challenge. Agent 03 did not alter PR #53 challenge prompts/seeds/scoring.

## Resource / safety receipt

- main changed: NO
- main merged: NO
- paid GPU: NO
- provider pod/job created: NO
- paid inference: NO
- historical authorization reused: NO
- historical G1 rerun: NO
- historical W05 material accessed/regenerated: NO
- historical training recipe changed: NO
- historical R0 metrics rewritten: NO
- final capability promotion claimed: NO

## Handoff

Agent 03 lane is released.

Before any future paid 27B execution, Agent 01/Manager should hard-bind the exact contract hash above into the control plane and fail closed if the contract, source blobs, or frozen trainer constants do not validate.

Completion verdict:

**RERUN_SCIENTIFIC_CONTRACT_READY**
