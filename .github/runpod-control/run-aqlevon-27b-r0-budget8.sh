#!/usr/bin/env bash
set -euo pipefail

AUTH=.github/runpod-control/aqlevon-27b-r0-fresh-authorization.json
CLAIMS_DIR=.github/runpod-control/claims
RESERVATION=""
CONSUMED=""
RESULT=.github/runpod-control/aqlevon-27b-r0-fresh-result.json
IMAGE_DIGEST=sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec
SCIENTIFIC_CONTRACT_SHA256=484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d
SCIENTIFIC_CONTRACT_COMMIT=4ddb508ea0dc99ab7e02588e19915915fc67976c
SCIENTIFIC_CONTRACT_BLOB=6d2424a589af250f878c1a83a3811aa6ccd5b4b0
SCIENTIFIC_CONTRACT_PATH=research/weight_factory/agent03/aqlevon_27b_rerun_scientific_contract_v1.json
SCIENTIFIC_CONTRACT_VERIFIER_PATH=research/weight_factory/agent03/aqlevon_27b_rerun_contract_v1.py
SCIENTIFIC_CONTRACT_VERIFIER_BLOB=990ab86bebcbe69050dc5f644c6ff12f60db75d3
HISTORICAL_SOURCE_COMMIT=4e3f1b03cfe77ac4355907ec692574f30d180252
EXPECTED_CURRENT_TRAINER_BLOB=9085e692d43110600e7bf214ffdab910f4821f1c
CURRENT_TRAINER_PATH=research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py
W02_COMMIT=abb94ef134e2e97036b6959dbc9db4278d3736b6
MAX_ELAPSED=3200
pod=""
stopped=0

cleanup() {
  status=$?
  if [ -n "$pod" ] && [ "$stopped" != 1 ]; then
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-exit-stop.json || true
    stopped=1
  fi
  # Fail closed on durability: never delete here. Deletion is a later workflow
  # step permitted only after durable artifact upload succeeds.
  exit "$status"
}
trap cleanup EXIT

test -n "${RUNPOD_API_KEY:-}"
test -f "$AUTH"
python3 -m py_compile research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py .github/runpod-control/aqlevon-27b-reservation.py
bash -n .github/runpod-control/aqlevon-27b-r0-bootstrap.sh
echo AQLEVON_27B_FREE_SYNTAX_PREFLIGHT_PASS

SCIENTIFIC_CONTRACT_SHA256="$SCIENTIFIC_CONTRACT_SHA256" AUTH="$AUTH" python3 - <<'PY'
import json,os,re
from pathlib import Path
p=Path(os.environ["AUTH"])
a=json.loads(p.read_text())
assert a["kind"]=="AQLEVON_MANAGER_PAID_AUTHORIZATION_V2"
assert a["control_plane_contract"]=="AQLEVON_27B_CONTROL_PLANE_V2"
assert a["fresh_authorization"] is True
assert a["scientific_contract_sha256"]==os.environ["SCIENTIFIC_CONTRACT_SHA256"]
auth_id=str(a.get("authorization_id") or "")
assert auth_id and re.fullmatch(r"[A-Za-z0-9._:-]{8,160}",auth_id)
assert a["single_use"] is True and a["training_authorized"] is True
assert a["model_repo"]=="Qwen/Qwen3.8-27B"
assert a["model_revision"]=="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
assert float(a["max_total_cost_usd"])<=1.50
assert float(a["max_hourly_rate_usd"])<=1.60
assert int(a["max_billed_seconds"])<=3200
assert a["automatic_cleanup_required"] is True
assert a["artifact_preservation_required"] is True
assert a["no_main_merge"] is True
assert a["sealed_eval_forbidden"] is True
assert str(a.get("issued_at_utc") or "").strip()
resume_pod_id=str(a.get("resume_pod_id") or "").strip()
if resume_pod_id:
    assert re.fullmatch(r"[A-Za-z0-9_-]{6,80}",resume_pod_id)
Path("/tmp/aq27-auth-id").write_text(auth_id)
Path("/tmp/aq27-resume-pod-id").write_text(resume_pod_id)
print("AQLEVON_27B_FRESH_AUTHORIZATION_V2_PASS",auth_id,"resume_pod_id="+(resume_pod_id or "NONE"))
PY
AUTH_ID="$(cat /tmp/aq27-auth-id)"
export AUTH_ID
export SCIENTIFIC_CONTRACT_SHA256
mkdir -p "$CLAIMS_DIR"
RESERVATION="$CLAIMS_DIR/${AUTH_ID}.reservation.json"
CONSUMED="$CLAIMS_DIR/${AUTH_ID}.consumed.json"
test ! -e "$RESERVATION"
test ! -e "$CONSUMED"

# Verify Agent 03's frozen scientific contract, source blobs, and training
# constants before any provider API call or provider-create action.
for ref in "$SCIENTIFIC_CONTRACT_COMMIT" "$HISTORICAL_SOURCE_COMMIT" "$W02_COMMIT"; do
  git cat-file -e "$ref^{commit}" 2>/dev/null || git fetch --no-tags --depth=1 origin "$ref"
done
test "$(git rev-parse "$GITHUB_SHA:$CURRENT_TRAINER_PATH")" = "$EXPECTED_CURRENT_TRAINER_BLOB"
echo AQLEVON_27B_CURRENT_TRAINER_BLOB_PASS "$EXPECTED_CURRENT_TRAINER_BLOB"
test "$(git rev-parse "$SCIENTIFIC_CONTRACT_COMMIT:$SCIENTIFIC_CONTRACT_PATH")" = "$SCIENTIFIC_CONTRACT_BLOB"
test "$(git rev-parse "$SCIENTIFIC_CONTRACT_COMMIT:$SCIENTIFIC_CONTRACT_VERIFIER_PATH")" = "$SCIENTIFIC_CONTRACT_VERIFIER_BLOB"
rm -rf /tmp/aq27-scientific-contract
mkdir -p /tmp/aq27-scientific-contract
git show "$SCIENTIFIC_CONTRACT_COMMIT:$SCIENTIFIC_CONTRACT_PATH" > /tmp/aq27-scientific-contract/aqlevon_27b_rerun_scientific_contract_v1.json
git show "$SCIENTIFIC_CONTRACT_COMMIT:$SCIENTIFIC_CONTRACT_VERIFIER_PATH" > /tmp/aq27-scientific-contract/aqlevon_27b_rerun_contract_v1.py
python3 /tmp/aq27-scientific-contract/aqlevon_27b_rerun_contract_v1.py verify > /tmp/aq27-scientific-contract-verification.json
SCIENTIFIC_CONTRACT_SHA256="$SCIENTIFIC_CONTRACT_SHA256" python3 - <<'PY'
import json,os
x=json.load(open("/tmp/aq27-scientific-contract-verification.json"))
assert x["status"]=="PASS"
assert x["contract_sha256"]==os.environ["SCIENTIFIC_CONTRACT_SHA256"]
assert x["training_recipe_match"] is True
assert x["source_blobs_match"] is True
assert x["same_seed_pairing"] is True
assert x["private_or_sealed_source_count"]==0
print("AQLEVON_27B_SCIENTIFIC_CONTRACT_PRECREATE_PASS",x["contract_sha256"])
PY

curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-pods.json
python3 - <<'PY'
import json
p=json.load(open("/tmp/aq27-pods.json"))
xs=p if isinstance(p,list) else p.get("pods") or p.get("items") or []
active=[]
for x in xs:
    name=str(x.get("name") or "")
    status=str(x.get("desiredStatus") or x.get("status") or "")
    if name.startswith("AQLEVON-27B-R0") and status!="EXITED":
        active.append({"id":x.get("id"),"name":name,"status":status})
assert not active,active
print("AQLEVON_27B_NO_ACTIVE_POD_PASS")
PY

RUNPODCTL_URL="https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64"
RUNPODCTL_TMP="/tmp/aqlevon-runpodctl"
rm -f "$RUNPODCTL_TMP"
for attempt in 1 2 3 4 5; do
  if curl -fL --retry 2 --retry-all-errors --connect-timeout 10 --max-time 90 "$RUNPODCTL_URL" -o "$RUNPODCTL_TMP"; then
    break
  fi
  rm -f "$RUNPODCTL_TMP"
  sleep $((attempt * 2))
done
test -s "$RUNPODCTL_TMP"
sudo install -m 0755 "$RUNPODCTL_TMP" /usr/local/bin/runpodctl
runpodctl version
runpodctl gpu list --output json >/tmp/aq27-gpus.json
python3 - <<'PY'
import json
choices=[]
for g in json.load(open("/tmp/aq27-gpus.json")):
    if str(g.get("gpuId"))!="NVIDIA A100-SXM4-80GB" or not g.get("secureCloud"):
        continue
    price=float(g.get("securePricePerHr") or 999)
    if price>1.60:
        continue
    for d in g.get("dataCenterAvailability") or []:
        if str(d.get("stockStatus") or "").lower()=="none" or not d.get("dataCenterId"):
            continue
        choices.append((price,str(d["dataCenterId"]),str(d.get("stockStatus"))))
assert choices,"no_a100_sxm_80_stock_under_ceiling"
price,dc,stock=sorted(choices)[0]
open("/tmp/aq27-price","w").write(str(price))
open("/tmp/aq27-dc","w").write(dc)
print("AQLEVON_27B_CAPACITY_PASS",price,dc,stock)
PY

RESUME_POD_ID="$(cat /tmp/aq27-resume-pod-id)"
if [ -n "$RESUME_POD_ID" ]; then
  TARGET_POD_ID="$RESUME_POD_ID" python3 - <<'PY' >/tmp/aq27-pod-query.json
import json,os
q="""query pod($input: PodFilter) {
  pod(input: $input) {
    id name desiredStatus costPerHr gpuCount imageName machineId
    containerDiskInGb volumeInGb volumeMountPath ports
  }
}"""
print(json.dumps({"query":q,"variables":{"input":{"podId":os.environ["TARGET_POD_ID"]}}}))
PY
  curl -fsS https://api.runpod.io/graphql     -H "Authorization: Bearer $RUNPOD_API_KEY"     -H 'Content-Type: application/json'     --data-binary @/tmp/aq27-pod-query.json >/tmp/aq27-pod-query-response.json
  TARGET_POD_ID="$RESUME_POD_ID" IMAGE_DIGEST="$IMAGE_DIGEST" python3 - <<'PY'
import json,os
d=json.load(open("/tmp/aq27-pod-query-response.json"))
assert not d.get("errors"),d.get("errors")
p=(d.get("data") or {}).get("pod")
assert p and p.get("id")==os.environ["TARGET_POD_ID"],p
assert p.get("name")=="AQLEVON-27B-R0-BUDGET8",p
assert p.get("desiredStatus")=="EXITED",p
assert int(p.get("gpuCount") or 0)==1,p
assert str(p.get("imageName") or "")=="ghcr.io/india123445t-pixel/mus-ai@"+os.environ["IMAGE_DIGEST"],p
assert float(p.get("costPerHr") or 999)<=1.60,p
assert str(p.get("machineId") or ""),p
print("AQLEVON_27B_RESUME_POD_PRECREATE_PASS",p["id"],p["machineId"],p["costPerHr"])
PY
fi

# Durable pre-create claim. The authorization is consumed before any provider
# create mutation. Ordinary non-force Git push is the cross-run CAS: if another
# claimant moves the control branch first, this run fails before pod creation.
: "${GITHUB_RUN_ID:?missing GITHUB_RUN_ID}"
: "${GITHUB_RUN_ATTEMPT:?missing GITHUB_RUN_ATTEMPT}"
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git fetch origin ops/runpod-control-v1
git rebase origin/ops/runpod-control-v1
test ! -e "$RESERVATION"
test ! -e "$CONSUMED"
python3 .github/runpod-control/aqlevon-27b-reservation.py reserve \
  --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED" \
  --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT" \
  --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID"
git add "$RESERVATION" "$CONSUMED"
git commit -m "ops: reserve and consume AQLEVON 27B authorization before provider create [skip ci]"
if ! git push origin HEAD:ops/runpod-control-v1; then
  echo "AQLEVON_27B_PRECREATE_RESERVATION_PUSH_CONFLICT"
  exit 73
fi

# Re-check provider state after the durable claim and immediately before create.
curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-pods-after-reservation.json
python3 - <<'PY'
import json
p=json.load(open("/tmp/aq27-pods-after-reservation.json"))
xs=p if isinstance(p,list) else p.get("pods") or p.get("items") or []
active=[]
for x in xs:
    name=str(x.get("name") or "")
    status=str(x.get("desiredStatus") or x.get("status") or "")
    if name.startswith("AQLEVON-27B-R0") and status!="EXITED":
        active.append({"id":x.get("id"),"name":name,"status":status})
assert not active,active
print("AQLEVON_27B_POST_RESERVATION_NO_ACTIVE_POD_PASS")
PY

# Verify the exact claim from the remote control branch, not only local files.
git fetch origin ops/runpod-control-v1
git show origin/ops/runpod-control-v1:"$RESERVATION" >/tmp/aq27-reservation-remote.json
git show origin/ops/runpod-control-v1:"$CONSUMED" >/tmp/aq27-consumed-remote.json
python3 .github/runpod-control/aqlevon-27b-reservation.py verify \
  --authorization "$AUTH" --reservation /tmp/aq27-reservation-remote.json --consumed /tmp/aq27-consumed-remote.json \
  --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT" \
  --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID" --require-precreate
echo AQLEVON_27B_DURABLE_PRECREATE_RESERVATION_PASS

BOOT_URL="https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/$GITHUB_SHA/.github/runpod-control/aqlevon-27b-r0-bootstrap.sh"
DOCKER_ARGS="bash -lc 'export AQLEVON_SOURCE_SHA=$GITHUB_SHA; curl -fsSL $BOOT_URL -o /tmp/aq27.sh && chmod +x /tmp/aq27.sh && exec bash /tmp/aq27.sh'"
IMAGE_NAME="ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"

if [ -n "$RESUME_POD_ID" ]; then
  TARGET_POD_ID="$RESUME_POD_ID" AQLEVON_BOOT_URL="$BOOT_URL" AQLEVON_SOURCE_SHA="$GITHUB_SHA" AQLEVON_IMAGE_NAME="$IMAGE_NAME" python3 - <<'PY' >/tmp/aq27-update-body.json
import json,os
script=(
    "export AQLEVON_SOURCE_SHA="+os.environ["AQLEVON_SOURCE_SHA"]+"; "
    "curl -fsSL "+os.environ["AQLEVON_BOOT_URL"]+" -o /tmp/aq27.sh && "
    "chmod +x /tmp/aq27.sh && exec bash /tmp/aq27.sh"
)
body={
  "containerDiskInGb":100,
  "dockerEntrypoint":["bash","-lc"],
  "dockerStartCmd":[script],
  "imageName":os.environ["AQLEVON_IMAGE_NAME"],
  "name":"AQLEVON-27B-R0-BUDGET8",
  "ports":["8000/http"],
  "volumeInGb":100,
  "volumeMountPath":"/workspace"
}
print(json.dumps(body))
PY
  curl -fsS --request PATCH \
    --url "https://rest.runpod.io/v1/pods/$RESUME_POD_ID" \
    --header "Authorization: Bearer $RUNPOD_API_KEY" \
    --header 'Content-Type: application/json' \
    --data-binary @/tmp/aq27-update-body.json >/tmp/aq27-edit-response.json
  TARGET_POD_ID="$RESUME_POD_ID" AQLEVON_IMAGE_NAME="$IMAGE_NAME" python3 - <<'PY'
import json,os
p=json.load(open("/tmp/aq27-edit-response.json"))
assert p.get("id")==os.environ["TARGET_POD_ID"],p
assert str(p.get("image") or p.get("imageName") or "")==os.environ["AQLEVON_IMAGE_NAME"],p
assert int(p.get("containerDiskInGb") or 0)>=100,p
assert int(p.get("volumeInGb") or 0)>=100,p
assert str(p.get("volumeMountPath") or "")=="/workspace",p
print("AQLEVON_27B_STOPPED_POD_REST_UPDATE_PASS",p["id"],p.get("machineId"))
PY

  curl -fsS --request POST \
    --url "https://rest.runpod.io/v1/pods/$RESUME_POD_ID/start" \
    --header "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-create.json
  TARGET_POD_ID="$RESUME_POD_ID" AQLEVON_IMAGE_NAME="$IMAGE_NAME" python3 - <<'PY'
import json,os
p=json.load(open("/tmp/aq27-create.json"))
assert p.get("id")==os.environ["TARGET_POD_ID"],p
img=str(p.get("image") or p.get("imageName") or "")
assert img==os.environ["AQLEVON_IMAGE_NAME"],(img,p)
price=float(p.get("costPerHr") or p.get("adjustedCostPerHr") or 999)
assert price<=1.60,p
open("/tmp/aq27-price","w").write(str(price))
open("/tmp/aq27-resumed-pod","w").write(str(p["id"]))
print("AQLEVON_27B_EXISTING_POD_REST_START_PASS",p["id"],p.get("machineId"),price)
PY
  pod="$(cat /tmp/aq27-resumed-pod)"
  printf '%s' "$pod" >/tmp/aq27-pod
else
  runpodctl pod create     --name AQLEVON-27B-R0-BUDGET8     --image "$IMAGE_NAME"     --gpu-id "NVIDIA A100-SXM4-80GB"     --gpu-count 1     --cloud-type SECURE     --container-disk-in-gb 100     --volume-in-gb 100     --volume-mount-path /workspace     --ports 8000/http     --ssh=false     --docker-args "$DOCKER_ARGS"     --output json >/tmp/aq27-create.json
  python3 - <<'PY'
import json
from pathlib import Path
p=json.load(open("/tmp/aq27-create.json"))
pod=p.get("id") or p.get("podId")
assert pod
Path("/tmp/aq27-pod").write_text(str(pod))
PY
  pod="$(cat /tmp/aq27-pod)"
fi
date +%s >/tmp/aq27-start
python3 .github/runpod-control/aqlevon-27b-reservation.py mark-created \
  --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED" \
  --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT" \
  --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID" --pod-id "$pod"
git add "$RESERVATION" "$CONSUMED"
git commit -m "ops: bind AQLEVON 27B reservation to created pod [skip ci]"
git fetch origin ops/runpod-control-v1
git rebase origin/ops/runpod-control-v1
python3 .github/runpod-control/aqlevon-27b-reservation.py verify \
  --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED" \
  --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT" \
  --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID" --require-created --pod-id "$pod"
git push origin HEAD:ops/runpod-control-v1
echo AQLEVON_27B_PROVIDER_RESOURCE_ID_DURABLY_BOUND

proxy="https://$pod-8000.proxy.runpod.net"
final_stage=""
http_seen=0
last_ok=0
for i in $(seq 1 2900); do
  now="$(date +%s)"
  elapsed=$(( now - $(cat /tmp/aq27-start) ))
  if curl -fsS --connect-timeout 5 --max-time 10 "$proxy/status.json?t=$now" -o /tmp/aq27-status.json 2>/dev/null; then
    http_seen=1
    last_ok="$now"
    stage="$(python3 -c 'import json; print(json.load(open("/tmp/aq27-status.json")).get("stage",""))' 2>/dev/null || true)"
    echo "AQLEVON_27B_STATUS elapsed=$elapsed stage=$stage"
    case "$stage" in DONE|FAILED) final_stage="$stage"; break;; esac
  elif [ "$http_seen" = 1 ] && [ "$last_ok" -gt 0 ] && [ $((now-last_ok)) -gt 180 ]; then
    final_stage="HTTP_LOST"; break
  fi
  if [ "$elapsed" -ge "$MAX_ELAPSED" ]; then final_stage="BUDGET_WINDOW_TIMEOUT"; break; fi
  sleep 5
done
printf '%s\n' "$final_stage" >/tmp/aq27-final-stage

evidence_ok=0
if [ "$final_stage" = "DONE" ] || [ "$final_stage" = "FAILED" ]; then
  for attempt in $(seq 1 8); do
    if curl -fsS --connect-timeout 10 --max-time 240 "$proxy/evidence.tgz" -o /tmp/aq27-r2-evidence.tgz; then
      if python3 .github/runpod-control/verify-aqlevon-27b-evidence.py \
        --archive /tmp/aq27-r2-evidence.tgz \
        --output /tmp/aq27-evidence-verified.json; then
        evidence_ok=1
        break
      fi
    fi
    sleep 3
  done
fi
if [ "$final_stage" = "DONE" ] && [ "$evidence_ok" != 1 ]; then
  final_stage="EVIDENCE_EGRESS_FAILED"
  printf '%s\n' "$final_stage" >/tmp/aq27-final-stage
fi

# Stop GPU billing after egress verification, but retain the pod until
# actions/upload-artifact has completed durably in the next workflow step.
curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-stop.json || true
stopped=1
python3 - <<'PY'
import datetime,hashlib,json,os,tarfile
from pathlib import Path
start=int(Path("/tmp/aq27-start").read_text())
elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-start
price=float(Path("/tmp/aq27-price").read_text())
stage=Path("/tmp/aq27-final-stage").read_text().strip()
out={
 "kind":"AQLEVON_27B_R0_FRESH_AUTH_RUN_RECEIPT_V2",
 "authorization_id":os.environ["AUTH_ID"],
 "scientific_contract_sha256":os.environ["SCIENTIFIC_CONTRACT_SHA256"],
 "source_sha":os.environ["GITHUB_SHA"],
 "final_stage":stage,
 "billed_seconds_estimate":elapsed,
 "rate_per_hour_usd":price,
 "compute_cost_estimate_usd":round(price*elapsed/3600,6),
 "pod_stopped":True,
 "pod_stopped_and_deleted":False,
 "artifact_preservation_state":"PENDING_DURABLE_UPLOAD",
 "sealed_eval_consumed":False
}
p=Path("/tmp/aq27-r2-evidence.tgz")
if p.exists():
    out["evidence_sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        with tarfile.open(p,"r:gz") as t:
            out["candidate_manifest"]=json.loads(t.extractfile("candidate/candidate_manifest.json").read())
            out["training_receipt"]=json.loads(t.extractfile("candidate/training_receipt.json").read())
    except Exception as e:
        out["parse_error"]=repr(e)
v=Path("/tmp/aq27-evidence-verified.json")
if v.exists():
    verification=json.loads(v.read_text())
    out["artifact_verification"]=verification
    out["runtime_versions"]=verification["runtime_versions"]
    out["runtime_versions_sha256"]=verification["runtime_versions_sha256"]
Path(".github/runpod-control/aqlevon-27b-r0-preserve-result-02.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_27B_RUN_RESULT",json.dumps(out,sort_keys=True))
PY

# Do not commit or delete yet. The workflow must first complete durable upload.
# The finalizer records preservation metadata and only then deletes the pod.
trap - EXIT

test "$final_stage" = "DONE"
test "$evidence_ok" = 1
test -s /tmp/aq27-evidence-verified.json
