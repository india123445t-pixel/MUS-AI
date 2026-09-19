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


---

## 12. P4.1 accelerated surrogate retry guard

Task overlay: `P4.1-A06-RETRY-COST-GUARD`.

### Exact A1 identity bound by this overlay

This section is preparation only and does **not** authorize spend.

- run task: `P4-A03-GENE1-PHYSICAL-TRAINER`
- arm: `P4_A1_RLVR_CONTROL`
- seed: `1701`
- compute profile: `p4-surrogate-1x24`
- training-plan SHA-256: `3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095`
- run-manifest SHA-256: `7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45`
- command SHA-256: `3ad2fd2cd5303e1eb4ea71f3e25edf07d38269df1b5b3c8b6e98c8553e017400`
- command-lock SHA-256: `f1d05b53d0e00b07f7f4d60c90a6bf489f4cd2bd118b2b6a6b38c66026cee44e`

Retry07 and every older authorization are stale/consumed and must not be reused.

### Manager authorization TEMPLATE ONLY — intentionally invalid until Manager fills it

Do not copy this template into execution as-is. The numeric/cost placeholders deliberately make it invalid. After the Manager chooses every ceiling, generate the canonical object through `buildManagerComputeAuthorization()` and use its resulting self-hash as the separately supplied expected authorization SHA.

```json
{
  "schema_version": 1,
  "authorization_kind": "AQLEVON_MANAGER_COMPUTE_AUTHORIZATION_V1",
  "hash_profile": "AQLEVON_CANONICAL_JSON_SHA256_V1",
  "authorization_id": "<MANAGER_NEW_UNIQUE_SINGLE_USE_ID>",
  "run_task_id": "P4-A03-GENE1-PHYSICAL-TRAINER",
  "run_manifest_sha256": "7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45",
  "profile_id": "p4-surrogate-1x24",
  "compute_origin": "paid_manager_authorized",
  "max_billed_seconds": "<MANAGER_INTEGER>",
  "max_total_cost_usd": "<MANAGER_CANONICAL_DECIMAL>",
  "max_hourly_rate_usd": "<MANAGER_CANONICAL_DECIMAL>",
  "max_artifact_egress_bytes": "<MANAGER_INTEGER>",
  "single_use": true,
  "authorization_sha256": "<DERIVE_ONLY_AFTER_MANAGER_FILLS_ALL_FIELDS>"
}
```

No Worker may choose these ceilings on the Manager's behalf.

### Current public RunPod planning snapshot — checked 2026-09-19

Public Community Cloud model listings currently show:
- RTX A5000 24GB: about **$0.16/h**
- RTX 3090 24GB: about **$0.22/h**
- RTX 4090 24GB: about **$0.34/h**

Public Secure Cloud pricing is higher (for example A5000 24GB about **$0.27/h**, 3090 about **$0.50/h**, 4090 about **$0.74/h**). RunPod states Pod billing is per second. Public pages indicate broad inventory across regions, but they do not prove that a particular account/region has the requested card available at launch time.

Sources:
- https://www.runpod.io/gpu-models
- https://www.runpod.io/pricing
- https://www.runpod.io/articles/guides/ai-server-cost

### Cost-ceiling options — recommendations only, NOT authorization

For one GPU and compute charge only, `cost = hourly_rate × billed_seconds / 3600`.

| Optional time ceiling | A5000 Community @ $0.16/h | 3090 Community @ $0.22/h | 4090 Community @ $0.34/h |
|---|---:|---:|---:|
| 15 min | $0.040 | $0.055 | $0.085 |
| 30 min | $0.080 | $0.110 | $0.170 |
| 60 min | $0.160 | $0.220 | $0.340 |

These are decision aids only. They exclude any storage/tax/other provider charges and do not replace provider-actual billing. The Manager must choose the exact GPU class/provider lane, time, hourly-rate cap, total-cost cap, and egress cap.

### Why the cheapest hourly GPU may not be the cheapest successful experiment

Compare expected cost per valid evidence result rather than hourly rate alone:

`expected_compute_cost_per_valid_result ≈ hourly_rate × expected_billed_hours_per_attempt × expected_attempts_to_valid_result`.

At the public Community rates above, with equal success probability:
- a 3090 at $0.22/h must finish in at most **72.7%** of the A5000's billed time to beat a $0.16/h A5000 on compute charge;
- a 4090 at $0.34/h must finish in at most **47.1%** of the A5000's billed time to beat it;
- a higher-priced lane can still win if it materially reduces bootstrap failures/retries or setup/download delay.

Do not assume those speed or reliability ratios; measure them on the exact workload if the Manager authorizes a run.

### P4.1 watchdog hardening

Paid execution now reserves a fixed **5-second shutdown margin** before the Manager's `max_billed_seconds` boundary. At that margin:
1. the payload process group receives `SIGTERM`;
2. if it has not exited within **1 second**, the process group receives `SIGKILL`;
3. the attempt remains a failed measurable receipt with `manager_budget_timeout`.

If less than the 5-second safety margin remains when dispatch starts, execution fails closed before launching the payload.

This protects the payload runtime budget. Provider billing is stopped separately by immediate pod deletion after artifact/receipt capture.

### Secret/log boundary

The dispatcher itself logs only hash identity for payload argv, never raw argv. P4.1 additionally removes secret-like environment variable names (API keys, tokens, secrets, passwords, credentials/private keys) from the payload environment before launch, including provider API keys such as `RUNPOD_API_KEY`.

Provider lifecycle credentials stay outside the repository and outside the training payload. A fixed training command must not contain credentials in raw argv.

### Single-use replay guard

A fresh Manager authorization produces a fresh authorization SHA. Before payload launch, the dispatcher atomically creates:

`manager-authorization-<AUTH_SHA>.used`

with exclusive-create semantics. A second attempt using the same authorization in the same receipt workspace fails closed with `manager_authorization_already_used`.

The marker is an operational local guard, not a global distributed lock. If a pod/workspace is recreated, the Manager must still issue a **new** single-use authorization rather than copying the old authorization file.

### One-command RunPod stop/destroy path

Current `runpodctl` uses the noun-verb lifecycle interface. The destructive one-shot stop path is:

```bash
runpodctl pod delete <pod-id>
```

For a guarded shell wrapper, register deletion before dispatch so failures still tear the pod down:

```bash
POD_ID="<exact-created-pod-id>"
trap 'runpodctl pod delete "$POD_ID" >/dev/null 2>&1 || true' EXIT INT TERM

# Exact Manager-authorized dispatcher command goes here.
<AUTHORIZED_AQLEVON_DISPATCH_COMMAND>
RUN_CODE=$?

# Copy only required evidence before normal exit if the workflow needs it.
<ARTIFACT_COPY_COMMAND>

exit "$RUN_CODE"
```

After deletion, `runpodctl pod list` / `runpodctl pod get <pod-id>` should be used to verify lifecycle state. Never leave a paid Pod alive waiting for Worker 05. Current CLI reference: https://github.com/runpod/runpodctl

### Failed-attempt accounting

A failed payload still emits its Compute Attempt Receipt with elapsed time / allocated GPU-seconds when measurable. P4 cost finalization accepts failed outcomes with incomplete token/example counters, so failed GPU time and billed cost remain in the candidate cost numerator instead of disappearing.

### P4.1 no-spend statement

This overlay performs CPU/control-plane preparation only. It creates no Pod, buys no GPU, starts no paid endpoint/storage, reruns no G1 work, changes no production system, and makes no capability-gain claim.
