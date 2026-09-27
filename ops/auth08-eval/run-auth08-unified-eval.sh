#!/usr/bin/env bash
set -euo pipefail

COMMAND=ops/auth08-eval/command.json
AUTH=ops/auth08-eval/authorization.json
CLAIMS_DIR=ops/auth08-eval/claims
RESULT=ops/auth08-eval/result.json
IMAGE_DIGEST=sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec
IMAGE_NAME="ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"
MAX_ELAPSED=3300

action="$(python3 -c 'import json; print(json.load(open("'"$COMMAND"'")).get("action",""))')"
if [ "$action" != "execute_auth08_unified_public_eval" ]; then
  echo AQLEVON_AUTH08_EVAL_COMMAND_NOT_REQUESTED
  exit 0
fi

test -n "$RUNPOD_API_KEY"
test -n "$GH_TOKEN"
test -f "$AUTH"

AUTH_ID="$(python3 - <<'PY'
import json
a=json.load(open("ops/auth08-eval/authorization.json"))
print(a["authorization_id"])
PY
)"
export AUTH_ID
RESERVATION="$CLAIMS_DIR/$AUTH_ID.reservation.json"
CONSUMED="$CLAIMS_DIR/$AUTH_ID.consumed.json"
test ! -e "$RESERVATION"
test ! -e "$CONSUMED"

python3 ops/auth08-eval/eval-reservation.py reserve   --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED"   --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT"   --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID"

git config user.name "aqlevon-manager-bot"
git config user.email "aqlevon-manager-bot@users.noreply.github.com"
git add "$RESERVATION" "$CONSUMED"
git commit -m "eval: reserve Auth08 public eval authorization [skip ci]"
git fetch origin manager/auth08-unified-eval-20260927
git rebase origin/manager/auth08-unified-eval-20260927
python3 ops/auth08-eval/eval-reservation.py verify   --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED"   --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT"   --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID"
git push origin HEAD:manager/auth08-unified-eval-20260927
echo AQLEVON_AUTH08_EVAL_RESERVATION_DURABLE_BEFORE_PROVIDER_CREATE

curl -fsS https://rest.runpod.io/v1/pods   -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pods.json
python3 - <<'PY'
import json
p=json.load(open("/tmp/pods.json"))
xs=p if isinstance(p,list) else p.get("pods") or p.get("items") or []
active=[]
for x in xs:
    name=str(x.get("name") or "")
    status=str(x.get("desiredStatus") or x.get("status") or "")
    if name.startswith("AQLEVON-AUTH08-EVAL") and status!="EXITED":
        active.append({"id":x.get("id"),"name":name,"status":status})
assert not active,active
print("AQLEVON_AUTH08_EVAL_NO_ACTIVE_POD_PASS")
PY

RUNPODCTL_URL="https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64"
for attempt in 1 2 3 4 5; do
  if curl -fL --retry 2 --retry-all-errors --connect-timeout 10 --max-time 90 "$RUNPODCTL_URL" -o /tmp/runpodctl; then break; fi
  rm -f /tmp/runpodctl
  sleep $((attempt*2))
done
test -s /tmp/runpodctl
sudo install -m 0755 /tmp/runpodctl /usr/local/bin/runpodctl
runpodctl version

runpodctl gpu list --output json >/tmp/gpus.json
python3 - <<'PY' >/tmp/capacity.env
import json
choices=[]
for g in json.load(open("/tmp/gpus.json")):
    if str(g.get("gpuId"))!="NVIDIA A100-SXM4-80GB" or not g.get("secureCloud"):
        continue
    price=float(g.get("securePricePerHr") or 999)
    if price>1.60: continue
    for d in g.get("dataCenterAvailability") or []:
        if str(d.get("stockStatus") or "").lower()=="none" or not d.get("dataCenterId"): continue
        choices.append((price,str(d["dataCenterId"]),str(d.get("stockStatus"))))
assert choices,"no_a100_secure_capacity_under_ceiling"
price,dc,stock=sorted(choices)[0]
print(f"PRICE={price}")
print(f"DC={dc}")
print(f"STOCK={stock}")
PY
cat /tmp/capacity.env
. /tmp/capacity.env
export PRICE DC STOCK
python3 - <<'PY'
import os
price=float(os.environ["PRICE"])
assert price<=1.60
assert price*3300/3600<=1.50
print("AQLEVON_AUTH08_EVAL_CAPACITY_BUDGET_PASS",price,os.environ["DC"],os.environ["STOCK"])
PY

rm -rf /tmp/auth08-candidate /tmp/genprep /tmp/pairprep /tmp/auth08-evidence /tmp/auth08-bundle
mkdir -p /tmp/auth08-candidate /tmp/genprep /tmp/pairprep /tmp/auth08-evidence /tmp/auth08-bundle

gh run download 36332132785 -n aqlevon-27b-r0-preserve-36332132785 -D /tmp/auth08-candidate
gh run download 36338123679 -n aqlevon-auth08-generalization-eval-prep -D /tmp/genprep
gh run download 36338128347 -n aqlevon-auth08-paired-public-eval-prep -D /tmp/pairprep

EVIDENCE="$(find /tmp/auth08-candidate -type f -name 'aq27-r2-evidence.tgz' | head -n1)"
test -n "$EVIDENCE"
test "$(sha256sum "$EVIDENCE" | awk '{print $1}')" = "335ece52ae8aae5c41ad92cc964880fea583e4a2e834b879200d053e162a969b"
tar -xzf "$EVIDENCE" -C /tmp/auth08-evidence
ADAPTER_FILE="$(find /tmp/auth08-evidence -type f -path '*/adapter/adapter_model.safetensors' | head -n1)"
test -n "$ADAPTER_FILE"
test "$(sha256sum "$ADAPTER_FILE" | awk '{print $1}')" = "5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74"
ADAPTER_DIR="$(dirname "$ADAPTER_FILE")"
CANDIDATE_MANIFEST="$(find /tmp/auth08-evidence -type f -name candidate_manifest.json | head -n1)"
test -n "$CANDIDATE_MANIFEST"

cp -a "$ADAPTER_DIR" /tmp/auth08-bundle/adapter
cp "$CANDIDATE_MANIFEST" /tmp/auth08-bundle/candidate_manifest.json
cp /tmp/genprep/auth08-generalization-manifest.json /tmp/auth08-bundle/
cp /tmp/genprep/auth08-generalization-results-skeleton.json /tmp/auth08-bundle/
cp /tmp/pairprep/auth08-paired-public-execution-plan.json /tmp/auth08-bundle/
cp /tmp/pairprep/auth08-paired-public-binding.json /tmp/auth08-bundle/
cp research/evaluation/auth08_unified_public_eval_runner_v1.py /tmp/auth08-bundle/
cp research/weight_factory/agent04/aqlevon_27b_public_generalization_challenge_v1.py /tmp/auth08-bundle/

BUNDLE="/tmp/aqlevon-auth08-eval-bundle-$GITHUB_RUN_ID.tgz"
tar -czf "$BUNDLE" -C /tmp/auth08-bundle .
BUNDLE_SHA="$(sha256sum "$BUNDLE" | awk '{print $1}')"
echo "$BUNDLE_SHA" >/tmp/bundle.sha

: >/tmp/send.log
(
  set +e
  runpodctl send "$BUNDLE" 2>&1 | tee /tmp/send.log
  echo "${PIPESTATUS[0]}" >/tmp/send.rc
) &
SEND_PID=$!
TRANSFER_CODE=""
for _ in $(seq 1 120); do
  TRANSFER_CODE="$(sed -n 's/.*code is:[[:space:]]*//p' /tmp/send.log | head -n1 | tr -d '\r\n')"
  if [ -n "$TRANSFER_CODE" ]; then break; fi
  if ! kill -0 "$SEND_PID" 2>/dev/null; then
    cat /tmp/send.log
    exit 31
  fi
  sleep 1
done
test -n "$TRANSFER_CODE"
echo AQLEVON_AUTH08_EVAL_TRANSFER_CODE_READY

BOOT_URL="https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/$GITHUB_SHA/ops/auth08-eval/bootstrap.sh"
DOCKER_ARGS="bash -lc 'export AQLEVON_TRANSFER_CODE=$TRANSFER_CODE AQLEVON_BUNDLE_SHA256=$BUNDLE_SHA AQLEVON_SOURCE_SHA=$GITHUB_SHA; curl -fsSL $BOOT_URL -o /tmp/aqeval.sh && chmod +x /tmp/aqeval.sh && exec bash /tmp/aqeval.sh'"

runpodctl pod create   --name AQLEVON-AUTH08-EVAL   --image "$IMAGE_NAME"   --gpu-id "NVIDIA A100-SXM4-80GB"   --gpu-count 1   --cloud-type SECURE   --container-disk-in-gb 100   --volume-in-gb 100   --volume-mount-path /workspace   --ports 8000/http   --ssh=false   --docker-args "$DOCKER_ARGS"   --output json >/tmp/create.json

python3 - <<'PY'
import json
p=json.load(open("/tmp/create.json"))
pod=p.get("id") or p.get("podId")
assert pod,p
open("/tmp/pod","w").write(str(pod))
PY
pod="$(cat /tmp/pod)"
date +%s >/tmp/start

python3 ops/auth08-eval/eval-reservation.py mark-created   --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED"   --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT"   --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID" --pod-id "$pod"
git add "$RESERVATION" "$CONSUMED"
git commit -m "eval: bind Auth08 public eval reservation to pod [skip ci]"
git fetch origin manager/auth08-unified-eval-20260927
git rebase origin/manager/auth08-unified-eval-20260927
python3 ops/auth08-eval/eval-reservation.py verify   --authorization "$AUTH" --reservation "$RESERVATION" --consumed "$CONSUMED"   --run-id "$GITHUB_RUN_ID" --run-attempt "$GITHUB_RUN_ATTEMPT"   --source-sha "$GITHUB_SHA" --expected-authorization-id "$AUTH_ID" --pod-id "$pod"
git push origin HEAD:manager/auth08-unified-eval-20260927
echo AQLEVON_AUTH08_EVAL_PROVIDER_RESOURCE_ID_DURABLY_BOUND

proxy="https://$pod-8000.proxy.runpod.net"
final_stage=""
http_seen=0
last_ok=0
for _ in $(seq 1 700); do
  now="$(date +%s)"
  elapsed=$((now-$(cat /tmp/start)))
  if curl -fsS --connect-timeout 5 --max-time 10 "$proxy/status.json?t=$now" -o /tmp/status.json 2>/dev/null; then
    http_seen=1
    last_ok="$now"
    stage="$(python3 -c 'import json; print(json.load(open("/tmp/status.json")).get("stage",""))' 2>/dev/null || true)"
    echo "AQLEVON_AUTH08_EVAL_STATUS elapsed=$elapsed stage=$stage"
    case "$stage" in DONE|FAILED) final_stage="$stage"; break;; esac
  elif [ "$http_seen" = 1 ] && [ "$last_ok" -gt 0 ] && [ $((now-last_ok)) -gt 180 ]; then
    final_stage="HTTP_LOST"; break
  fi
  if [ "$elapsed" -ge "$MAX_ELAPSED" ]; then final_stage="BUDGET_WINDOW_TIMEOUT"; break; fi
  sleep 5
done
echo "$final_stage" >/tmp/final-stage

evidence_ok=0
if [ "$final_stage" = "DONE" ]; then
  curl -fsS --retry 5 --retry-all-errors --connect-timeout 10 --max-time 120 "$proxy/evidence.tgz" -o /tmp/auth08-eval-evidence.tgz
  test -s /tmp/auth08-eval-evidence.tgz
  evidence_ok=1
fi

runpodctl pod stop "$pod" || true
echo "$pod" >/tmp/stopped-pod

if [ "$evidence_ok" != 1 ]; then
  echo "AQLEVON_AUTH08_EVAL_STOPPED_WITHOUT_DELETE final_stage=$final_stage pod=$pod"
  exit 41
fi

rm -rf /tmp/eval-return
mkdir -p /tmp/eval-return
tar -xzf /tmp/auth08-eval-evidence.tgz -C /tmp/eval-return
test -f /tmp/eval-return/results/generalization-results.json
test -f /tmp/eval-return/results/paired-public-results.jsonl
test -f /tmp/eval-return/results/runtime-receipt.json

python3 research/weight_factory/agent04/aqlevon_27b_public_generalization_result_harness_v1.py score   --manifest /tmp/eval-return/bundle/auth08-generalization-manifest.json   --results /tmp/eval-return/results/generalization-results.json   --out /tmp/generalization-score.json

python3 research/weight_factory/agent03/aqlevon_27b_rerun_contract_v1.py score   --results-jsonl /tmp/eval-return/results/paired-public-results.jsonl   --output /tmp/paired-public-score.json

python3 - <<'PY'
import json,time,hashlib,os
g=json.load(open("/tmp/generalization-score.json"))
p=json.load(open("/tmp/paired-public-score.json"))
r=json.load(open("/tmp/eval-return/results/runtime-receipt.json"))
start=int(open("/tmp/start").read()); elapsed=max(0,int(time.time())-start)
price=float(os.environ["PRICE"])
verdict={
 "kind":"AQLEVON_AUTH08_COMBINED_PUBLIC_EVAL_VERDICT_V1",
 "generalization_support_observed":bool(g["support_observed"]),
 "generalization_delta":g["primary_delta_candidate_minus_base"],
 "generalization_p":g["paired_one_sided_exact_sign_binomial_p"]["fraction"],
 "paired_public_pass":bool(p["paired_public_pass"]),
 "paired_public_strict_gain_observed":bool(p["strict_gain_observed"]),
 "paired_public_delta":p["delta"],
 "runtime_receipt_sha256":r["receipt_sha256"],
 "billed_seconds_estimate":elapsed,
 "rate_per_hour_usd":price,
 "compute_cost_estimate_usd":round(price*elapsed/3600,6),
 "sealed_eval_consumed":False,
 "truth_boundary":"Public independent/generalization evidence only; not historical W05 sealed promotion authority."
}
verdict["public_support_pass"]=verdict["generalization_support_observed"] and verdict["paired_public_pass"]
raw=json.dumps(verdict,sort_keys=True,separators=(",",":")).encode()
verdict["verdict_sha256"]=hashlib.sha256(raw).hexdigest()
open("/tmp/combined-public-eval-verdict.json","w").write(json.dumps(verdict,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH08_PUBLIC_EVAL_VERDICT",json.dumps(verdict,sort_keys=True))
PY

cp /tmp/generalization-score.json /tmp/paired-public-score.json /tmp/combined-public-eval-verdict.json /tmp/eval-return/
tar -czf /tmp/auth08-public-eval-final-evidence.tgz -C /tmp/eval-return .
sha256sum /tmp/auth08-public-eval-final-evidence.tgz >/tmp/auth08-public-eval-final-evidence.sha256

python3 - <<'PY'
import json,os
v=json.load(open("/tmp/combined-public-eval-verdict.json"))
out={
 "kind":"AQLEVON_AUTH08_PUBLIC_EVAL_RUN_RECEIPT_V1",
 "authorization_id":os.environ["AUTH_ID"],
 "pod_id":open("/tmp/pod").read().strip(),
 "final_stage":"DONE",
 "artifact_preservation_state":"PENDING_DURABLE_UPLOAD",
 "evidence_sha256":open("/tmp/auth08-public-eval-final-evidence.sha256").read().split()[0],
 "verdict":v,
}
open("ops/auth08-eval/result.json","w").write(json.dumps(out,indent=2,sort_keys=True)+"\n")
PY

git add "$RESULT"
git commit -m "eval: record Auth08 public-eval result pending durable upload [skip ci]"
git fetch origin manager/auth08-unified-eval-20260927
git rebase origin/manager/auth08-unified-eval-20260927
git push origin HEAD:manager/auth08-unified-eval-20260927

echo AQLEVON_AUTH08_EVAL_RESULT_READY_FOR_DURABLE_UPLOAD
