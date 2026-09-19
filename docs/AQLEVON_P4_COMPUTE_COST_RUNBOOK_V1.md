# AQLEVON P4 Compute Cost Orchestrator Runbook V1

Task: `P4-A06-COMPUTE-COST-ORCHESTRATOR`  
Status: execution plumbing only. G1 is already complete and MUST NOT be rerun by this runbook.

## 1. Hard safety / authority law
Paid compute is disabled unless ALL are true for the exact run:
1. `AQLEVON_GPU_EXECUTION_AUTHORIZED=1`;
2. `AQLEVON_COMPUTE_ORIGIN=paid_manager_authorized`;
3. a self-hashed `AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1` exists;
4. its SHA exactly equals `AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_SHA256`;
5. it binds the exact run-task ID, run-manifest SHA, compute profile, max billed seconds, max hourly rate, max total cost and max artifact egress;
6. the configured provider hourly rate is inside the Manager cap;
7. the run-time/rate plan is inside the Manager total-cost cap;
8. `AQLEVON_BILLING_START_EPOCH_MS` is present so the watchdog budgets from billing start, not from training start.

Any unapproved `paid`, `spot`, provider name or mismatched authorization fails closed.

The authorization is marked `single_use`; the dispatcher also creates a local one-use marker in the receipt directory before launching the payload. This is an operational replay guard, not a cryptographic identity system. The Manager's separately supplied expected authorization SHA is the explicit approval boundary.

## 2. P4 price-first profiles

| Profile | Purpose | Required visible VRAM | Default economic intent |
|---|---|---:|---|
| `p4-surrogate-1x24` | same-architecture/small surrogate method tournament | >=22,000 MiB | lowest-cost technically adequate 24GB-class GPU |
| `p4-gene1-27b-1x80` | one canonical 27B Gene #1 adapter run after surrogate decision | >=78,000 MiB | A100 80GB only; shortest justified run |
| `b07-e0-1x8to12` | B07 small falsification | >=7,800 MiB | free/donated first; cheap 8–12GB if separately authorized |

Current provider snapshot, checked 2026-09-19 and NOT hard-coded:
- RunPod Community listing showed RTX A5000 24GB about $0.16/h, RTX 3090 24GB about $0.22/h, RTX 4090 24GB about $0.34/h, A100 PCIe 80GB about $1.19/h, A100 SXM 80GB about $1.39/h.
- RunPod Secure pricing showed higher rates (for example A5000 24GB about $0.27/h and A100 80GB about $1.59/h).
- Lambda lists different billing/rates and bills on-demand instances in one-minute increments.

Prices/availability change. Always pass the rate actually shown by the provider into the dispatcher and let the Manager authorization cap it.

## 3. Cheapest-run decision law
Surrogate tournament:
1. free/donated compatible 24GB first;
2. otherwise price-first 24GB class;
3. prefer the cheapest card that passes exact model/framework preflight; do not pay for 80GB merely to run a surrogate.

Canonical 27B:
1. do not run until Worker 05 surrogate evidence + Manager recipe decision exist;
2. use exactly one 80GB-class A100 profile;
3. price-first A100 PCIe 80GB is acceptable for a single-GPU run if Worker 03's exact recipe/preflight passes;
4. A100 SXM 80GB is the G1-proven hardware fallback;
5. do not keep the instance alive waiting for Worker 01/02/05 or missing data.

## 4. Before creating any paid GPU
All of these must already exist locally or in ready-to-download storage:
- exact Worker 01 frozen recipe;
- exact Worker 02 training-visible shard + manifest;
- Worker 03 exact command/config;
- run-manifest SHA;
- output location;
- telemetry path;
- Manager compute authorization + expected authorization SHA;
- max time/cost/egress budget.

Run a dry plan BEFORE provisioning:

```bash
node scripts/p3-compute-dispatch.mjs \
  --profile p4-surrogate-1x24 \
  --run-manifest-sha <RUN_MANIFEST_SHA> \
  --gpu-indices 0 \
  --telemetry-json artifacts/p4-surrogate/payload-telemetry.json \
  --receipt-dir artifacts/p4-surrogate/compute \
  --dry-run -- <EXACT_WORKER03_COMMAND...>
```

The dry-run emits only a hash identity for argv; it must not print raw secret arguments.

## 5. Exact paid execution form
Example surrogate run after Manager authorization:

```bash
export AQLEVON_GPU_EXECUTION_AUTHORIZED=1
export AQLEVON_COMPUTE_ORIGIN=paid_manager_authorized
export AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_SHA256=<MANAGER_AUTH_SHA>
export AQLEVON_BILLING_START_EPOCH_MS=<PROVIDER_BILLING_START_EPOCH_MS>

node scripts/p3-compute-dispatch.mjs \
  --profile p4-surrogate-1x24 \
  --run-task-id P4-A03-GENE1-PHYSICAL-TRAINER \
  --run-manifest-sha <RUN_MANIFEST_SHA> \
  --manager-authorization <MANAGER_AUTH_JSON> \
  --provider-hourly-usd <ACTUAL_PROVIDER_RATE> \
  --gpu-indices 0 \
  --telemetry-json artifacts/p4-surrogate/payload-telemetry.json \
  --receipt-dir artifacts/p4-surrogate/compute \
  --execute -- <EXACT_WORKER03_COMMAND...>
```

Canonical 27B uses the same pattern with `--profile p4-gene1-27b-1x80` and a separately authorized run manifest/budget. Never reuse the surrogate authorization.

The dispatcher watchdog computes remaining time from billing start and terminates the payload process tree when the Manager time budget is exhausted.

## 6. Provider launch/stop discipline
For RunPod, current `runpodctl` uses noun-verb lifecycle commands:
- create: `runpodctl pod create ...`
- stop: `runpodctl pod stop <pod-id>`
- delete: `runpodctl pod delete <pod-id>`

Cost-minimizing law:
- do not create the pod until inputs and authorization are ready;
- record billing start immediately when the provider says billing starts;
- run exactly one frozen experiment;
- upload/copy only required small artifacts;
- delete/terminate the pod immediately after artifact integrity is confirmed.

A stopped pod may still incur storage charges. For one-shot Gene #1 compute, delete/terminate after artifact transfer unless the Manager explicitly chooses persistent storage.

Generic one-shell pattern:

```bash
# provision only after preflight; capture provider ID and billing start
<PROVIDER_CREATE_COMMAND>
# execute the exact authorized dispatcher command
<AUTHORIZED_AQLEVON_DISPATCH_COMMAND>
RUN_CODE=$?
# transfer only the required adapter/manifests/receipts
<ARTIFACT_COPY_COMMAND>
# stop billing immediately
<PROVIDER_DELETE_OR_TERMINATE_COMMAND>
exit $RUN_CODE
```

Provider lifecycle remains external so AQLEVON does not store cloud API secrets in repository scripts.

## 7. Payload telemetry contract
The existing P3 payload telemetry remains authoritative for the training process:
```json
{
  "schema": "aqlevon-p3-payload-telemetry-v1",
  "peak_vram_bytes": 123456789,
  "tokens_processed": 512,
  "tokens_generated": 0
}
```

For P4 cost finalization, also provide exact `examples_processed` and artifact egress bytes from the training/artifact pipeline. Failed attempts are allowed to have incomplete work counters; their GPU/billing cost still remains in totals.

## 8. Finalize cost immediately after provider stop
Create one `AQLEVON_COMPUTE_COST_RECEIPT_V1` per compute attempt:

```bash
node scripts/p4-cost-finalize.mjs \
  --attempt-receipt artifacts/p4-surrogate/compute/compute-attempt-<ID>.json \
  --manager-authorization <MANAGER_AUTH_JSON> \
  --billing-start-epoch-ms <START_MS> \
  --process-end-epoch-ms <PROCESS_END_MS> \
  --provider-hourly-usd <RATE> \
  --billing-granularity-seconds <PROVIDER_GRANULARITY> \
  --artifact-egress-bytes <BYTES> \
  --egress-usd-per-gib <RATE> \
  --examples-processed <EXAMPLES_OR_OMIT_IF_UNKNOWN> \
  --actual-billed-wall-seconds <PROVIDER_ACTUAL_SECONDS> \
  --actual-compute-cost-usd <PROVIDER_ACTUAL_COMPUTE_COST> \
  --actual-egress-cost-usd <PROVIDER_ACTUAL_EGRESS_COST> \
  --out artifacts/p4-surrogate/cost-<ID>.json
```

If provider-actual billing is not available yet, omit the three `--actual-...` fields. The receipt remains estimated and must later be replaced/finalized with provider-actual values before claiming actual cost.

The budget gate checks both estimated and provided actual billed time/cost/egress against the Manager authorization.

## 9. Cost per verified candidate
Worker 06 does not decide verification. Only after:
- exact Candidate Artifact Manifest exists;
- Worker 05 evaluation receipt exists; and
- Manager acceptance receipt/identity exists,

bind all compute cost receipts:

```bash
node scripts/p4-candidate-cost-summary.mjs \
  --candidate-manifest-sha <CANDIDATE_SHA> \
  --worker05-evaluation-receipt-sha <WORKER05_RECEIPT_SHA> \
  --manager-acceptance-receipt-sha <MANAGER_ACCEPTANCE_SHA> \
  --cost-receipt artifacts/p4/cost-attempt-1.json \
  --cost-receipt artifacts/p4/cost-attempt-2.json \
  --out artifacts/p4/verified-candidate-cost.json
```

This produces `AQLEVON_VERIFIED_CANDIDATE_COST_SUMMARY_V1` with:
- total GPU-seconds;
- billed wall time;
- retries/failures because every attempt receipt is included;
- token/example totals when known;
- incomplete-work-attempt count;
- artifact egress bytes;
- estimated total cost;
- provider-actual total cost only when complete for every included attempt.

The summary only binds the supplied Worker 05 + Manager receipt identities. It does not independently recreate Worker 05 evaluation logic or Manager authority.

## 10. Failure / idle-billing stop law
Terminate immediately if any occurs before training:
- shard/manifest missing;
- command drift from frozen run manifest;
- Manager authorization mismatch;
- hourly rate exceeds cap;
- projected max time × rate exceeds Manager total cost cap;
- GPU VRAM/profile mismatch;
- telemetry path unwritable;
- Worker 03 required artifact/output path missing.

During training, terminate on:
- Manager watchdog expiry;
- irrecoverable OOM/framework failure;
- repeated failure unless retry was explicitly marked retry-safe;
- evidence path corruption.

Never leave a paid GPU waiting for another worker. Re-provision later instead.

## 11. Truth boundary
This lane measures and gates compute. It does not prove a capability gain.
- G1 PASS is historical input and is not rerun.
- Worker 06 never selects the winning model/method.
- Worker 05 supplies evaluation evidence.
- Manager alone accepts/rejects Gene #1.
- No production deployment or `main` merge is authorized here.
