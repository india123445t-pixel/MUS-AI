# AQLEVON Child Lab V1

Status: isolated owner-only experimental personality lab.

## Purpose
The Child Lab is a separate place where the owner can raise, teach, test, and shape an experimental AQLEVON personality in plain language.

It is not the public AQLEVON model.
It is not Owner Core.
It is not the current Worker 03 / P4 training lane.
It does not write production weights.

## Isolation contract
The Child Lab uses only:
- AQLEVON_CHILD_MODEL_URL
- AQLEVON_CHILD_MODEL_NAME
- AQLEVON_CHILD_MODEL_HEALTH_URL
- AQLEVON_CHILD_MODEL_KEY

It must never fall back to:
- AQLEVON_MODEL_URL
- the public AQLEVON runtime
- the current training candidate
- Worker 03 / P4 training artifacts
- production model weights

Browser memory key:
- aqlevon-child-lab-v1

## Owner workflow
1. Define the child's personality in plain language.
2. Add lessons in plain language.
3. Talk to the child.
4. Define a test goal.
5. Define success criteria.
6. Run the test in the isolated lab.
7. Mark the result PASS or FAIL.
8. Iterate.

Nothing is promoted to the main AQLEVON model automatically.

## Execution/tools
The lab can have its own adapters for:
- web research
- browser
- terminal
- files
- media
- later specialist toolchains

Every adapter is fail-closed and starts as ADAPTER_REQUIRED.
No tool execution is considered real without a dedicated Child Lab adapter and evidence/receipt.

## Training evolution
V1 stores personality, lessons, messages, and trial history locally in the owner's browser and routes inference only to the dedicated Child Runtime.

Future versions may add:
- server-side encrypted child memory
- child-only datasets
- child-only checkpoints/adapters
- child-only fine-tuning
- LoRA/personality snapshots
- role packaging/export
- sellable specialist persona packages
- automated trial suites
- web/browser/media execution receipts

Any future weight update must target a child-specific artifact and must never reuse the production training lane implicitly.

## Safety against project breakage
- No writes to main.
- No writes to production AQLEVON weights.
- No writes to Worker 03 / P4 training state.
- No automatic promotion from Child Lab to public AQLEVON.
- Owner Core remains a separate control surface.
- Child runtime must be explicitly configured before chat is enabled.


## V1.1 — teaching, snapshots and tool execution lane
The Child Lab now includes:
- owner-written personality
- owner-written lessons
- isolated chat history
- PASS/FAIL trial history
- correction examples: owner can replace a bad child answer with a preferred answer
- child-only JSONL teaching dataset export
- persona package export/import
- local snapshots that preserve persona, lessons, trials and teaching examples
- child-only tool broker with explicit adapters for web, browser, terminal, files and media
- receipt-gated tool execution: a tool run is not accepted as executed without an adapter receipt

### Child teaching dataset contract
Schema:
- AQLEVON_CHILD_TEACHING_EXAMPLE_V1

Each row contains only child-lab material:
- input
- child_answer
- preferred_answer
- persona_snapshot
- source=child-lab-only
- production_weight_write=false
- training_lane_write=false

This dataset is NOT automatically connected to the current AQLEVON training pipeline.
It is an export artifact for a future child-specific training lane.

### Child persona package contract
Schema:
- AQLEVON_CHILD_PERSONA_PACKAGE_V1

A package can contain:
- persona
- lessons
- trials
- teaching examples
- child isolation metadata

Import restores only Child Lab state.

### Child tool adapter contract
Protocol:
- AQLEVON_CHILD_TOOL_V1

Supported adapter identities:
- AQLEVON_CHILD_WEB_ADAPTER_URL
- AQLEVON_CHILD_BROWSER_ADAPTER_URL
- AQLEVON_CHILD_TERMINAL_ADAPTER_URL
- AQLEVON_CHILD_FILES_ADAPTER_URL
- AQLEVON_CHILD_MEDIA_ADAPTER_URL

Each tool has a matching optional *_KEY server-side secret.
No tool credential is accepted from the browser UI.

A tool adapter must return:
- ok=true
- receipt
- optional output
- optional evidence

Without a receipt the run is rejected as RECEIPT_REQUIRED.

Every adapter request receives hard isolation metadata:
- scope=child-lab-only
- public_model_access=false
- production_weight_write=false
- training_lane_write=false

### Future child weight training
Actual child weight updates remain intentionally absent from V1.1.
When introduced, they must use:
- a child-specific base/checkpoint identity
- a child-specific dataset manifest
- a child-specific output artifact path
- no implicit access to Worker 03 / P4 artifacts
- no automatic promotion to production AQLEVON
- explicit evaluation before any packaging/export


## V1.2 — identity and isolated training pack
The owner can now define a child identity:
- name
- specialty
- purpose

This allows separate specialist children such as video, music, research, security, or any other owner-defined role without changing the public AQLEVON model.

Training-pack export schema:
- AQLEVON_CHILD_TRAINING_PACK_V1

The pack contains:
- child identity
- persona
- lessons
- teaching examples
- trial results
- isolation manifest

Hard manifest values:
- target_artifact=CHILD_CHECKPOINT_ONLY
- public_model_access=false
- production_weight_write=false
- training_lane_write=false
- auto_promote=false

The Training Pack is preparation material only. It does not run training and does not modify weights.

## V1.2 — isolated teaching candidate lane

The Child Lab can now package its teaching state into an isolated evaluation candidate without starting training.

Schema:
- AQLEVON_CHILD_TEACHING_CANDIDATE_V1

Candidate contents:
- child persona
- lessons
- correction examples
- PASS/FAIL trial summary
- deterministic candidate SHA-256
- hard isolation metadata

The owner UI exposes a simple "جهّز Candidate" action. Packaging returns:
- evaluation recommendation
- example count
- candidate SHA
- training_started=false
- gpu_requested=false

Hard rules:
- Candidate packaging never starts training.
- Candidate packaging never requests GPU.
- Candidate packaging never reads or writes Worker 03 / P4 state.
- Candidate packaging never writes production AQLEVON weights.
- Candidate packaging never auto-promotes to public AQLEVON.
- The only valid next state after packaging is evaluation (EVAL_REQUIRED) or rejection.

Owner-only route:
- POST /api/admin/child-lab/candidate

Implementation:
- lib/aqlevon/child-candidate.js
- app/api/admin/child-lab/candidate/route.js
- tests/child-candidate.test.mjs

This lane exists so Child Lab teaching can later feed a dedicated child-specific checkpoint pipeline without contaminating the active AQLEVON training lane.

## V1.4 — long-term memory retrieval

The Child Lab now has a dedicated long-term memory layer that grows independently from the prompt and from the public AQLEVON runtime.

Storage:
- browser IndexedDB database: aqlevon-child-memory-v1
- scope: child-lab-only
- separate from Workspace local storage
- separate from public model memory
- separate from Worker 03 / P4 training state

Each memory record can store:
- text
- kind
- topic
- tags
- importance
- source
- active state
- use count
- creation/update timestamps

Supported memory kinds in the owner UI:
- lesson
- correction
- experience
- preference
- fact

Retrieval contract:
- the full memory archive is never injected into every prompt
- before each child turn, the browser searches the child memory store
- only the most relevant memories are selected
- current retrieval cap: top 24 memories per turn
- the server re-validates and caps incoming memories to 24
- the child runtime injects only this filtered set under RELEVANT LONG-TERM MEMORY

Automatic memory capture:
- explicit owner lessons are saved as long-term lesson memories
- owner corrections are saved as high-importance correction memories
- retrieved memories can track usage

Owner controls:
- add memory manually
- choose kind/topic/tags/importance
- search and filter memory
- delete individual memories
- export the child memory archive
- import a child memory archive
- reset Child Lab long-term memory without touching public AQLEVON or the training lane

Memory export schema:
- AQLEVON_CHILD_MEMORY_EXPORT_V1

Implementation:
- lib/aqlevon/child-memory.js
- app/admin/child-lab/memory-db.js
- app/admin/child-lab/page.js
- app/api/admin/child-lab/chat/route.js
- lib/aqlevon/child-runtime.js
- tests/child-memory.test.mjs

Important capacity note:
The design is expandable rather than literally infinite. The archive can continue growing until the storage backend reaches its physical quota. Retrieval keeps prompt size bounded because only relevant memories are selected. A future server-side memory adapter can replace or extend IndexedDB without changing the child runtime contract.

## V1.5 — owner permissions console

The Child Lab now has an owner-facing operational permissions console.

Permissions are explicit toggles instead of hidden operational choices.

Controls:
- master execution on/off
- emergency STOP that disables execution and revokes all operational grants
- autonomy policy sent to the connected adapter: observe/propose, require an action command, or allow multi-step continuation within enabled grants. No hidden autonomous agent loop is claimed.
- per-capability toggles
- local audit log for permission changes

Operational permission catalog:
- web research
- browser navigation
- browser form filling
- browser use of an already-authenticated owner session
- browser downloads
- browser uploads
- browser submit/confirm actions
- file read
- file create/edit
- file delete
- terminal/code execution in the child sandbox
- media read
- media create/edit
- multi-step workflows
- external publishing
- connected-account setting changes

Enforcement:
- lib/aqlevon/child-permissions.js defines the owner permission schema
- lib/aqlevon/child-tools.js maps tool actions to required operational permissions
- the tool broker returns PERMISSION_DISABLED before calling an adapter when the required toggle is off
- app/api/admin/child-lab/tool/route.js passes the owner permission state into the broker
- app/admin/child-lab/page.js exposes the controls and Emergency Stop

Default state:
- master execution OFF
- all operational grants OFF
- autonomy = ask_each_action

The permissions console controls Child Lab operational capabilities. Platform safety boundaries remain separate from these toggles.

CI:
- tests/child-permissions.test.mjs
- workflow gate: Child permissions tests
- exact verified implementation head before this documentation commit: 8abf70a47a68a27fb65325588f3bd833e11877e9
- GitHub Actions run: 35951056992 — SUCCESS

No main merge, no production AQLEVON weight mutation, no Worker 03/P4 mutation, and no GPU request occurred in V1.5.


## V1.6 — readiness hardening (2026-09-25)

This audit hardened Child Lab and the public AQLEVON application without touching the active Worker 03/P4 training lane, production weights, paid GPU, or main.

### Fresh-child baseline
A fresh/reset child now starts with:
- no owner-defined persona text
- no owner-defined purpose
- no lessons
- no teaching examples
- no candidate/evaluation state
- all operational permissions revoked

The base child runtime may still contain general pretrained knowledge. "Blank" here means blank owner upbringing/persona state, not an untrained language model.

### Complete reset and snapshots
Reset now clears:
- persona/identity upbringing state
- lessons/trials/examples
- long-term Child Lab memory
- current Candidate and Candidate evaluation
- operational permissions

Reset never touches public AQLEVON or Worker 03/P4.

Snapshots now preserve and restore child identity together with persona, lessons, trials, and correction examples.

### Executable permission actions
The owner can choose an explicit tool action in the test arena instead of every browser run silently becoming "navigate".

Examples:
- browser.navigate
- browser.form_fill
- browser.session_login
- browser.download
- browser.upload
- browser.submit
- browser.publish
- browser.account_modify
- files.read / files.write / files.delete
- terminal.run
- media.read / media.write

Compound actions require every relevant grant:
- publish => browser.submit + external.publish
- account modification => browser.submit + account.modify
- multi-step execution additionally requires workflow.multi_step

The broker returns required_permissions and missing_permissions when execution is blocked.

### Autonomy truth
The autonomy selector is an adapter policy, not a claim that an autonomous tool-use loop already exists.
Real external execution still requires:
- a connected Child Lab adapter
- enabled owner permissions
- an adapter receipt

The UI explicitly states this.

### Persistence truth
Current child persona/settings and permission toggles are browser/device local.
Long-term memory uses browser IndexedDB.
They are not yet server-synchronized across devices.

A future server-side Child memory/permission adapter is a scale step, not a prerequisite for isolated local teaching.

### Mobile readiness
Child Lab layout now uses fluid padding, wrapping controls, mobile-safe login width, and a grid that collapses without horizontal overflow on narrow screens.

### Sovereign multi-pass reasoning repair
The public AQLEVON chat previously retained an old multi-provider exclusion rule. After the runtime became AQLEVON-only, that rule could suppress the second deep-reasoning pass and advisory verifier because both use the same owned aqlevon-engine.

The old exclusion was removed. Deep reasoning can now make multiple passes on the same sovereign runtime.
Truth metadata now says:
- candidate_passes = number of solution passes requested
- independent_candidates = 1
- verifier_independent = false
- advisory.same_runtime = true

Model agreement is still not treated as formal proof.

### Public personalization and local memory
Workspace personalization and local memory are no longer cosmetic settings.
The browser now sends bounded context to AQLEVON:
- personalization: max 4,000 characters
- recent memories: max 16 items, max 1,000 characters each

The server redacts secret-like material again and labels this context non-authoritative.
It cannot override runtime law, TaskContract, permissions, or verification requirements.
This context is also preserved when the unified chat path falls back to AQLEVON Commons.

### Known not-yet-connected surfaces
These remain intentionally fail-closed until their dedicated runtime/adapters exist:
- AQLEVON main model endpoint in the current preview
- Child Runtime endpoint
- Child web/browser/terminal/files/media adapters
- public Web Search / Deep Research adapter
- real public Git/terminal adapter
- public external Apps connectors
- real background Automations executor
- Owner Core external Executor

The UI must continue to label these as unavailable / adapter required rather than simulate success.
