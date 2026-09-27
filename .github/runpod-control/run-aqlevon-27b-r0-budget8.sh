#!/usr/bin/env bash
set -euo pipefail

AUTH=.github/runpod-control/aqlevon-27b-r0-preserve-authorization-02.json
CONSUMED=.github/runpod-control/aqlevon-27b-r0-preserve-consumed-02.json
RESULT=.github/runpod-control/aqlevon-27b-r0-preserve-result-02.json
IMAGE_DIGEST=sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec
AUTH_ID=P4-AQLEVON-27B-R0-PRESERVE-20260927-02
MAX_ELAPSED=3000
pod=""
cleaned=0

cleanup() {
  status=$?
  if [ -n "$pod" ] && [ "$cleaned" != 1 ]; then
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-exit-stop.json || true
    sleep 2
    curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-exit-delete.json || true
  fi
  exit "$status"
}
trap cleanup EXIT

test -n "${RUNPOD_API_KEY:-}"
test -f "$AUTH"
test ! -e "$CONSUMED"
python3 -m py_compile research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py
bash -n .github/runpod-control/aqlevon-27b-r0-bootstrap.sh
echo AQLEVON_27B_FREE_SYNTAX_PREFLIGHT_PASS

python3 - <<'PY'
import json
a=json.load(open(".github/runpod-control/aqlevon-27b-r0-preserve-authorization-02.json"))
assert a["authorization_id"]=="P4-AQLEVON-27B-R0-PRESERVE-20260927-02"
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
print("AQLEVON_27B_AUTHORIZATION_PASS")
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

curl -sSL https://cli.runpod.net | sudo bash >/dev/null
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

BOOT_URL="https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/$GITHUB_SHA/.github/runpod-control/aqlevon-27b-r0-bootstrap.sh"
DOCKER_ARGS="bash -lc 'export AQLEVON_SOURCE_SHA=$GITHUB_SHA; curl -fsSL $BOOT_URL -o /tmp/aq27.sh && chmod +x /tmp/aq27.sh && exec bash /tmp/aq27.sh'"
runpodctl pod create   --name AQLEVON-27B-R0-BUDGET8   --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"   --gpu-id "NVIDIA A100-SXM4-80GB"   --gpu-count 1   --cloud-type SECURE   --container-disk-in-gb 100   --ports 8000/http   --ssh=false   --docker-args "$DOCKER_ARGS"   --output json >/tmp/aq27-create.json

python3 - <<'PY'
import datetime,json,os,time
from pathlib import Path
p=json.load(open("/tmp/aq27-create.json"))
pod=p.get("id") or p.get("podId")
assert pod
Path("/tmp/aq27-pod").write_text(str(pod))
Path("/tmp/aq27-start").write_text(str(int(time.time())))
out={
 "authorization_id":"P4-AQLEVON-27B-R0-PRESERVE-20260927-02",
 "pod_id":pod,
 "source_sha":os.environ["GITHUB_SHA"],
 "created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "single_use_consumed":True,
 "max_total_cost_usd":1.50,
 "controller_budget_window_seconds":3000
}
Path(".github/runpod-control/aqlevon-27b-r0-preserve-consumed-02.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
PY
pod="$(cat /tmp/aq27-pod)"
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$CONSUMED"
git commit -m "ops: consume AQLEVON 27B R0 budget8 authorization [skip ci]"
git fetch origin ops/runpod-control-v1
git rebase origin/ops/runpod-control-v1
git push origin HEAD:ops/runpod-control-v1

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
      if python3 - <<'PY'
import tarfile
from pathlib import Path
p=Path("/tmp/aq27-r2-evidence.tgz")
assert p.exists() and p.stat().st_size > 0
with tarfile.open(p,"r:gz") as t:
    names=set(t.getnames())
required={
    "candidate/candidate_manifest.json",
    "candidate/training_receipt.json",
    "candidate/adapter/adapter_model.safetensors",
    "candidate/adapter/adapter_config.json",
}
missing=required-names
assert not missing, missing
print("AQLEVON_27B_R2_EVIDENCE_ARCHIVE_VERIFIED", p.stat().st_size)
PY
      then
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

curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-stop.json || true
sleep 3
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-delete.json || true
for i in $(seq 1 45); do
  code="$(curl -sS -o /tmp/aq27-final.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  if [ "$code" = 404 ]; then cleaned=1; break; fi
  sleep 2
done
test "$cleaned" = 1

python3 - <<'PY'
import datetime,hashlib,json,os,tarfile
from pathlib import Path
start=int(Path("/tmp/aq27-start").read_text())
elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-start
price=float(Path("/tmp/aq27-price").read_text())
stage=Path("/tmp/aq27-final-stage").read_text().strip()
out={
 "kind":"AQLEVON_27B_R0_PRESERVE_RUN_RECEIPT_V1",
 "authorization_id":"P4-AQLEVON-27B-R0-PRESERVE-20260927-02",
 "source_sha":os.environ["GITHUB_SHA"],
 "final_stage":stage,
 "billed_seconds_estimate":elapsed,
 "rate_per_hour_usd":price,
 "compute_cost_estimate_usd":round(price*elapsed/3600,6),
 "pod_stopped_and_deleted":True,
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
Path(".github/runpod-control/aqlevon-27b-r0-preserve-result-02.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_27B_RUN_RESULT",json.dumps(out,sort_keys=True))
PY

git add "$RESULT"
git commit -m "ops: record AQLEVON 27B R0 budget8 result [skip ci]" || true
git fetch origin ops/runpod-control-v1
git rebase origin/ops/runpod-control-v1
git push origin HEAD:ops/runpod-control-v1
trap - EXIT

test "$final_stage" = "DONE"
