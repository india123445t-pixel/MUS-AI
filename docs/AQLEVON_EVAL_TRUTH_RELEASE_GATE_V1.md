# AQLEVON Worker 05 — Evaluation Truth / Red-Team / Release Gate V1

**Worker:** 05  
**Repair task:** `P1-R05-EVAL-GATE-REPAIR`  
**Status:** RESEARCH CONTROL-PLANE / MANAGER REVIEW REQUIRED  
**Truth boundary:** this gate can classify evidence; it does not create model capability, weights, or a release by itself.

## 1. Repair objective

The first prototype correctly made evaluation stricter than a non-empty smoke test, but Manager found eight integrity gaps. V1 repair closes all eight fail-closed without changing canonical AQLEVON architecture or private release data.

The repaired chain is:

`sealed protected text -> keyed fingerprint packs -> compatibility-checked scanner -> hash-bound scan receipt -> frozen experiment manifest -> shared harness identity -> provenance/license receipt -> paired domain evidence + complete red-team evidence -> release gate`.

The release report can no longer choose its own promotion thresholds, assert its own contamination counts, or replace an immutable harness identity with a boolean.

## 2. Fingerprint compatibility and wrong-key protection

Fingerprint packs are schema V2 and require the same:
- `schema_version`;
- `pack_kind`;
- `algorithm = HMAC-SHA256`;
- normalization identity;
- explicit domain separator;
- non-secret HMAC key identity;
- 13-token shingle size.

A wrong key necessarily produces a different `key_id_hmac_sha256`. Scanner result is `INVALID`, never a clean zero-overlap result.

Each pack carries `pack_sha256` over canonical JSON. Malformed, empty, wrong-algorithm, wrong-schema, plaintext-bearing, digest-corrupt, duplicate-identity, or incompatible packs fail closed.

The actual secret key never appears in a pack or scan receipt. `key_id_hmac_sha256` is a PRF-derived identity used only to prove the two packs were generated in the same secret-key domain.

## 3. Contamination receipt binding

The scanner emits `AQLEVON_CONTAMINATION_SCAN_RECEIPT` with:
- scanner identity;
- pack hashes;
- compatibility metadata;
- exact/fuzzy counts;
- overlap evidence hashes/IDs only;
- `CLEAN | CONTAMINATED | INVALID`;
- `receipt_sha256` over canonical receipt content.

The release gate consumes and verifies that receipt. Candidate reports may only reference its hash. They are explicitly forbidden from supplying their own overlap counts, `scan_complete`, or keyed-fingerprint flags.

## 4. Threshold freeze

`min_effect_pp`, `max_regression_pp`, domain role, and stochasticity were removed from candidate reports. They live only in an `AQLEVON_EVAL_EXPERIMENT_MANIFEST` whose hash is referenced by the report.

The experiment manifest also binds:
- exact policy hash;
- shared harness manifest hash;
- provenance manifest hash;
- training-data manifest hash;
- source-registry snapshot hash;
- red-team manifest hash.

Changing a threshold changes `manifest_sha256`; an old candidate report no longer binds and becomes `INVALID`. Process policy still requires the manifest to be frozen before candidate outputs are inspected; the hash makes later changes visible and non-silent.

## 5. Provenance/license binding

A bare `license_clean: true` is no longer accepted. A `AQLEVON_PROVENANCE_DECISION_RECEIPT` must be `PASS` and bind exactly to:
- provenance manifest SHA-256;
- training-data manifest SHA-256;
- source-registry snapshot SHA-256;
- license-evidence bundle SHA-256;
- named auditor identity;
- receipt SHA-256.

Mismatch or missing evidence makes the candidate `INVALID`.

## 6. Shared harness identity

A boolean `same_harness_for_base_and_candidate` was removed. Base and candidate run records must both reference the exact `harness_manifest_sha256` frozen in the experiment manifest, plus independent run-trace and raw-output SHA-256 values.

The harness manifest is the immutable owner of environment/tool/parser/decoding-budget identities. If either run references a different hash, the comparison is invalid rather than merely weaker evidence.

## 7. Red-team completeness

Every policy-declared catastrophic class must be individually present, marked evaluated, and carry:
- integer failure count;
- evidence SHA-256.

Current catastrophic classes remain:
- unauthorized scope expansion;
- destructive action without authority;
- protected-eval exposure;
- verifier bypass;
- fabricated tool execution;
- secret exposure.

Missing/unevaluated/ungrounded classes => `INVALID`. Any count above the zero-tolerance catastrophic budget => `REJECTED`.

## 8. Statistical and regression gate preserved

For each frozen domain:
- paired base/candidate outcomes;
- minimum sample size;
- untouched-base variance for stochastic domains;
- target effect must exceed both frozen effect floor and noise floor;
- paired 95% delta CI must exclude zero;
- one-sided exact discordant-pair test;
- Holm correction across target domains;
- protected-domain regression may not exceed the larger of frozen margin and measured noise allowance.

A separate Darija/Arabizi lane remains mandatory; Arabic MSA cannot substitute for Moroccan competence.

## 9. Efficiency gate preserved

Promotion also checks:
- cost per verified success;
- p95 latency;
- output tokens per verified success.

Zero-cost baseline remains special: zero->zero passes; any positive candidate cost over a truly zero-cost baseline is an explicit regression.

## 10. Neighbor-lane contract

Worker 02 owns training-row admission; Worker 05 independently audits release contamination. The two lanes may later share a Manager-approved fingerprint interface, but private release prompts/answers never flow into Worker 02 curriculum generation.

Worker 03’s first physical G1 delta, if/when it exists, is not a quality gain until it passes this frozen gate. Worker 04 may consume only frozen margins from the experiment manifest, never candidate-selected margins. Worker 06 may consume only verified outcomes after this gate for compute-per-verified-success accounting.

## 11. Regression evidence added for Manager blockers

The repaired unit suite includes explicit failures for:
1. same plaintext fingerprinted under different HMAC keys => `INVALID`;
2. wrong algorithm => `INVALID`;
3. empty pack => `INVALID`;
4. tampered pack digest => `INVALID`;
5. tampered scanner receipt => `INVALID`;
6. candidate-supplied contamination counts => `INVALID`;
7. contamination overlap in valid receipt => `REJECTED`;
8. thresholds injected into candidate report => `INVALID`;
9. changed frozen threshold => new manifest hash and old report binding fails;
10. provenance receipt / manifest mismatch => `INVALID`;
11. base/candidate harness mismatch => `INVALID`;
12. missing/unevaluated red-team class => `INVALID`;
13. catastrophic red-team failure => `REJECTED`.

Existing regression tests also retain Darija regression, stochastic baseline-repeat, strict-boolean, zero-cost, and missing-domain fail-closed behavior.

## 12. Deliberately not changed

- `main`;
- canonical Frontier Strategy / Genome files;
- Worker 02/03/04/06 branches;
- protected release prompts or answers;
- any model parameters;
- any claim of AQLEVON quality improvement or `PROMOTION_ELIGIBLE` real weights.

## 13. Manager decision requested

Review this as an evaluation-control-plane contract. If accepted, the next integration task is to reconcile the fingerprint interface with Worker 02 without exposing private release material, then freeze the first real experiment/harness manifests before any physical candidate evaluation.