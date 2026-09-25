# AQLEVON UI / Owner Core / Child Lab Readiness Audit — 2026-09-25

Status: PREVIEW / DRAFT ONLY. Do not merge or promote without owner authorization.

## Scope
Audit target:
- public Workspace application
- Owner Core /admin
- Child Lab /admin/child-lab
- sovereign AQLEVON inference/readiness paths
- browser-local features that could overclaim server/external execution

Excluded:
- Worker 03 / P4 training lane
- paid GPU
- model-weight training
- main merge
- production cutover

## Verified architectural truths

### Public application
- / and catch-all workspace routes use one WorkspaceRoot.
- public inference is AQLEVON-only.
- unified browser chat calls /api/commons/chat.
- /api/commons/chat first calls sovereign /api/chat; Commons is only a fallback when primary returns 503.
- no external model provider fallback exists.
- send/work controls fail closed while inference is unavailable.
- Web Search / Deep Research are unavailable until a real adapter is connected.
- Automations are browser drafts with Adapter Required state.
- Apps/connectors are not claimed connected.
- Developer is a browser-local sandbox; unsupported shell commands exit 126.

### Owner Core
- owner authentication is required.
- executor state is shown as NOT_CONNECTED when no execution adapter exists.
- prepared/approved missions are not reported as executed without ActionAttempt/Receipt evidence.
- runtime settings remain self_hosted_only and paid external inference is forced off.

### Child Lab
- separate AQLEVON_CHILD_* runtime contract.
- no fallback to public AQLEVON.
- no public weight write.
- no Worker 03/P4 write.
- no automatic promotion.
- external tool execution requires owner permissions + dedicated adapter + receipt.

## Defects found and repaired in this audit

### R1 — sovereign deep reasoning silently suppressed
Old multi-provider exclusion logic excluded aqlevon-engine after the first call. In a one-engine sovereign runtime that could suppress second-pass reasoning and advisory verification.

Repair:
- remove same-engine excludeProviders usage from chat multi-pass flow.
- keep multiple prompt passes on the owned AQLEVON engine.
- mark verifier as same_runtime=true and independent=false.
- route metadata now distinguishes candidate_passes from independent_candidates.
- formal verification still requires deterministic/external evidence where required.

### R2 — fresh Child Lab carried an authored persona
Fresh state contained prewritten personality/purpose text.

Repair:
- owner-defined persona and purpose start empty.
- base-model general pretrained knowledge is not falsely described as erased.
- owner upbringing begins from blank Child Lab persona/lesson state.

### R3 — permission toggles were not all executable
The UI exposed browser login/form/submit/publish/account/multi-step permissions but the test arena mapped most browser actions to navigate.

Repair:
- explicit action selector.
- compound permission resolution.
- multi-step grant enforcement.
- denied tool requests return required_permissions and missing_permissions.

### R4 — autonomy UI overclaimed behavior
The previous label implied an autonomous agent loop.

Repair:
- autonomy is labeled as Adapter policy.
- UI states that no hidden autonomous execution loop exists without adapter + receipt.

### R5 — incomplete child reset / snapshot restoration
Reset could leave a stale Candidate/Eval and operational grants. Snapshot restoration omitted child identity.

Repair:
- reset clears Candidate/Eval and revokes permissions.
- snapshot stores/restores identity with persona/datasets.
- public model and training lane remain untouched.

### R6 — Child Lab narrow-screen overflow risk
Inline layout used fixed 360px login and min 340px grid cards with non-wrapping rows.

Repair:
- fluid shell padding.
- mobile-safe login width.
- wrapped controls/header.
- minmax(min(100%,340px),1fr) responsive grid.

### R7 — public personalization and memory were saved but not used
Workspace settings stored custom instructions and local memory but they did not enter AQLEVON prompts.

Repair:
- personalization max 4,000 chars.
- up to 16 recent local memories, max 1,000 chars each.
- sent on both public chat and Work paths.
- preserved through AQLEVON Commons fallback.
- server redacts secret-like material again.
- system prompt labels user context as non-authoritative and unable to override runtime law, TaskContract, permissions, or verification.

## Current persistence boundaries
- public Workspace chats/files/settings/memory: browser-local.
- Child Lab persona/trials/permissions: browser-local.
- Child long-term memory: IndexedDB.
- these are not cross-device server synchronization.

This is intentional truthfulness for the current preview. Server-side persistence can be added later without pretending it already exists.

## Current expected blockers before trained model cutover
The preview may correctly report:
- AQLEVON_MODEL_URL missing / main inference unavailable.
- zero Commons workers.
- AQLEVON Child Runtime not connected.
- Child tool adapters ADAPTER_REQUIRED.
- public Web Search unavailable.
- external Apps / real Git / terminal / automation executor unavailable.

These are connection/runtime blockers, not UI success claims.

## Verification gate
The branch CI must pass all of:
- Sovereign runtime tests
- Workspace truth/readiness
- Child Lab isolation
- Child candidate
- Child evaluation
- Child long-term memory
- Child permissions
- Owner Core contract
- Security regression
- exact Vercel parity command: npm run bos:check && npm run bos:test && npm run build
- Production build

Exact final head/run/live preview should be recorded after this document commit and Preview deployment complete.

## Hard boundaries
- no main merge
- no Production promotion
- no Worker 03/P4 mutation
- no paid GPU
- no capability-gain claim
