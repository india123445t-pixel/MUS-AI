# AQLEVON AI — Behavioral Operating System v1 Implementation

This patch translates the frozen AQLEVON AI research architecture into an implementable runtime kernel without pretending the underlying model weights have changed.

## What becomes real immediately

### Chat cognition kernel
The public `/api/chat` route now constructs a controller-owned TaskContract before model generation. It composes domain protocols, decides Fast/Normal/High routing, sanitizes obvious secret material, and keeps formal verification separate from model agreement.

### AQLEVON personality
The provider model is treated as an implementation detail. A dedicated persona contract gives AQLEVON AI its own restrained, analytical, non-sycophantic voice. It must not impersonate ChatGPT/Claude/Gemini or inherit provider-specific personality habits.

### Truth boundaries
- model answer != evidence;
- second-model agreement != VERIFIED;
- citation presence != entailment;
- receipt != world-state postcondition;
- current claims without current evidence remain INCONCLUSIVE rather than silently “verified”.

### Memory/context boundary
The patch does not introduce general personal memory. Conversation history is a derived view, secrets are redacted before external-provider exposure, and project authority is intended to live in canonical state rather than summaries.

### Domain protocols
Software, research, math, data/statistics, science, external communication, and operations protocols are declarative controller rules. They can narrow actions and strengthen verification requirements but cannot grant authority or create new truth objects.

### Tool/authority framework
The patch now includes executable, dependency-free kernel modules for the frozen authority design:
- `tool-registry.js`: immutable ToolSpec/CapabilitySpec registry semantics;
- `authority.js`: canonical resource identity, ActionIntent binding, DurableConstraint evaluation, Permit issuance, and pre-dispatch recheck;
- `state-machines.js`: frozen Task/ActionAttempt/Verification transition guards;
- `receipts.js`: exact ActionAttempt/Intent/Permit receipt binding without confusing Receipt with Verification;
- `context.js`: non-authoritative model context views and compaction integrity checks;
- `response-governor.js`: deterministic transparency when current evidence, real execution, or external postcondition evidence is missing.

The database migration includes the 16 frozen logical runtime objects plus trusted ToolSpec/CapabilitySpec registries. Permit remains the only exact executable runtime authority. Live arbitrary side effects are intentionally not wired until a real Credential Broker, registered ToolSpecs, and provider-specific executors exist.

## Why live action execution is not enabled by default

The current repository exposes model-provider calls and chat/evaluation APIs, but does not yet contain a registered external ToolSpec/Permit/Executor/Credential-Broker pipeline for arbitrary side effects. Enabling external actions directly from model text would violate the architecture we spent the research phase defining.

The safe next activation step is:
1. apply the BOS schema to the actual AQLEVON AI Supabase project;
2. register a small allowlisted ToolSpec set;
3. add a server-only Credential Broker;
4. create exact Permit issuance and ActionAttempt dispatch fencing;
5. add postcondition VerificationState checks;
6. only then expose consequential actions.

## Current database connector limitation found during implementation

The Supabase connector available in this ChatGPT session exposes only project `qkoscgdegnqcypkjrefn` (`mysindbad's Projec`), not the AQLEVON AI project previously identified in research. The migration is therefore prepared but intentionally not executed against that unrelated project.

## Current GitHub connector limitation found during implementation

The GitHub repository `india123445t-pixel/AQLEVON-AI` is readable, but the connected GitHub app reports `push: false`. ChatGPT plugin permission was raised to full access at the user's explicit request, but OAuth/repository write scope remains read-only. The patch is therefore generated and tested locally, ready to apply as soon as the GitHub connector is reconnected with write access.

## Validation

Run:

```bash
npm run bos:check
npm run bos:test
npm run build
```

`bos:check` passes for all BOS modules and both Next.js route files.

`bos:test` currently passes **28/28 tests** and intentionally checks architectural invariants such as:
- current claims cannot be formally verified without current evidence;
- provider/model agreement alone does not mint VERIFIED;
- software tasks require real execution evidence before claiming execution;
- multi-domain tasks compose;
- obvious secrets are redacted before external model-provider exposure;
- repository prompt injection cannot become authority merely because it appears in context;
- exact Permit parameters cannot drift before dispatch;
- a changed DurableConstraint set invalidates stale dispatch authority;
- hidden write effects disqualify a claimed pure READ path;
- ActionReceipt never becomes VerificationState truth;
- illegal state-machine rewrites are rejected;
- context compaction cannot drop UNKNOWN/blockers/authority-critical state;
- AQLEVON personality stays provider-independent while controller law remains above personality;
- response governance adds deterministic evidence/execution qualifications instead of trusting model wording.

## Research-to-code map

| Frozen concept | Code / schema |
|---|---|
| TaskContract | `lib/aqlevon/kernel.js`, `aqlevon_task_contracts` |
| DurableConstraint | migration `aqlevon_durable_constraints` |
| ActionIntent | `aqlevon_action_intents` |
| Permit | `aqlevon_permits` |
| ConfirmationRecord | `aqlevon_confirmation_records` |
| ActionAttempt | `aqlevon_action_attempts` |
| ActionReceipt | `aqlevon_action_receipts` |
| Artifact | `aqlevon_artifacts` |
| EvidenceBinding | `aqlevon_evidence_bindings` |
| VerificationState | `aqlevon_verification_states` |
| Claim | `aqlevon_claims` |
| Response | `aqlevon_responses` |
| AuditEvent | `aqlevon_audit_events` |
| ToolSpec / CapabilitySpec | `lib/aqlevon/tool-registry.js` + trusted registry tables, not runtime authority tokens |
| Permit / authority gate | `lib/aqlevon/authority.js`, `aqlevon_permits` |
| State machines | `lib/aqlevon/state-machines.js` |
| Receipt binding | `lib/aqlevon/receipts.js` |
| Context/compaction | `lib/aqlevon/context.js` |
| Response Governor | `lib/aqlevon/response-governor.js` |
| Domain protocols | `lib/aqlevon/domain-protocols.js` |
| Personality | `lib/aqlevon/persona.js` |
| Secret boundary | `lib/aqlevon/security.js` |
| Provider fallback | `lib/aqlevon/providers.js` |

## Explicit non-claims

This patch does **not** claim:
- AQLEVON has new trained weights;
- model-generated verification is formal truth;
- external side-effect tools are production-ready before the broker/permit/executor path is connected;
- the migration has been applied to the actual AQLEVON Supabase project;
- the GitHub repository has already been modified while the connector remains read-only.

Those boundaries are deliberate rather than missing work.


## Validation environment limitation

A full `next build` could not be executed inside the current sandbox because outbound DNS/package-registry access is unavailable and the npm cache does not contain `@supabase/supabase-js`. This is recorded as **not tested**, not as a successful build. Syntax checks for every changed JavaScript module/route and the 28 dependency-free BOS regression tests do pass.
