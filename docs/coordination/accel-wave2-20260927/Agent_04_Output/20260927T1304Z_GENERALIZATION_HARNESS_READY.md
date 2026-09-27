# Agent 04 Final — Wave 2 Frozen Generalization Inference Harness

Timestamp: 2026-09-27T13:04Z
Role: AQLEVON Agent 04
Wave: accel-wave2-20260927
Lane: frozen structural-generalization result ingestion + deterministic scoring
Mode: FREE-ONLY
Status: COMPLETE / GENERALIZATION_HARNESS_READY

## Verdict

**GENERALIZATION_HARNESS_READY**

The already accepted PR #53 public structural-generalization challenge is now paired with a no-GPU execution manifest/template, exact 128-attempt result matrix, fail-closed result-ingestion gate, deterministic frozen scorer, edge-case tests, and FREE GitHub Actions verification.

No inference was run. No prompt, task, seed, retry rule, scoring metric, threshold, or frozen challenge identity was changed.

## Frozen dependency preserved exactly

Stacked base:
`agent/04-27b-generalization-audit-pr-20260927 @ 061ef205664aa7af27708c2ee27741a6cf246667`

Frozen challenge identities:
- generator SHA256: `06bb54774830918bc1f9b3254186f139b442b334e7e7ac328100db437e39ad83`
- logical pack SHA256: `10e049fa86fb034023bfa7e93a9dc0cfa58b3cff35718ef32b26533a18ff2b3b`
- freeze manifest SHA256: `5d1e848c5609874d0f1e184f285f4202538fab4a0456828e008f77ba9914c7fd`
- base: `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- systems: `canonical_base`, `candidate_adapter_on_same_base`
- common seeds: `27092026, 27092027, 27092028, 27092029`
- tasks: 16
- attempts/system: 64
- exact total rows: 128

The Wave 2 branch modifies none of the PR #53 frozen challenge files.

## Dedicated Wave 2 branch

Branch:
`agent/04-wave2-generalization-harness-20260927`

Final verified head:
`e04ff782c242a2f29c7110b3a9d72737118e08ae`

Commits:
1. `c95145cc48478387fae9dda32ec43686067aed5a` — add result-ingestion/scoring harness, tests, template, CPU workflow
2. `e04ff782c242a2f29c7110b3a9d72737118e08ae` — normalize the template file ending only; no scientific field changed

Diff against frozen PR #53 head:
- ahead by 2 commits
- behind by 0
- exactly 4 files added
- no frozen challenge file modified

Added files:
1. `.github/workflows/agent04-wave2-generalization-harness.yml`
2. `research/weight_factory/agent04/aqlevon_27b_public_generalization_execution_manifest_template_v1.json`
3. `research/weight_factory/agent04/aqlevon_27b_public_generalization_result_harness_v1.py`
4. `research/weight_factory/agent04/test_aqlevon_27b_public_generalization_result_harness_v1.py`

## Result-ingestion contract

The harness creates and requires exactly:
- 16 frozen task IDs
- 4 frozen common seeds
- 2 frozen systems
- 128 unique `(system, task_id, seed)` rows

Each row is bound to:
- execution-manifest SHA256
- frozen challenge-pack SHA256
- frozen freeze-manifest SHA256
- exact system/model identity SHA256
- raw model output string

The candidate manifest requires:
- base repo/revision match the frozen base
- candidate adapter SHA256
- adapter-state SHA256
- candidate-manifest SHA256
- self-hashed execution manifest

## Fail-closed ingestion behavior

Scoring is rejected before metric computation for:
- missing pair
- duplicate pair
- extra/substituted pair
- wrong model/system identity
- wrong challenge hash
- wrong freeze hash
- wrong manifest binding
- malformed result-envelope schema
- non-string raw output

A model response that is a string but fails the frozen JSON output contract is **not retried**. It is counted as one failed attempt, matching `no_retry_on_failed_parse=true`.

## Frozen deterministic scoring implemented

The scorer computes the already frozen metrics without external statistical libraries:

Primary:
`candidate_total_successes - base_total_successes` over 64 attempts/system.

Paired evidence:
- discordant candidate-wins count
- discordant base-wins count
- one-sided exact sign/binomial p-value
- exact rational numerator/denominator plus decimal representation

Secondary:
- robust tasks/system
- robust = at least 3 successes among the 4 frozen seeds

Frozen support condition:
- delta > 0
- one-sided exact p <= 0.05

Interpretation boundary remains unchanged:
this is additional public structural-generalization evidence only; it is not W05 sealed evaluation and cannot independently authorize final promotion.

## No-GPU execution manifest/template

The `prepare` command accepts only candidate identity hashes and emits:
1. self-hashed future execution manifest;
2. empty 128-row result skeleton.

It does not perform inference and contains no oracle programs in the result matrix.

Future executor fills only the `raw_output` field for each already-bound row and then calls `score`.

## FREE CI evidence

Final workflow:
`Agent04 Wave2 Generalization Harness`

Final run:
`36320785988`

Job:
`108624078713`

Head:
`e04ff782c242a2f29c7110b3a9d72737118e08ae`

Conclusion:
**SUCCESS**

All steps passed:
- compile frozen challenge + Wave 2 harness
- frozen challenge tests
- Wave 2 harness edge-case tests
- no-GPU manifest preparation smoke test

Combined tests:
**16/16 PASS**
- 5 existing frozen challenge tests
- 11 new Wave 2 harness tests

Wave 2 tests cover:
- exact 128 unique pair matrix
- deterministic perfect-candidate metric math
- missing pair rejection
- duplicate pair rejection
- extra pair rejection
- wrong model identity rejection
- wrong challenge/freeze hash rejection
- malformed envelope rejection
- malformed model text = failed attempt with no retry
- frozen template tamper rejection
- wrong candidate-base rejection
- exact binomial edge math

Smoke proof:
`AGENT04_WAVE2_HARNESS_PREPARE_PASS e685c7eca78879eba23df2e2ba239d261e3691b64b38e176f7d35c4ec2e33e58 128`

## Transparent first-CI failure and correction

First run:
`36320431597`

Result:
FAIL during Wave 2 tests.

Root cause:
the newly added JSON execution template ended with the literal two characters `\n` after the closing JSON object, producing `JSONDecodeError: Extra data`.

The frozen challenge, scorer design, metrics, task set, seeds, and thresholds were not the cause.

Fix:
commit `e04ff782c242a2f29c7110b3a9d72737118e08ae` changed only the file ending to a real newline.

The next exact-byte GitHub run passed 16/16.

## Draft PR

Stacked Draft PR:
`#55 — research(agent04): add frozen generalization execution/scoring harness`

Live checked state:
- OPEN
- DRAFT
- mergeable=true
- merged=false
- base: `agent/04-27b-generalization-audit-pr-20260927 @ 061ef205...`
- head: `e04ff782...`
- 2 commits
- exactly 4 changed files

PR #55 is deliberately stacked on PR #53 rather than main so it contains only the Wave 2 harness delta.

No merge was performed.

## Concurrent-worker reconciliation

Latest Wave 2 reports read before closure:

Agent 02:
- verdict `FUTURE_W05_HARD_BINDING_READY`
- branch/head `agent/02-w05-future-custody-gate-v1 @ 1af3828480f6c1d28106e088dd42b6567f356378`
- future private W05 hard-binding only
- no collision with Agent 04 public structural-generalization harness

Agent 03:
- verdict `RERUN_SCIENTIFIC_CONTRACT_READY`
- scientific contract SHA256 `484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`
- separate historical/public W02 reproducibility path
- explicitly preserves Agent 04's structurally different PR #53 challenge
- no collision

No Agent 01 Wave 2 output was present in the shared Wave 2 folder at the last pre-report scan. Agent 01 owns future paid-run control-plane consolidation and is not modified by Agent 04.

## Future execution boundary

This harness validates the result envelope and deterministic scoring after outputs are supplied. It does not itself prove that a future inference runtime actually honored temperature/top-p/top-k/max tokens/seed/one-dispatch/no-retry settings.

Therefore any future authorized inference executor must independently emit a runtime receipt binding the actual dispatch settings and candidate identity to this frozen manifest. No post-result prompt/seed/task/retry/scoring/threshold changes are allowed.

## Resource / safety receipt

- main changed: NO
- main merged: NO
- paid GPU: NO
- provider pod/job: NO
- paid inference/API: NO
- historical paid authorization reused: NO
- historical G1 rerun: NO
- W05 private material accessed/regenerated: NO
- frozen PR #53 challenge changed: NO
- historical training recipe changed: NO
- final capability/promotion claimed: NO

## Handoff

Agent 04 Wave 2 lane is released.

Manager should review PR #55 after/with its dependency PR #53. Actual structural-generalization inference remains a future separately authorized action; this worker intentionally stopped before it.

Completion verdict:

**GENERALIZATION_HARNESS_READY**

AQLEVON_WORKER_COMPLETION
WORKER_ID: 04
TASK_ID: WAVE2_FROZEN_GENERALIZATION_INFERENCE_HARNESS
STATUS: COMPLETE
BRANCH: agent/04-wave2-generalization-harness-20260927
COMMIT: e04ff782c242a2f29c7110b3a9d72737118e08ae
PR: 55
TESTS: GitHub Actions run 36320785988 / job 108624078713 SUCCESS; 16/16 PASS
BASE_DEPENDENCY: PR #53 @ 061ef205664aa7af27708c2ee27741a6cf246667
MANAGER_REVIEW_REQUIRED: YES
