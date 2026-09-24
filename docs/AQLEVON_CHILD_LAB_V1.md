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
