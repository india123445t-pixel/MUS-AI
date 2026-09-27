# Manager Acceptance — Agent 01 27B Artifact Recovery / Durability

Timestamp: 2026-09-27
Reviewer: AQLEVON Manager
Agent: 01
Lane: 27B artifact recovery and durability
Decision: **ACCEPTED / LANE RELEASED**

## Historical recovery verdict accepted

**IRRECOVERABLE_AFTER_POD_DELETE**

The historical AQLEVON-27B-R0 adapter with SHA256:
`c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e`

is not currently recoverable as durable bytes from accessible sources.

The historical run receipt remains evidence that the adapter existed and passed save/reload hashing during run `36307917194`, but the actual adapter bytes were lost after the evidence archive remained only on ephemeral runner/pod storage and the pod was deleted.

Do not claim the original adapter can be delivered.

## Verified implementation

Branch:
`agent/01-27b-artifact-durability-20260927`

Verified HEAD:
`716a7d0f3a1ebf32c6576d08b4e6efa796bd8295`

Draft PR:
`#54`

Base:
`ops/runpod-control-v1`

State verified:
- OPEN
- DRAFT
- NOT MERGED
- mergeable=true

Free CI:
- workflow: `Agent 01 27B Artifact Durability Free Test`
- run: `36318285694`
- job: `108617048761`
- conclusion: **SUCCESS**
- runner: GitHub-hosted `ubuntu-latest`

## Manager code review

Accepted fail-closed ordering:

1. candidate evidence archive must be present;
2. archive must include manifest, receipt, adapter and config;
3. adapter byte SHA is verified against both manifest and training receipt;
4. save/reload hash proof must be true;
5. GPU pod is stopped after evidence egress so paid compute stops;
6. pod is retained while preservation runs;
7. `actions/upload-artifact@v4` uses `if-no-files-found: error`;
8. finalizer requires upload outcome success, artifact ID, artifact digest and SHA-verification marker;
9. pod deletion occurs only after those conditions pass;
10. failure leaves the pod stopped and not deleted.

The execution script contains no pod DELETE. Deletion authority is isolated to the post-upload finalizer.

## Scope integrity

- no scientific training constants changed;
- no evaluation thresholds changed;
- no main merge;
- no paid compute launched by Agent 01;
- no paid authorization reused;
- no historical G1 rerun;
- no W05 private material accessed or regenerated;
- no capability promotion claim.

## Remaining Manager consolidation requirement

Agent 01 artifact durability is accepted, but **no future paid 27B run is authorized yet**.

Before any future paid run, Manager must separately reconcile Agent 03's control-plane findings into the final control path:
- workflow-level single-flight serialization and/or durable pre-create lease;
- preserve exact runtime package-version receipt durably.

This is not a rejection of Agent 01's lane and does not require reopening its artifact-recovery mission.

## Final state

**AGENT_01_ACCEPTED_AND_RELEASED**

PR #54 remains draft/unmerged pending Manager consolidation. No merge authorization is implied.
