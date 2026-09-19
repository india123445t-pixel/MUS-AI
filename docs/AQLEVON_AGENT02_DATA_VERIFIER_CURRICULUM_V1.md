# AQLEVON Agent 02 — Data + Verifier + Curriculum Architecture V1

**Worker:** 02  
**Task:** P1-A02-DATA-VERIFIERS  
**Status:** RESEARCH / IMPLEMENTATION-READY — MANAGER REVIEW REQUIRED  
**Scope:** Training-signal quality, not release scoring. This artifact does not alter main, model weights, protected evaluation data, or canonical strategy files.

## 1. Core finding

AQLEVON already has strong source-level guardrails: default-deny registries, protected-eval exclusions, TeacherCouncil verification, adversarial seed generation, and provenance-aware training-mix construction. The missing layer is instance-level admission.

A dataset can be legally admissible while an individual row is duplicated, benchmark-contaminated, unverifiable, already mastered, too hard for the current curriculum stage, dialectally poor, or backed by a verifier that cannot detect its claimed failure. Therefore “dataset allowed” must never mean “all rows enter training.”

## 2. Proposed training-signal architecture

Frozen protected-eval manifest (hashes only)
→ source/license/provenance gate
→ immutable instance identity + content hash
→ exact + semantic/near deduplication
→ protected-eval contamination scan
→ solvability / hard-verifier gate
→ student baseline attempts and learning-zone estimate
→ defect classification
→ failure-neighbor / adversarial generation
→ legal local/open-weight teacher only where needed
→ independent objective verifier + fault-injection proof
→ Arabic/Darija/Arabizi quality gate where applicable
→ ADMIT / QUARANTINE / DENY
→ curriculum scheduler → hashed training shard.

The low-cost strategy is failure-conditioned verified curriculum, not maximum data volume.

## 3. Admission semantics

**DENY:** protected-eval record/overlap, disallowed source/license/provenance, mutable/unbound revision, malformed cryptographic identity, or incomplete protected-holdout scan.

**QUARANTINE:** potentially useful but incomplete: no qualified hard verifier, verifier failed fault injection, duplicate/near-duplicate, insufficient baseline attempts, task currently too easy/too hard, or missing dialect-quality audit.

**ADMIT:** only when all mandatory source, contamination, verifier, learnability, deduplication and language-quality gates pass.

## 4. Learnable-information filter

Initial research heuristic in the attached policy:
- at least 4 baseline attempts;
- quarantine success below 5% as currently too hard/unstable;
- quarantine above 85% as likely already mastered / low marginal information;
- retain the middle band for curriculum experiments.

These are not release thresholds. They must be tuned by measured learning-progress ablations. A stronger scheduler should eventually optimize expected verified learning progress per GPU-second rather than fixed difficulty bands.

## 5. Verifier hierarchy

| Capability | Preferred verifier | Secondary checks | Never sole truth |
|---|---|---|---|
| Math | symbolic/equivalence solver, exact/numeric tolerance | independent recomputation, domain/unit checks | LLM judge |
| Science | executable calculation or structured reference fact | citation-span + quantity/unit checks | majority vote |
| Coding | isolated unit/integration tests, compiler/build, hidden property tests | minimal-diff/static constraints, timeout/resource checks | “looks correct” judge |
| Tools | schema + deterministic postcondition/state transition | arguments, idempotency, retry/rollback | executor SUCCESS |
| Research/citations | exact source version/span + proposition/number/date/polarity checks | calibrated semantic entailment advisory | citation presence/source count |
| Long context | keyed retrieval/state constraints with distractors | exact evidence location + multi-hop consistency | answer similarity |
| Arabic MSA | same objective domain verifier | language/grammar audit | generic English judge |
| Darija/Arabizi/code-switch | domain verifier + native/approved dialect audit | transliteration/locale invariants | synthetic fluency score |
| Structured output | schema/parser + field constraints | canonicalization | free-form judge |
| Agent recovery | final world-state/postcondition | fault injection + safe retry/rollback | HTTP 200/no exception |

Every consequential verifier must state its target failure mode, observation, blind spots/shared dependencies, and negative/fault-injection test. A verifier that cannot fail on an injected target defect is verification theatre.

## 6. Curriculum loop

1. Freeze baseline and protected-evaluation manifests.
2. Mine failures into defect classes, not benchmark names.
3. Select a high-value defect with a deterministic verifier.
4. Generate neighbors around the exact failure while preserving an objective solution.
5. Validate solvability before the student sees the task.
6. Run student baseline multiple times where stochasticity matters.
7. Drop mastered tasks; quarantine tasks beyond the current learning frontier.
8. Route only unresolved useful tasks to legally admissible local/open-weight teachers.
9. Verify teacher output independently; teacher reputation or consensus is never truth.
10. Admit only rows passing source, contamination, verification, dedup and quality gates.
11. Train a small specialist shard and measure verified gain per GPU-second.
12. Generate harder neighbors from residual failures and repeat.

## 7. Concrete source candidates

| Source | Evidence | Agent-02 status | Required before use |
|---|---|---|---|
| Team-ACE/ToolACE | Apache-2.0; 11.3k synthetic English/Chinese tool rows | CANDIDATE | immutable revision/hash; BFCL/private tool overlap scan; schema/postcondition re-verification; exact+semantic dedup |
| osunlp/QUEST-SFT-Data-Objective | MIT; synthetic deep-research SFT; card says raw website content is not included | CANDIDATE WITH CONDITIONS | immutable hash; source-policy scan; isolate QUEST evaluation splits; citation/answer re-verification |
| open-r1/OpenR1-Math-220k | Apache-2.0; DeepSeek-R1 traces over NuminaMath 1.5; Math-Verify for most rows and LLM judge for a subset | QUARANTINE / TRANSFORM | upstream problem provenance; final-answer re-verification; avoid blindly importing long traces; math holdout scan |
| nvidia/OpenCodeReasoning-2 | CC-BY-4.0 wrapper; card says underlying datasets retain their own terms | QUARANTINE UPSTREAM | per-source license allowlist; problem decontamination; compile/tests; dedup; attribution |
| Lyte/Moroccan-Darija-Instruct-573K | CC-BY-4.0; gated; 573,175 synthetic Darija QA pairs | QUARANTINE QUALITY+ACCESS | explicit access acceptance; immutable hash; native Moroccan audit; synthetic-artifact filtering; private Darija scan; attribution |
| CoEvolve | Apache-2.0; failure signals drive validated task synthesis | RECIPE CANDIDATE | reproduce in small sandbox under AQLEVON verifier/firewall |
| Agent0 | Apache-2.0; curriculum/executor co-evolution with tools | RECIPE CANDIDATE | same; curriculum-agent score never equals truth |
| Absolute Zero | self-generated tasks validated/answered with executable rewards | RESEARCH CONCEPT | exact code/license audit per AQLEVON registry; sandbox hardening; decontamination |

License labels are engineering admission metadata, not legal advice. Pin and re-audit the exact revision before a real training run.

## 8. Contamination + dedup strategy

Use layers, not one detector:
1. exact record/content hashes;
2. normalized duplicate clusters;
3. protected-eval N-gram hashes with no raw protected answers copied into training artifacts;
4. repo/issue identity for coding tasks;
5. semantic-near-duplicate scan for paraphrase/translation leakage;
6. provenance/source lineage comparison;
7. Agent-05 independent decontamination audit before promotion.

EleutherAI lm-evaluation-harness documents a 13-gram detector as a useful exact-overlap baseline. It is not complete for paraphrases, translations, short items or embedded fragments. SemDeDup supports an additional representation-level redundancy layer.

## 9. Arabic / Moroccan lanes

Keep at least separate tags for msa, darija, arabizi, darija_fr_codeswitch and msa_darija_codeswitch. Do not collapse them into one “Arabic” bucket.

For synthetic Darija/Arabizi/code-switch rows, admission requires language-quality audit in addition to the domain verifier. Private linguistic minimal pairs stay under Agent 05’s protected holdout boundary.

High-value generated families include:
- natural Darija tool calls while schema keys remain exact;
- Darija↔MSA reformulation preserving facts/tone;
- Arabizi normalization with ambiguity;
- Moroccan French code-switch preserving entities/numbers/dates;
- coding/research tasks instructed in Darija while executable/citation truth stays objective.

## 10. Cross-agent boundary

Agent 02 owns training-signal admission and curriculum construction. Agent 05 owns release/promotion evaluation, statistical confidence, private unseen tasks and final decontamination judgment.

Agent 02 emits source/provenance hashes, contamination evidence, verifier evidence, baseline success band, language audit, and reason-coded admission decisions. Agent 05 independently verifies no protected material entered training and determines whether post-training gains survive the frozen harness.

Agent 02 must never consume private evaluation answers during curriculum generation.

## 11. Assumption challenged

Rejected assumption: an allow-listed dataset plus one passing teacher answer is training-ready.

Stronger alternative: two-stage admission:
1. source-level legal/provenance eligibility;
2. instance-level contamination + verifier + learnability + dedup + language-quality gate.

A second assumption is challenged: fixed data mixtures are not necessarily the best use of limited compute. Failure-conditioned verified generation (CoEvolve/Agent0/AZR-style) is a higher-leverage hypothesis because it spends teacher/GPU budget near demonstrated defects. AQLEVON must still validate this by verified gain per GPU-second.

## 12. Minimal branch implementation

New research-only files:
- research/weight_factory/agent02/training_signal_gate_v1.py
- research/weight_factory/agent02/training_signal_policy_v1.json
- research/weight_factory/agent02/test_training_signal_gate_v1.py

Properties:
- Python standard library only;
- fail closed;
- immutable source identity + SHA-256;
- hash-only protected holdout manifest;
- N-gram contamination detection without committing protected answers;
- source/license/provenance gates;
- semantic duplicate-score hook;
- verifier fault-injection requirement;
- learned-semantic-only verification cannot admit;
- baseline learning-zone filter;
- synthetic Darija/Arabizi/code-switch audit gate;
- explicit ADMIT/QUARANTINE/DENY reason codes.

It does not execute untrusted code. Executable coding/tool verifiers must run in a separate sandbox and feed evidence into this gate.

## 13. External sources consulted

- https://huggingface.co/datasets/Team-ACE/ToolACE
- https://huggingface.co/datasets/osunlp/QUEST-SFT-Data-Objective
- https://huggingface.co/datasets/open-r1/OpenR1-Math-220k
- https://huggingface.co/datasets/nvidia/OpenCodeReasoning-2
- https://huggingface.co/datasets/Lyte/Moroccan-Darija-Instruct-573K
- https://github.com/StoneHanaMori/CoEvolve
- https://github.com/aiming-lab/Agent0
- https://arxiv.org/abs/2505.03335
- https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/decontamination.md
- https://arxiv.org/abs/2303.09540

## 14. Cheap experiment / ablation

Local unit suite: 15/15 PASS.

Seeded seven-record gate ablation:
- ADMIT: 1 clean record;
- QUARANTINE: 3 (already mastered, verifier not fault-tested, synthetic Darija missing language audit);
- DENY: 3 (uncleared license, protected-manifest overlap, explicit protected-eval hit).

Recommended next physical experiment before large ingestion: 1k-record admission ablation in coding/tools/math/research/Darija, comparing source-level-only vs instance-level gate vs instance-level+failure-neighbor generation. Measure false verifier acceptance under injected defects, protected-overlap rejection, duplicate reduction, difficulty distribution, and post-training verified gain per GPU-second on a small surrogate.


## 15. P1 Repair Wave — Manager blockers closed

Task: `P1-R02-DATA-GATE-REPAIR`.

### Trusted registry identity and source-kind separation
The row no longer self-authorizes training eligibility. `gate` now requires an explicit `--source-registry` input. The registry must be default-deny, structurally valid, and is hashed canonically. Every row carries that registry SHA-256 and must match an existing registry entry by `source.id`; its claimed `kind` and `admission` must match the trusted entry.

Recipe/code/model-recipe kinds are explicitly non-trainable. `recipe_allow` is forbidden from the trainable admission allowlist and is denied even if attached to a dataset-shaped entry. This preserves the distinction between permission to study/reuse a recipe and permission to ingest training rows.

### Canonical per-record content binding
A separate `record_content_sha256` now binds `record_id + prompt + answer/response` under a versioned domain (`AQLEVON_TRAINING_ROW_CONTENT_V1`). Unicode is NFKC-normalized and newlines are normalized; case and semantically relevant whitespace are preserved. Any later prompt/answer mutation produces `DENY: record_content_sha256_mismatch`.

This hash is intentionally separate from `source.content_sha256`, which remains source/artifact provenance evidence rather than proof that a particular training row is unchanged.

### Manifest and schema hardening
Protected-manifest validation now requires:
- positive integer `ngram_size`;
- non-negative integer `record_count`;
- structurally valid SHA-256 hex digests for manifest and all hash entries;
- no duplicate hash entries;
- recomputed manifest digest match;
- policy/manifest N-gram-size agreement.

Policy, registry, record-count, contamination-count, semantic-score, and baseline-count type errors fail closed. A malformed policy/config file at CLI level causes every parseable input row to be written to DENY and returns non-zero status; no ADMIT output is possible.

### Learnability truth boundary
The 5%-85% band remains a configurable `research_heuristic`, not a release threshold, canonical fact, or model-quality claim.

### Repair regression evidence
The repaired suite contains 38 tests. Manager-blocker regressions include:
- recipe_allow/code_recipe rejection;
- recipe kind rejection even with admission=`allow`;
- trusted registry ID/kind/admission/digest binding;
- prompt and answer tamper detection;
- malformed/zero/string N-gram manifest rejection;
- invalid protected hash rejection;
- policy type failure → controlled DENY;
- malformed policy JSON through CLI → denied row + non-zero exit.

Local repair result: **38/38 PASS**; Python compile PASS; policy JSON parse PASS.

No model training, parameter change, new checkpoint, or capability improvement is claimed by this repair.
