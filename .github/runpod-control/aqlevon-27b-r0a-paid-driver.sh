#!/usr/bin/env bash
set -uo pipefail

AUTH=.github/runpod-control/aqlevon-27b-r0a-authorization-01.json
TRIGGER=.github/runpod-control/aqlevon-27b-r0a-trigger-01.json
CONSUMED=.github/runpod-control/aqlevon-27b-r0a-consumed-01.json
LIVE=.github/runpod-control/aqlevon-27b-r0a-live-selection-01.json
RESULT=.github/runpod-control/aqlevon-27b-r0a-result-01.json
IMAGE_DIGEST=sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec
POD_NAME=AQLEVON-27B-R0A-BUDGET8-01
pod=""
cleaned=0
final_stage=""
started_epoch=""
rate=""
max_secs=""
evidence=/tmp/aq27-evidence.tgz
status_file=/tmp/aq27-status.json

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing:$1" >&2; return 1; }; }

write_terminal_result() {
  DRIVER_FINAL_STAGE="$final_stage" DRIVER_POD="$pod" DRIVER_CLEANED="$cleaned" DRIVER_STARTED="$started_epoch" DRIVER_RATE="$rate" DRIVER_EVIDENCE="$evidence" python3 - <<'PY'
import datetime,hashlib,json,os,tarfile
from pathlib import Path
a=json.loads(Path(".github/runpod-control/aqlevon-27b-r0a-authorization-01.json").read_text())
s={}
p=Path("/tmp/aq27-status.json")
if p.exists():
    try:s=json.loads(p.read_text())
    except Exception:pass
start=int(os.environ["DRIVER_STARTED"]) if os.environ.get("DRIVER_STARTED","").isdigit() else None
elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-start if start else None
rate=float(os.environ["DRIVER_RATE"]) if os.environ.get("DRIVER_RATE") else None
ep=Path(os.environ["DRIVER_EVIDENCE"])
out={
 "kind":"AQLEVON_27B_R0A_PAID_RUN_RECEIPT_V1",
 "authorization_id":a["authorization_id"],
 "authorization_sha256":a["authorization_sha256"],
 "source_head":a["source_head"],
 "pod_id":os.environ.get("DRIVER_POD") or None,
 "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "final_transport_stage":os.environ.get("DRIVER_FINAL_STAGE") or None,
 "http_status":s,
 "rate_per_hour_usd":rate,
 "billed_seconds_estimate":elapsed,
 "compute_cost_estimate_usd":round(rate*elapsed/3600,6) if rate is not None and elapsed is not None else None,
 "evidence_archive_present":ep.exists(),
 "evidence_archive_sha256":hashlib.sha256(ep.read_bytes()).hexdigest() if ep.exists() else None,
 "pod_stopped_and_deleted":os.environ.get("DRIVER_CLEANED")=="1",
 "single_use_consumed":Path(".github/runpod-control/aqlevon-27b-r0a-consumed-01.json").exists(),
 "sealed_eval_consumed":False,
 "worker05_used_for_tuning":False,
 "capability_gain_claim":False,
}
if ep.exists():
    try:
        with tarfile.open(ep,"r:gz") as t:
            rec=json.loads(t.extractfile("candidate/training_run_receipt.json").read())
        for k in ("candidate_status","public_gate_pass","discovery_dev_gate_pass","public_shadow_gate_pass",
                  "selected_optimizer_updates","selected_phase","dev_pre_successes","dev_post_successes",
                  "dev_gain_tasks","dev_regressions","shadow_pre_successes","shadow_post_successes",
                  "shadow_gain_tasks","shadow_regressions","adapter_state_sha256","adapter_model_sha256",
                  "trainable_parameter_count","peak_vram_allocated_bytes","receipt_sha256"):
            if k in rec: out[k]=rec[k]
    except Exception as e:
        out["artifact_parse_error"]=repr(e)
if out["compute_cost_estimate_usd"] is not None:
    assert out["compute_cost_estimate_usd"] <= float(a["max_total_cost_usd"])+0.08
Path(".github/runpod-control/aqlevon-27b-r0a-result-01.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_27B_TERMINAL_RESULT",json.dumps(out,sort_keys=True))
PY
}

cleanup() {
  rc=$?
  set +e
  if [ -n "$pod" ] && [ "$cleaned" != 1 ]; then
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-stop.json 2>/dev/null || true
    sleep 2
    curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-delete.json 2>/dev/null || true
    for _ in $(seq 1 30); do
      code="$(curl -sS -o /tmp/aq27-final-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" 2>/dev/null || true)"
      if [ "$code" = 404 ]; then cleaned=1; break; fi
      sleep 2
    done
  fi
  write_terminal_result || true
  exit "$rc"
}
trap cleanup EXIT

set -euo pipefail
need curl
need python3
test -n "${RUNPOD_API_KEY:-}"
test -f "$AUTH"
test -f "$TRIGGER"
test ! -e "$CONSUMED"

eval "$(python3 - <<'PY'
import hashlib,json,shlex,subprocess
from pathlib import Path
a=json.loads(Path(".github/runpod-control/aqlevon-27b-r0a-authorization-01.json").read_text())
t=json.loads(Path(".github/runpod-control/aqlevon-27b-r0a-trigger-01.json").read_text())
body={k:v for k,v in a.items() if k!="authorization_sha256"}
h=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert h==a["authorization_sha256"]==t["authorization_sha256"]
assert a["authorization_id"]==t["authorization_id"]=="P4-27B-R0A-BUDGET8-20260927-01"
assert a["single_use"] is True and a["training_authorized"] is True
assert a["model_repo"]=="Qwen/Qwen3.8-27B"
assert a["model_revision"]=="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
assert a["precision"]=="bf16" and a["quantization"]=="none"
assert a["gpu_id"]=="NVIDIA A100-SXM4-80GB"
assert a["max_hourly_rate_usd"]=="1.60"
assert a["max_total_cost_usd"]=="6.50"
assert a["minimum_balance_reserve_usd"]=="0.60"
assert a["observed_account_balance_usd"]=="7.437698534"
assert float(a["max_total_cost_usd"])+float(a["minimum_balance_reserve_usd"])<=float(a["observed_account_balance_usd"])
for path,key in [
 ("research/weight_factory/agent03/p4_27b_progressive_curriculum.py","trainer_blob_sha"),
 (".github/runpod-control/aqlevon-27b-r0a-bootstrap.sh","bootstrap_blob_sha")]:
    data=subprocess.check_output(["git","show",f'{a["source_head"]}:{path}'])
    blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    assert blob==a[key],(path,blob,a[key])
for key in ("source_head","trainer_blob_sha","bootstrap_blob_sha"):
    print(f'{key.upper()}={shlex.quote(str(a[key]))}')
PY
)"
export SOURCE_HEAD TRAINER_BLOB_SHA BOOTSTRAP_BLOB_SHA
echo AQLEVON_27B_AUTH_AND_SOURCE_PASS

curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl version
runpodctl user >/tmp/aq27-user.json
runpodctl pod list --output json >/tmp/aq27-pods.json || echo '[]' >/tmp/aq27-pods.json
runpodctl gpu list --output json >/tmp/aq27-gpus.json

python3 - <<'PY'
import datetime,json
from pathlib import Path
a=json.load(open(".github/runpod-control/aqlevon-27b-r0a-authorization-01.json"))
user=json.load(open("/tmp/aq27-user.json"))
vals=[]
def walk(x):
    if isinstance(x,dict):
        for k,v in x.items():
            nk=str(k).casefold().replace("_","")
            if nk in {"balance","currentbalance","creditbalance","clientbalance"} and isinstance(v,(int,float)) and not isinstance(v,bool):
                vals.append(float(v))
            walk(v)
    elif isinstance(x,list):
        for v in x: walk(v)
walk(user)
uniq=sorted(set(vals))
assert len(uniq)==1,("ambiguous_balance",uniq)
balance=uniq[0]
assert balance>=float(a["max_total_cost_usd"])+float(a["minimum_balance_reserve_usd"]),(balance,a)

try: pods=json.load(open("/tmp/aq27-pods.json"))
except Exception: pods=[]
xs=pods if isinstance(pods,list) else pods.get("pods") or pods.get("items") or pods.get("data") or []
active=[x for x in xs if isinstance(x,dict) and str(x.get("name","")).startswith("AQLEVON-") and str(x.get("desiredStatus") or x.get("status")).upper() in {"RUNNING","STARTING","CREATED"}]
assert not active,active

choices=[]
for g in json.load(open("/tmp/aq27-gpus.json")):
    if str(g.get("gpuId",""))!="NVIDIA A100-SXM4-80GB" or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in g.get("dataCenterAvailability") or []:
        if str(d.get("stockStatus")).lower()!="none" and d.get("dataCenterId"):
            secs=min(int(a["max_billed_seconds"]),int(float(a["max_total_cost_usd"])*3600/price))
            if secs>=10800: choices.append((price,str(d["dataCenterId"]),secs))
assert choices,"no_bounded_A100_SXM_80GB_capacity"
price,dc,secs=sorted(choices)[0]
out={
 "authorization_id":a["authorization_id"],
 "account_balance_before_creation_usd":balance,
 "selected_gpu_id":"NVIDIA A100-SXM4-80GB",
 "selected_datacenter":"UNPINNED_ANY_AVAILABLE",
 "observed_capacity_datacenter":dc,
 "selected_price_hr":price,
 "dynamic_max_billed_seconds":secs,
 "max_total_cost_usd":a["max_total_cost_usd"],
 "minimum_balance_reserve_usd":a["minimum_balance_reserve_usd"],
 "paid_boundary_refresh_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
Path("/tmp/aq27-gpu").write_text("NVIDIA A100-SXM4-80GB")
Path("/tmp/aq27-max-secs").write_text(str(secs))
Path(".github/runpod-control/aqlevon-27b-r0a-live-selection-01.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_27B_PAID_BOUNDARY_PASS",json.dumps(out,sort_keys=True))
PY

rate="$(python3 -c 'import json;print(json.load(open(".github/runpod-control/aqlevon-27b-r0a-live-selection-01.json"))["selected_price_hr"])')"
max_secs="$(cat /tmp/aq27-max-secs)"
BOOT_URL="https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/$SOURCE_HEAD/.github/runpod-control/aqlevon-27b-r0a-bootstrap.sh"
DOCKER_ARGS="bash -lc 'curl -fsSL $BOOT_URL -o /tmp/aq27-bootstrap.sh && chmod +x /tmp/aq27-bootstrap.sh && AQLEVON_SOURCE_HEAD=$SOURCE_HEAD AQLEVON_TRAINER_BLOB=$TRAINER_BLOB_SHA exec bash /tmp/aq27-bootstrap.sh'"

runpodctl pod create --name "$POD_NAME"   --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"   --gpu-id "$(cat /tmp/aq27-gpu)" --gpu-count 1 --cloud-type SECURE   --container-disk-in-gb 100 --ports 8000/http --ssh=false   --docker-args "$DOCKER_ARGS" --output json >/tmp/aq27-create.json

pod="$(python3 - <<'PY'
import json
p=json.load(open("/tmp/aq27-create.json"))
v=p.get("id") or p.get("podId")
assert v,p
print(v)
PY
)"
started_epoch="$(date +%s)"
POD_ID="$pod" STARTED="$started_epoch" python3 - <<'PY'
import datetime,json,os
from pathlib import Path
a=json.load(open(".github/runpod-control/aqlevon-27b-r0a-authorization-01.json"))
sel=json.load(open(".github/runpod-control/aqlevon-27b-r0a-live-selection-01.json"))
out={
 "authorization_id":a["authorization_id"],"authorization_sha256":a["authorization_sha256"],
 "source_head":a["source_head"],"trainer_blob_sha":a["trainer_blob_sha"],
 "bootstrap_blob_sha":a["bootstrap_blob_sha"],"pod_id":os.environ["POD_ID"],
 "created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "single_use_consumed":True,"training_authorized":True,**sel,
}
Path(".github/runpod-control/aqlevon-27b-r0a-consumed-01.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_27B_POD_CREATED")
PY
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$CONSUMED" "$LIVE"
git commit -m "ops: consume authorized 27B R0A budget8 run [skip ci]"
git pull --rebase origin ops/aqlevon-27b-r0a-budget8-20260927
git push origin HEAD:ops/aqlevon-27b-r0a-budget8-20260927

proxy="https://$pod-8000.proxy.runpod.net"
http_seen=0
last_ok=0
for _ in $(seq 1 1600); do
  now="$(date +%s)"
  elapsed=$((now-started_epoch))
  if curl -fsS --connect-timeout 5 --max-time 10 "$proxy/status.json?t=$now" -o "$status_file" 2>/dev/null; then
    http_seen=1; last_ok="$now"
    stage="$(python3 -c 'import json;print(json.load(open("/tmp/aq27-status.json")).get("stage",""))' 2>/dev/null || true)"
    echo "AQLEVON_27B_STATUS elapsed=$elapsed/$max_secs stage=$stage"
    case "$stage" in DONE|FAILED) final_stage="$stage"; break;; esac
  elif [ "$http_seen" = 1 ] && [ "$last_ok" -gt 0 ] && [ $((now-last_ok)) -gt 180 ]; then
    final_stage=HTTP_LOST; break
  fi
  if [ "$http_seen" = 0 ] && [ "$elapsed" -ge 420 ]; then final_stage=HTTP_READINESS_TIMEOUT; break; fi
  if [ "$elapsed" -ge $((max_secs-90)) ]; then final_stage=BILLING_WINDOW_TIMEOUT; break; fi
  sleep 10
done

if [ "$final_stage" = DONE ] || [ "$final_stage" = FAILED ]; then
  curl -fsS --connect-timeout 10 --max-time 900 "$proxy/evidence.tgz" -o "$evidence" || true
fi

curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-stop.json || true
sleep 2
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-delete.json || true
for _ in $(seq 1 45); do
  code="$(curl -sS -o /tmp/aq27-final-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" 2>/dev/null || true)"
  if [ "$code" = 404 ]; then cleaned=1; break; fi
  sleep 2
done
test "$cleaned" = 1
write_terminal_result
trap - EXIT

if [ "$final_stage" != DONE ]; then
  echo "AQLEVON_27B_RUN_NOT_DONE stage=$final_stage" >&2
  exit 92
fi
python3 - <<'PY'
import json
r=json.load(open(".github/runpod-control/aqlevon-27b-r0a-result-01.json"))
assert r.get("evidence_archive_present") is True,r
print("AQLEVON_27B_RUN_DONE_EVIDENCE_PRESENT")
PY
