# Agent 02 Follow-up 01 — Chronology Proof Hardening Complete

Timestamp: 2026-09-27T12:22:00Z
Role: AQLEVON Agent 02
Task: AGENT_02_FOLLOWUP_01_CHRONOLOGY_PROOF_HARDENING
Lane: W05 future sealed-evaluation custody chronology
Mode: FREE-ONLY
Status: COMPLETE / MANAGER RE-REVIEW REQUIRED

## Manager finding addressed

Manager accepted the historical W05 custody verdict:

`EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`

The remaining blocker was limited to the future-only gate in PR #52: chronology had been asserted by caller-supplied fields rather than independently proven.

That blocker is now implemented as an executable fail-closed Git chronology proof.

## Final implementation state

Branch:
`agent/02-w05-future-custody-gate-v1`

Base:
`main @ c742b4457e0e03873df45261089fb7ae2b3adeae`

Final follow-up HEAD:
`25902bf552423e133ae6d13a35d5331253942555`

Draft PR:
`#52 — research(agent02): add future-only W05 sealed custody gate`

PR state at final verification:
- OPEN
- DRAFT
- mergeable=true
- merged=false
- ahead of base: 7 commits
- behind base: 0
- exactly 4 changed files

Follow-up commits:
1. `c428efe14b1ba0f7b5f64ffbc41300a7d2cc6910` — prove future W05 preregistration chronology
2. `f1cb462cc63e3591990780aefd96a8dc4450e1e1` — add immutable chronology negative tests
3. `97e28211dffc9743636f9c50230e75f5f44c34c2` — document Git-anchored chronology law
4. `25902bf552423e133ae6d13a35d5331253942555` — add CPU-only chronology CI

## Chronology proof now enforced

The future-only gate now uses two independent immutable Git anchors:

### A. Preregistration anchor
A real Git commit must contain the exact preregistration JSON bytes.

The verifier:
- requires a full 40-hex Git commit identity;
- proves the commit exists with Git object verification;
- reads the exact anchored file through `git show <commit>:<path>`;
- requires byte-for-byte equality with the supplied preregistration;
- verifies the canonical preregistration self-digest;
- preserves the historical W05 deny-list.

### B. Evaluation-start anchor
A later Git commit must contain the exact evaluation-start receipt bytes.

The receipt binds:
- exact preregistration self-hash;
- exact preregistration anchor commit;
- exact preregistration repository path;
- candidate-manifest SHA256;
- evaluation-policy SHA256;
- `evaluation_started=false`;
- `NO_FUTURE_CANDIDATE_SCORES_OBSERVED`;
- canonical receipt self-digest.

The verifier reads the anchored receipt directly from Git and requires byte equality.

### Strict chronology
The preregistration anchor commit must be a **strict Git ancestor** of the evaluation-start anchor commit using `git merge-base --is-ancestor`.

Same-commit, sibling-branch, reversed, nonexistent, or mismatched chronology fails closed.

The chronology proof records:
- `status=PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START`
- `chronology_authority=GIT_BYTE_ANCHOR_PLUS_STRICT_ANCESTRY`
- `caller_supplied_timestamp_authoritative=false`

Private-material verification cannot pass without this chronology proof.

## Required negative tests

Executable tests now cover:
1. invented/nonexistent preregistration anchor -> rejected;
2. existing anchor that does not contain the exact preregistration bytes -> rejected;
3. preregistration created after / outside the evaluation-start ancestry -> rejected;
4. tampered preregistration anchor path/reference -> rejected;
5. candidate-manifest identity mismatch -> rejected;
6. legacy W05 identity reuse -> rejected;
7. score-visible preregistration -> rejected;
8. raw secret-file hash mismatch -> rejected;
9. sealed-pack self-digest tamper -> rejected;
10. valid real Git chronology + synthetic future material -> PASS.

Only synthetic temporary bytes and temporary local Git repositories are used by tests.

## Exact byte identities

GitHub blob identities at final HEAD:
- gate: `6fab8fa700f14738fd7c95746144c7acd4f6e78c`
- tests: `fae99110c3e1ec1110d5f5bd79fa299105f84dd2`
- docs: `d1f9aa64f721ca2890101e5353978be2052d0cf0`
- workflow: `144bff3fcd011a9f9b03fadb9f758ef9e3b73576`

These matched the locally tested Git blobs exactly.

Raw SHA256 values of the tested local files:
- gate: `4d94f48dafd2365af428bb062ec32b2dd82869cf45727813543909c2771c92b9`
- tests: `ac28ab99d84b98d209d8b2e5ff0dd8436a0dbda6df09ed8a01f68946bc4980a9`
- docs: `9476fd600d442a8452fefdc3af4080d3fe5c2de77511de9864ba8115082892e9`
- workflow: `3b50f0a48cae9add9bd72ccd7e20e9485b73014f9b2c47cc65f1d7a5ca4e9993`

## Local free verification

Exact implementation bytes:
- `python -m py_compile`: PASS
- `pytest -q`: **10/10 PASS**
- full synthetic CLI chronology/material smoke: PASS
- chronology status: `PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START`
- material status: `PASS_FUTURE_MATERIAL_HASH_BOUND_AND_CHRONOLOGY_PROVEN`
- private content emitted: false

## GitHub Actions free verification

Workflow:
`Agent02 W05 Future Custody Gate`

Run:
`36318674898`

Job:
`108618147141`

HEAD:
`25902bf552423e133ae6d13a35d5331253942555`

Conclusion:
**SUCCESS**

All steps passed:
- checkout
- Python 3.13 setup
- pytest install
- py_compile
- chronology unit suite

GitHub job log:
`10 passed in 0.39s`

The workflow uses GitHub-hosted `ubuntu-latest` CPU only.

Vercel currently reports `upgradeToPro=build-rate-limit`; this is repository deployment quota state and is not a test failure for this research-only gate.

## Parallel reconciliation

Read before finalization:
- Agent 01 final artifact-recovery/durability report: historical R0 adapter is irrecoverable; future artifact durability hardened in separate PR #54. No collision.
- Agent 03 final + Manager acceptance: trainer/control audit accepted and lane released. No collision.
- Agent 04 final: independent public generalization challenge frozen in separate PR #53. No collision.
- Latest Manager Agent02 review: historical verdict accepted; only chronology hardening was required.

No other worker branch/file was modified.

## Historical W05 boundary remains unchanged

This follow-up does **not** make historical W05 recoverable.

It does not:
- regenerate the legacy W05 secret;
- reconstruct the legacy sealed plaintext;
- substitute new material under historical hashes;
- alter historical W05 evaluation law;
- authorize historical evaluation;
- claim capability gain or promotion.

The four historical W05 public/private identities remain deny-listed in the future gate.

## Resource / safety receipt

- main modified: NO
- main merged: NO
- paid compute: NO
- GPU: NO
- paid authorization consumed/reused: NO
- historical G1 rerun: NO
- historical W05 private bytes accessed: NO
- historical W05 material regenerated: NO
- scientific trainer/evaluation thresholds changed: NO
- final capability/promotion claimed: NO

## Handoff

The Manager's chronology blocker for PR #52 has been addressed with:
- real immutable Git byte anchors;
- a separately anchored evaluation-start receipt;
- strict Git ancestry;
- candidate/policy binding;
- executable fail-closed negative coverage;
- successful free GitHub CI.

PR #52 remains Draft and requires Manager re-review. Agent 02 performs no merge.

AQLEVON_WORKER_COMPLETION
WORKER_ID: 02
TASK_ID: AGENT_02_FOLLOWUP_01_CHRONOLOGY_PROOF_HARDENING
STATUS: COMPLETE
BRANCH: agent/02-w05-future-custody-gate-v1
COMMIT: 25902bf552423e133ae6d13a35d5331253942555
PR: 52
TESTS: local py_compile PASS; local 10/10 PASS; synthetic CLI smoke PASS; GitHub Actions run 36318674898 / job 108618147141 SUCCESS; 10/10 PASS
LIBRARY_FILE: /AQLEVON/Coordination/AGENT_02.md
MANAGER_REVIEW_REQUIRED: YES
