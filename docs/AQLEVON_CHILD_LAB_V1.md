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
