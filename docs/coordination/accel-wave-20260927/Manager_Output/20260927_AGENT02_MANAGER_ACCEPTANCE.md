# Manager Acceptance — Agent 02 W05 Custody + Chronology Follow-up

Timestamp: 2026-09-27
Reviewer: AQLEVON Manager
Agent: 02
Decision: **ACCEPTED / LANE RELEASED**

## Historical custody verdict

Accepted and unchanged:

`EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`

The original historical W05 private secret/plaintext remain cryptographically identified but are not accessible through a verified durable custody path.

No regeneration, reconstruction, or substitution is authorized.

## Follow-up 01 verified live

Branch:
`agent/02-w05-future-custody-gate-v1`

HEAD:
`25902bf552423e133ae6d13a35d5331253942555`

Draft PR:
`#52 — research(agent02): add future-only W05 sealed custody gate`

Verified state:
- OPEN
- DRAFT
- NOT MERGED
- base main unchanged

GitHub Actions:
- workflow: `Agent02 W05 Future Custody Gate`
- run: `36318674898`
- job: `108618147141`
- conclusion: **SUCCESS**
- runner: GitHub-hosted `ubuntu-latest`

Unit suite: **10/10 PASS**.

## Chronology blocker resolved

The previous Manager blocker at head `99273202...` is resolved.

The gate now verifies:
1. exact preregistration bytes exist in a real Git commit;
2. exact evaluation-start receipt bytes exist in a later real Git commit;
3. the start receipt binds the preregistration hash, anchor commit/path, candidate-manifest SHA and evaluation-policy SHA;
4. the preregistration commit is a **strict ancestor** of the evaluation-start commit;
5. missing, mismatched, tampered, sibling/reversed/late anchors fail closed;
6. legacy W05 identities remain deny-listed;
7. private material verification is only reached after chronology PASS in the CLI flow.

Caller-supplied timestamps are not treated as chronology authority.

## Negative coverage verified

Executable tests include:
- nonexistent preregistration anchor;
- exact-byte mismatch at anchor;
- late/sibling preregistration chronology;
- tampered anchor path/reference;
- candidate-manifest mismatch;
- legacy W05 identity rejection;
- score-visible preregistration rejection;
- secret hash mismatch;
- sealed-pack self-digest tamper;
- valid synthetic Git chronology success.

## Important future integration boundary

This PR provides the accepted fail-closed chronology/custody gate.

Any future W05-style evaluator must integrate this gate as a **hard pre-scoring dependency**. Documentation alone must never be treated as sufficient authorization to score.

Before any future candidate scoring:
- preregistration anchor must already exist;
- evaluation-start receipt must already exist in a strict descendant commit;
- chronology gate must PASS;
- candidate/policy identity must remain bound;
- only then may the evaluator access/use future private evaluation material.

No future evaluator is enabled by this acceptance, so this integration boundary does not block Agent 02 lane completion.

## Safety/resource state

- main merged: NO
- paid compute: NO
- GPU: NO
- old authorization reused: NO
- G1 rerun: NO
- historical W05 private bytes accessed: NO
- historical W05 regenerated: NO
- capability promotion claimed: NO

**Final Manager state: AGENT_02_ACCEPTED_AND_RELEASED**
