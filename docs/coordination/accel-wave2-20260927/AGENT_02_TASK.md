# AGENT 02 — FUTURE W05 EVALUATOR HARD-BINDING OWNER

Mode: FREE-ONLY.
Exclusive mutation lane: future W05 evaluation orchestration/harness only.

Mission:
Turn the accepted future chronology/custody gate from PR #52 into a hard pre-scoring dependency for a future evaluator, using synthetic-only tests.

Required:
1. Do not touch or reconstruct historical W05 private material.
2. Build a future-only evaluator wrapper/harness that refuses to score unless:
   - preregistration Git anchor verifies byte-for-byte;
   - evaluation-start anchor verifies;
   - strict ancestry passes;
   - candidate manifest and evaluation policy hashes match;
   - custody/material gate passes.
3. Scoring code must be unreachable on chronology/custody failure.
4. Add negative tests proving a mock scorer is never invoked for:
   - nonexistent anchor;
   - byte mismatch;
   - late/sibling chronology;
   - candidate mismatch;
   - material hash mismatch.
5. Add positive synthetic test proving exactly one scorer invocation after all gates PASS.
6. No inference, no GPU, no real secret material.
7. Do not merge main.

Completion verdict:
FUTURE_W05_HARD_BINDING_READY
or
FUTURE_W05_HARD_BINDING_BLOCKED_<reason>
