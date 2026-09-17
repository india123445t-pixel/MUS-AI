# KITE AI Frozen A–F Authority Responsibility Map

This map documents ownership of the frozen logical authority responsibilities. It is not a new runtime enum, service, persona, or Round-G extension.

## 1. Task & Contract Controller
- `lib/kite/kernel.js`: `buildTaskContract`, `buildRouteDecision`, acceptance criteria and controller-owned contract metadata.
- `lib/kite/frozen-foundations.js` (`decideControllerAction`): deterministic Round-C READ / ASK / ASSUME / BLOCK / WAIT / REFUSE / ESCALATE / NO_OP information-and-authority decision law.
- `lib/kite/state-machines.js`: Task lifecycle/outcome transition guards.

## 2. Canonical State & Audit
- Prepared schema: `supabase/migrations/20260915_kite_bos_v1.sql` for Request, PrincipalBinding, Task, TaskContract, DurableConstraint, ActionIntent, Permit, ActionAttempt, Receipt, Artifact, EvidenceBinding, VerificationState, Claim, Response, AuditEvent and ConfirmationRecord.
- `lib/kite/context.js`: exact authority-critical manifest and compaction integrity; context remains derived/non-authoritative.
- `lib/kite/frozen-foundations.js` (`recoverCanonicalRuntime`): canonical-first crash recovery interface that never promotes narrative/chat history into authority.
- Migration remains intentionally unapplied in this recovery task.

## 3. Model Gateway
- `lib/kite/providers.js`: provider routing, self-hosted KITE adapter, zero-cost OpenRouter guard and sanitized diagnostic classification.
- Model output remains proposal/data, never authorization, receipt or verification truth.

## 4. Authority & Policy Gate
- `lib/kite/authority.js`: canonical resource identity, DurableConstraint selection/evaluation, exact Permit issuance and pre-dispatch recheck.
- `lib/kite/tool-registry.js`: immutable/versioned ToolSpec and CapabilitySpec contracts.
- `lib/kite/frozen-foundations.js` (`createCredentialBroker`): server-only credential references and late transport-boundary injection.

## 5. Action Executor & Receipt Collector
- `lib/kite/frozen-foundations.js` (`dispatchRegisteredAction`, reconciliation/retry/compensation guards): registered-adapter/default-deny execution envelope, durable ActionAttempt ownership interface, duplicate-dispatch fencing, UNKNOWN reconciliation rules and separately authorized compensation.
- `lib/kite/receipts.js`: exact ActionAttempt/Intent/Permit receipt binding; Receipt does not prove world state.
- Arbitrary real-world production mutations remain unwired.

## 6. Outcome Truth & Response Governor
- `lib/kite/state-machines.js`: VerificationState lifecycle/result separation.
- `lib/kite/kernel.js`: formal verification adjudication; model agreement cannot mint VERIFIED.
- `lib/kite/response-governor.js`: deterministic fail-transparent response qualification when evidence/execution/postconditions are absent.

## Offline 7. Isolated Evaluation Harness
- `lib/kite/frozen-foundations.js` (`runIsolatedEvaluation` and deterministic fixture/result-store helpers): zero-cost, no-network, credential-free fixture/deterministic-adapter harness with isolated result storage and first-exposure contamination controls.
- It cannot write production learning/canonical state and is intentionally separate from the existing live benchmark UI.

## Deliberate unresolved blocker: external authenticated break-glass
The repository currently has user authentication but no applied BOS canonical authority store and no externally authenticated administrator/principal channel bound to exact Permit issuance. A genuine narrow break-glass cannot be implemented without faking the external authority dependency. It therefore remains blocked rather than model-triggered or simulated.
