#!/usr/bin/env bash
set -uo pipefail

AUTH_ID="P4-ONE-DAY-PUBLIC-PASSN-20260925-02"
AUTH_SHA="430ae3149249d9522aa027a852bde786f5ef4a97d252781fea15080483e467c6"
SOURCE_HEAD="c7b859f0a5459c1a79ea6fa96ca4adafe17599b6"
W02_HEAD="abb94ef134e2e97036b6959dbc9db4278d3736b6"
IMAGE_DIGEST="sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec"
AUTH=".github/runpod-control/one-day-public-probe-manager-authorization-02-20260925.json"
FREE=".github/runpod-control/one-day-public-probe-free-result-02.json"
TRIGGER=".github/runpod-control/execute-one-day-public-probe-02.json"
CONSUMED=".github/runpod-control/one-day-public-probe-consumed-02.json"
RESULT=".github/runpod-control/one-day-public-probe-run-result-02.json"
REMOTE_SCRIPT=".github/runpod-control/remote-one-day-public-probe-02.sh"

die(){ echo "FAIL_CLOSED_ONE_DAY $*" >&2; exit 1; }

# ---- free/pre-spend contract ----
test -n "${RUNPOD_API_KEY:-}" || die no_runpod_key
test ! -e "$CONSUMED" || die authorization_already_consumed
python3 - <<'PY' || exit 1
import hashlib,json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-public-probe-manager-authorization-02-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/one-day-public-probe-free-result-02.json").read_text())
t=json.loads(Path(".github/runpod-control/execute-one-day-public-probe-02.json").read_text())
raw={k:v for k,v in a.items() if k!="authorization_sha256"}
sha=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert sha==a["authorization_sha256"]==f["authorization_sha256"]==t["authorization_sha256"]=="430ae3149249d9522aa027a852bde786f5ef4a97d252781fea15080483e467c6"
assert a["authorization_id"]==f["authorization_id"]==t["authorization_id"]=="P4-ONE-DAY-PUBLIC-PASSN-20260925-02"
assert a["expected_source_head"]==f["source_head"]==t["expected_source_head"]=="c7b859f0a5459c1a79ea6fa96ca4adafe17599b6"
assert a["training_authorized"] is False and a["sealed_eval_consumed"] is False and a["worker05_used_for_tuning"] is False
assert a["single_use"] is True and f["paid_resource_created"] is False and not f["active_aqlevon_pods"]
assert float(a["prior_mission_spend_usd"])+float(a["max_total_cost_usd"]) < float(a["mission_max_total_usd"])
print("AQLEVON_ONE_DAY_AUTH02_PRESPEND_PASS",sha)
PY

remote_head="$(git ls-remote https://github.com/$GITHUB_REPOSITORY.git refs/heads/agent/03-one-day-verified-trajectory-20260925 | cut -f1)"
test "$remote_head" = "$SOURCE_HEAD" || die source_head_moved

# Stage exact source + public-only verifier bytes before billing.
git fetch -q origin "$SOURCE_HEAD" "$W02_HEAD" || die git_fetch_failed
mkdir -p /tmp/probe-payload
git show "$SOURCE_HEAD":research/weight_factory/agent03/p4_one_day_verified_trajectory_probe.py >/tmp/probe-payload/probe.py || die probe_stage_failed
git show "$W02_HEAD":research/weight_factory/agent02/gene1_data_verifier_pack_v1.py >/tmp/probe-payload/w02.py || die w02_stage_failed
git show "$W02_HEAD":research/weight_factory/agent02/gene1_training_visible_pack_v1.json >/tmp/probe-payload/public-pack.json || die pack_stage_failed
cp "$REMOTE_SCRIPT" /tmp/probe-payload/remote-runner.sh
printf '%s\n' "$SOURCE_HEAD" >/tmp/probe-payload/source_head.txt
python3 -m py_compile /tmp/probe-payload/probe.py || die probe_compile_failed
python3 /tmp/probe-payload/probe.py --self-test || die probe_selftest_failed
python3 - <<'PY' || exit 1
import json
from pathlib import Path
p=json.load(open("/tmp/probe-payload/public-pack.json"))
assert p["pack_kind"]=="AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1"
assert p["pack_sha256"]=="35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
tasks=[t for t in p["tasks"] if t.get("verifier_mode")=="hardened" and t.get("training_eligible") is True]
assert len(tasks)==56
assert all("eval" not in str(t.get("semantic_core_id","")).lower() for t in tasks)
probe=Path("/tmp/probe-payload/probe.py").read_text()
for forbidden in ("gene1_sealed_eval_pack_PRIVATE_v1.json","gene1_eval_secret_v1.key"):
    assert forbidden not in probe
print("AQLEVON_ONE_DAY_PUBLIC_PAYLOAD_PASS",len(tasks))
PY
sha256sum /tmp/probe-payload/* | tee /tmp/probe-payload-sha256.txt
tar -czf /tmp/aqlevon-one-day-probe-payload.tgz -C /tmp/probe-payload .
test "$(stat -c %s /tmp/aqlevon-one-day-probe-payload.tgz)" -lt 20000000 || die payload_too_large
echo AQLEVON_ONE_DAY_SOURCE_STAGED_BEFORE_BILLING

# Fresh live no-duplicate check. Bind to the free-sealed GPU/DC; if stock vanished, fail with no Pod.
curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pre-pods.json || die pod_inventory_failed
python3 - <<'PY' || exit 1
import json
pods=json.load(open("/tmp/pre-pods.json")); pods=pods if isinstance(pods,list) else pods.get("pods") or pods.get("items") or []
active=[p for p in pods if str(p.get("name","")).startswith("AQLEVON-") and str(p.get("desiredStatus") or p.get("status"))!="EXITED"]
assert not active,active
print("AQLEVON_ONE_DAY_NO_ACTIVE_PODS_PASS")
PY
curl -sSL https://cli.runpod.net | sudo bash >/dev/null || die runpodctl_install_failed
runpodctl gpu list --output json >/tmp/pre-gpus.json || die gpu_inventory_failed
python3 - <<'PY' || exit 1
import json
a=json.load(open(".github/runpod-control/one-day-public-probe-manager-authorization-02-20260925.json"))
f=json.load(open(".github/runpod-control/one-day-public-probe-free-result-02.json"))
gpu=f["selected_gpu_id"]; dc=f["selected_datacenter"]; sealed_price=float(f["selected_price_hr"])
allowed=set(a["permitted_gpu_ids"]); assert gpu in allowed and sealed_price<=float(a["max_hourly_rate_usd"])
found=False
for g in json.load(open("/tmp/pre-gpus.json")):
    if g.get("gpuId")!=gpu or not g.get("secureCloud"): continue
    if float(g.get("securePricePerHr") or 999)>float(a["max_hourly_rate_usd"]): continue
    for d in (g.get("dataCenterAvailability") or []):
        if d.get("dataCenterId")==dc and str(d.get("stockStatus")).lower()!="none": found=True
assert found,(gpu,dc,"stock_vanished")
open("/tmp/selected_gpu","w").write(gpu)
open("/tmp/selected_dc","w").write(dc)
open("/tmp/selected_rate","w").write(str(sealed_price))
print("AQLEVON_ONE_DAY_EXACT_CAPACITY_RECHECK_PASS",gpu,dc,sealed_price)
PY

# ---- paid boundary ----
ssh-keygen -q -t ed25519 -N '' -f /tmp/probe_key || die ssh_key_failed
PUBKEY="$(cat /tmp/probe_key.pub)"; export PUBKEY
env_json="$(python3 - <<'PY'
import json,os
print(json.dumps({"PUBLIC_KEY":os.environ["PUBKEY"]},separators=(",",":")))
PY
)"
runpodctl pod create --name AQLEVON-ONE-DAY-PASSN-02-20260925   --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"   --gpu-id "$(cat /tmp/selected_gpu)" --gpu-count 1 --cloud-type SECURE   --data-center-ids "$(cat /tmp/selected_dc)" --container-disk-in-gb 40   --ports 22/tcp --env "$env_json" --output json >/tmp/create.json
create_rc=$?
test "$create_rc" -eq 0 || die pod_create_failed_no_authorization_consumed
pod="$(python3 - <<'PY'
import json
p=json.load(open("/tmp/create.json")); print(p.get("id") or p.get("podId") or "")
PY
)"
test -n "$pod" || die pod_id_missing
printf '%s' "$pod" >/tmp/pod_id
date +%s >/tmp/pod_created_epoch
echo "AQLEVON_ONE_DAY_POD_CREATED $pod"

# Authorization becomes consumed immediately after Pod exists.
python3 - <<'PY'
import datetime,json
from pathlib import Path
out={"authorization_id":"P4-ONE-DAY-PUBLIC-PASSN-20260925-02","authorization_sha256":"430ae3149249d9522aa027a852bde786f5ef4a97d252781fea15080483e467c6",
     "source_head":"c7b859f0a5459c1a79ea6fa96ca4adafe17599b6","image_digest":"sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec",
     "pod_id":Path("/tmp/pod_id").read_text().strip(),"created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "single_use_consumed":True,"training_authorized":False}
Path(".github/runpod-control/one-day-public-probe-consumed-02.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
PY
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$CONSUMED"
git commit -m "ops: consume one-day public probe authorization [skip ci]" || die consumed_commit_failed
git pull --rebase origin ops/one-day-verified-trajectory-20260925 || die consumed_rebase_failed
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || die consumed_push_failed

final_rc=255
probe_rc=255
result_ok=0
stop_ok=0
deleted=0

# Readiness (max five billed minutes).
ready=0
for i in $(seq 1 60); do
  curl -sS "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pod.json || true
  python3 - <<'PY'
import json,sys
try:p=json.load(open("/tmp/pod.json"))
except Exception:sys.exit(1)
rate=float(p.get("costPerHr") or 999)
if rate>3.50: sys.exit(2)
ip=p.get("publicIp"); port=(p.get("portMappings") or {}).get("22")
if p.get("desiredStatus")=="RUNNING" and ip and port:
    open("/tmp/ssh_target","w").write(str(ip)+"|"+str(port)); open("/tmp/live_rate","w").write(str(rate)); sys.exit(0)
sys.exit(1)
PY
  s=$?
  if [ "$s" -eq 0 ]; then ready=1; break; fi
  if [ "$s" -eq 2 ]; then final_rc=97; break; fi
  elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch) ))
  [ "$elapsed" -lt 300 ] || break
  sleep 5
done

if [ "$ready" -eq 1 ]; then
  rate="$(cat /tmp/live_rate)"
  dynamic="$(python3 - <<PY
rate=float("$rate")
print(min(1200,int(1.20*3600/rate)))
PY
)"
  printf '%s' "$dynamic" >/tmp/dynamic_seconds
  host="$(cut -d'|' -f1 /tmp/ssh_target)"; port="$(cut -d'|' -f2 /tmp/ssh_target)"
  cat >/tmp/hardware.py <<'PY'
import subprocess,torch
name=subprocess.check_output(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],text=True).splitlines()[0].strip()
total=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],text=True).splitlines()[0])
assert total>=40000,(name,total)
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(),name
print("AQLEVON_ONE_DAY_HARDWARE_PASS",name,total)
PY
  scp -q -i /tmp/probe_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/hardware.py root@"$host":/tmp/hardware.py
  hw_scp=$?
  if [ "$hw_scp" -eq 0 ]; then
    ssh -i /tmp/probe_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" python3 /tmp/hardware.py
    hw_rc=$?
  else hw_rc=91; fi
  if [ "$hw_rc" -eq 0 ]; then
    scp -q -i /tmp/probe_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null       /tmp/aqlevon-one-day-probe-payload.tgz root@"$host":/tmp/aqlevon-one-day-probe-payload.tgz
    payload_rc=$?
    if [ "$payload_rc" -eq 0 ]; then
      scp -q -i /tmp/probe_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null         "$REMOTE_SCRIPT" root@"$host":/tmp/run-one-day-probe.sh
      payload_rc=$?
    fi
    if [ "$payload_rc" -eq 0 ]; then
      ssh -i /tmp/probe_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"         'rm -f /workspace/one_day_probe.rc; nohup setsid bash /tmp/run-one-day-probe.sh >/workspace/one_day_probe-supervisor.log 2>&1 < /dev/null &'
      launch_rc=$?
    else launch_rc=92; fi
    if [ "$launch_rc" -eq 0 ]; then
      echo AQLEVON_ONE_DAY_REMOTE_START
      for i in $(seq 1 120); do
        if ssh -i /tmp/probe_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 root@"$host"           'test -s /workspace/one_day_probe.rc' >/dev/null 2>&1; then
          probe_rc="$(ssh -i /tmp/probe_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" 'cat /workspace/one_day_probe.rc' | tail -n1)"
          break
        fi
        elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch) ))
        if [ "$elapsed" -gt $((dynamic-60)) ]; then probe_rc=125; echo "FAIL_CLOSED_ONE_DAY_BILLING_WATCHDOG seconds=$elapsed"; break; fi
        sleep 8
      done
      [[ "$probe_rc" =~ ^[0-9]+$ ]] || probe_rc=255
      for attempt in 1 2 3 4; do
        scp -q -i /tmp/probe_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null           root@"$host":/workspace/one_day_probe/probe.log /tmp/probe.log 2>/tmp/probe-log-copy.err && break
        sleep 2
      done
      for attempt in 1 2 3 4; do
        scp -q -i /tmp/probe_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null           root@"$host":/workspace/one_day_probe/result.json /tmp/probe-result.json 2>/tmp/probe-result-copy.err && break
        sleep 2
      done
      if [ "$probe_rc" -eq 0 ] && [ -s /tmp/probe-result.json ] && [ -s /tmp/probe.log ]; then result_ok=1; final_rc=0
      else final_rc="$probe_rc"; fi
    else final_rc="$launch_rc"; fi
  else final_rc="$hw_rc"; fi
else
  [ "$final_rc" -ne 255 ] || final_rc=90
fi
printf '%s\n' "$probe_rc" >/tmp/probe_remote_rc
printf '%s\n' "$final_rc" >/tmp/probe_final_rc

# Always stop; delete only after durable result/log egress.
for i in $(seq 1 20); do
  curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/stop.json || true
  sleep 3
  curl -sS "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/stop-probe.json || true
  if python3 - <<'PY'
import json,sys
try:p=json.load(open("/tmp/stop-probe.json"))
except Exception:sys.exit(1)
sys.exit(0 if p.get("desiredStatus")=="EXITED" else 1)
PY
  then stop_ok=1; break; fi
done
[ "$stop_ok" -eq 1 ] || final_rc=97

if [ "$result_ok" -eq 1 ] && [ "$stop_ok" -eq 1 ]; then
  curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/delete.json || true
  sleep 2
  code="$(curl -sS -o /tmp/delete-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  if [ "$code" = 404 ]; then deleted=1; fi
fi

if [ -s /tmp/probe-result.json ]; then
  python3 - <<'PY' || final_rc=98
import json
r=json.load(open("/tmp/probe-result.json"))
assert r["sealed_eval_consumed"] is False and r["worker05_used_for_tuning"] is False
assert r["summary_all"]["tasks"]==56
assert r["summary_discovery"]["tasks"]==28 and r["summary_shadow"]["tasks"]==28
assert r["decision"] in ("MATERIAL_LATENT_CAPABILITY","NO_MATERIAL_GAP")
print("AQLEVON_ONE_DAY_RESULT_GATE_PASS",r["decision"],json.dumps(r["summary_all"],sort_keys=True))
PY
fi
printf '%s\n' "$final_rc" >/tmp/probe_final_rc

python3 - <<PY
import datetime,hashlib,json
from pathlib import Path
def get(p):
    q=Path(p); return q.read_text().strip() if q.exists() else None
start=get("/tmp/pod_created_epoch")
elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-int(start) if start else None
rate=get("/tmp/live_rate") or get("/tmp/selected_rate")
result=json.load(open("/tmp/probe-result.json")) if Path("/tmp/probe-result.json").exists() else {}
out={"kind":"AQLEVON_ONE_DAY_PUBLIC_PASSN_PROBE_RUN_RECEIPT_V1","authorization_id":"$AUTH_ID","authorization_sha256":"$AUTH_SHA",
     "source_head":"$SOURCE_HEAD","w02_head":"$W02_HEAD","image_digest":"$IMAGE_DIGEST","pod_id":"$pod",
     "gpu_type":get("/tmp/selected_gpu"),"rate_per_hour_usd":rate,"billed_seconds_estimate":elapsed,
     "compute_cost_estimate_usd":round(float(rate)*elapsed/3600,6) if rate and elapsed is not None else None,
     "remote_exit_code":int(get("/tmp/probe_remote_rc")) if get("/tmp/probe_remote_rc") and get("/tmp/probe_remote_rc").isdigit() else None,
     "final_exit_code":int(get("/tmp/probe_final_rc")) if get("/tmp/probe_final_rc") and get("/tmp/probe_final_rc").isdigit() else None,
     "pod_status":(json.load(open("/tmp/stop-probe.json")).get("desiredStatus") if Path("/tmp/stop-probe.json").exists() else None),
     "pod_deleted_after_durable_egress":bool($deleted),"result_present":bool(result),
     "result_sha256":hashlib.sha256(Path("/tmp/probe-result.json").read_bytes()).hexdigest() if Path("/tmp/probe-result.json").exists() else None,
     "log_sha256":hashlib.sha256(Path("/tmp/probe.log").read_bytes()).hexdigest() if Path("/tmp/probe.log").exists() else None,
     "decision":result.get("decision"),"summary_all":result.get("summary_all"),"summary_discovery":result.get("summary_discovery"),
     "summary_shadow":result.get("summary_shadow"),"sealed_eval_consumed":False,"worker05_used_for_tuning":False,
     "capability_gain_claim":False,"training_performed":False,"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
Path("$RESULT").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_ONE_DAY_RUN_RECEIPT",json.dumps(out,sort_keys=True))
PY

git add "$RESULT"
git commit -m "ops: record one-day public passN probe result [skip ci]" || true
git pull --rebase origin ops/one-day-verified-trajectory-20260925 || true
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || true

test "$final_rc" -eq 0 || exit "$final_rc"
test "$stop_ok" -eq 1 || exit 97
test -s /tmp/probe-result.json || exit 95
