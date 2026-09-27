# AQLEVON W05 Future Evaluator Hard Binding V1

Status: Wave 2 implementation / Manager review required  
Owner lane: Agent 02  
Scope: future W05-style evaluation only  
Historical W05: remains `EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`

## Purpose

This wrapper turns the already accepted future custody/chronology gate from PR #52 into a mandatory pre-scoring dependency.

The scorer callback is not invoked until every prerequisite passes.

## Mandatory order

The only supported orchestration order is:

1. Verify the preregistration Git commit exists.
2. Verify the exact preregistration bytes at the frozen commit/path.
3. Verify the evaluation-start Git commit exists.
4. Verify the exact evaluation-start receipt bytes at its frozen commit/path.
5. Verify the preregistration commit is a strict ancestor of the evaluation-start commit.
6. Verify the evaluation-start receipt binds the expected candidate-manifest SHA256.
7. Verify the evaluation-start receipt binds the expected evaluation-policy SHA256.
8. Verify the future secret-file SHA256.
9. Verify the future sealed-plaintext raw SHA256.
10. Verify the sealed pack canonical self-digest and preregistered pack identity.
11. Only then emit a metadata-only pre-score authorization.
12. Invoke the scorer exactly once. There is no retry/fallback scorer path.

Any failure before step 12 raises and exits before scorer invocation.

## Interface

Implementation:

`research/evaluation/w05_future_evaluator_hard_binding_v1.py`

Primary function:

`run_future_w05_evaluator(..., scorer=callable)`

The scorer receives only a metadata-only pre-score authorization containing:
- preregistration SHA256;
- chronology proof SHA256;
- custody/material verification SHA256;
- candidate-manifest SHA256;
- evaluation-policy SHA256;
- authority/safety flags.

It does not receive:
- the secret-file path;
- the sealed-plaintext path;
- secret bytes;
- private task bodies;
- private prompts/answers/canaries.

## Fail-closed rules

Scoring is unreachable when any of these fail:
- nonexistent Git anchor;
- byte mismatch at either anchor;
- same/late/sibling chronology;
- candidate-manifest mismatch;
- evaluation-policy mismatch;
- private material hash mismatch;
- sealed-pack validation failure;
- legacy W05 identity boundary.

The wrapper also requires:
- `private_content_emitted=false`;
- `authoritative_for_legacy_w05=false`.

It emits:
- `authoritative_for_legacy_w05=false`;
- `authoritative_for_capability_gain=false`.

Passing this wrapper does not itself establish capability gain or promotion.

## Synthetic-only tests

`research/evaluation/test_w05_future_evaluator_hard_binding_v1.py`

The suite proves the mock scorer is never invoked for:
- nonexistent anchor;
- preregistration byte mismatch;
- evaluation-start byte mismatch;
- late/sibling chronology;
- candidate mismatch;
- evaluation-policy mismatch;
- material hash mismatch.

The positive test proves:
- chronology PASS;
- material/custody PASS;
- policy and candidate bindings match;
- scorer invoked exactly once;
- scorer authorization contains no private paths/content.

Only temporary synthetic bytes and temporary Git repositories are used.

## Historical isolation

This wrapper does not:
- open, regenerate, infer, reconstruct, or substitute historical W05 private material;
- remove the legacy identity deny-list;
- rewrite historical W05 chronology;
- alter the 27B training recipe;
- authorize a paid run;
- merge to main.

It is future-only orchestration glue.
