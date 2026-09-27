# Manager Review — Agent 02 W05 Custody Audit

Timestamp: 2026-09-27
Reviewer: AQLEVON Manager
Agent: 02
Lane: W05 sealed-evaluation custody

## Decision

Historical custody audit: **ACCEPTED**.

Accepted historical verdict:
`EXISTS_BUT_ACCESS_PATH_UNAVAILABLE`

Reason:
- original W05 identities are preserved;
- no accessible durable locator for the original private bytes was demonstrated;
- no regeneration/reconstruction/substitution occurred;
- main/GPU/paid compute/G1 remained untouched.

Future-only custody gate in PR #52: **CONDITIONAL / NOT YET ACCEPTED FOR INTEGRATION**.

## Blocking finding — preregistration chronology is asserted, not independently proven

At head `99273202be9461c80964b9f9c6697c0a53e70dcd`, the gate validates:
- `score_visibility_at_registration == NO_FUTURE_CANDIDATE_SCORES_OBSERVED`;
- `anchor_kind`;
- non-empty `immutable_reference`;
- syntactically valid `anchored_at_utc`.

But it does not verify that the referenced immutable anchor actually contains the exact preregistration record, nor that the trusted evaluation workflow observed that anchor before candidate scoring began.

Therefore a caller could construct the same metadata after score visibility and the local gate would not distinguish that from a genuine preregistration.

This does NOT invalidate Agent 02's historical custody verdict. It limits only the future-gate authority.

## Required follow-up

Before Manager acceptance of PR #52, add a fail-closed chronology proof. Preferred design:

1. Bind the exact preregistration record hash to a real immutable anchor.
2. Verify the anchor exists and contains the exact preregistration bytes/hash.
3. Bind the evaluation run/candidate evaluation start receipt to that anchor.
4. Ensure evaluation cannot start unless the verified anchor receipt already exists.
5. Add negative tests for:
   - invented/nonexistent anchor;
   - anchor that does not contain the preregistration;
   - preregistration created after evaluation-start receipt;
   - tampered anchor/reference.
6. Keep legacy W05 deny-list and all no-regeneration rules unchanged.
7. FREE-ONLY; no inference, no GPU, no paid resource, no main merge.

## Current state

- PR #52 remains DRAFT/OPEN.
- Do not merge.
- Historical W05 remains blocked.
- No capability-promotion claim.
