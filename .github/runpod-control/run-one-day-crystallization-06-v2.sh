#!/usr/bin/env bash
set -euo pipefail

AUTH=".github/runpod-control/one-day-crystallization-manager-authorization-06-20260925.json"
FREE=".github/runpod-control/one-day-crystallization-free-result-06.json"
TRIGGER=".github/runpod-control/execute-one-day-crystallization-06.json"
CONSUMED=".github/runpod-control/one-day-crystallization-consumed-06.json"
RESULT=".github/runpod-control/one-day-crystallization-run-result-06.json"
SOURCE_HEAD="f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb"
W02_HEAD="abb94ef134e2e97036b6959dbc9db4278d3736b6"
AUTH_ID="P4-ONE-DAY-CRYSTALLIZATION-20260925-06"
AUTH_SHA="271d954f40b5e9c67f75106cc1e0e480f9cb7b2ea12a1919383a79aa597cf327"
IMAGE_DIGEST="sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec"
pod=""
cleaned=0

cleanup() {
  status=$?
  if [ -n "$pod" ] && [ "$cleaned" != 1 ]; then
    echo "AQLEVON_AUTH06_EXIT_CLEANUP pod=$pod status=$status"
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth06-exit-stop.json || true
    sleep 2
    curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/auth06-exit-delete.json || true
  fi
  exit "$status"
}
trap cleanup EXIT

test -n "${RUNPOD_API_KEY:-}"
test ! -e "$CONSUMED"

python3 - <<'PY'
import hashlib,json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-crystallization-manager-authorization-06-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/one-day-crystallization-free-result-06.json").read_text())
t=json.loads(Path(".github/runpod-control/execute-one-day-crystallization-06.json").read_text())
sha=hashlib.sha256(json.dumps({k:v for k,v in a.items() if k!="authorization_sha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert sha==a["authorization_sha256"]=="271d954f40b5e9c67f75106cc1e0e480f9cb7b2ea12a1919383a79aa597cf327"
assert a["authorization_id"]==f["authorization_id"]==t["authorization_id"]=="P4-ONE-DAY-CRYSTALLIZATION-20260925-06"
assert a["expected_source_head"]==f["source_head"]==t["expected_source_head"]=="f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb"
assert a["training_authorized"] is True and a["single_use"] is True
assert a["training_examples"]==6 and a["public_shadow_tasks"]==28
assert f["paid_resource_created"] is False and f["active_aqlevon_pods"]==[]
assert float(a["fresh_authorization_spend_before_auth06_usd"])+float(a["max_total_cost_usd"])<=5.0
print("AQLEVON_AUTH06_DRIVER_CONTRACT_PASS")
PY

git fetch -q origin "$SOURCE_HEAD" "$W02_HEAD"
rm -rf /tmp/crystal-source
mkdir -p /tmp/crystal-source
git archive "$SOURCE_HEAD" | tar -x -C /tmp/crystal-source
printf "%s\n" "$SOURCE_HEAD" > /tmp/crystal-source/.aqlevon_source_head
test "$(cat /tmp/crystal-source/.aqlevon_source_head)" = "$SOURCE_HEAD"
git show "$W02_HEAD":research/weight_factory/agent02/gene1_training_visible_pack_v1.json > /tmp/public-pack.json
git show "$W02_HEAD":research/weight_factory/agent02/gene1_data_verifier_pack_v1.py > /tmp/w02.py
python3 -m py_compile /tmp/crystal-source/research/weight_factory/agent03/p4_one_day_recovered_materializer.py
python3 -m py_compile /tmp/crystal-source/research/weight_factory/agent03/p4_one_day_crystallize.py
python3 /tmp/crystal-source/research/weight_factory/agent03/p4_one_day_recovered_materializer.py   --recovered-decision /tmp/crystal-source/research/weight_factory/agent03/auth05_recovered_material_decision.json   --training-pack /tmp/public-pack.json --output /tmp/recovered-materialized-probe.json | tee /tmp/materializer06.log
grep -q 'train_targets=6 shadow_targets=0' /tmp/materializer06.log
python3 /tmp/crystal-source/research/weight_factory/agent03/p4_one_day_crystallize.py   --probe-result /tmp/recovered-materialized-probe.json --w02-module /tmp/w02.py   --training-pack /tmp/public-pack.json --preflight-only | tee /tmp/preflight06.log
grep -q 'train_verified=6 shadow=28 probe_decision=MATERIAL_LATENT_CAPABILITY' /tmp/preflight06.log

tar -czf /tmp/crystal-source.tgz -C /tmp/crystal-source .
sha256sum /tmp/crystal-source.tgz /tmp/public-pack.json /tmp/w02.py /tmp/recovered-materialized-probe.json > /tmp/auth06-input-sha256.txt
echo AQLEVON_AUTH06_EXACT_SOURCE_STAGED_BEFORE_BILLING

curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pods06.json
python3 - <<'PY'
import json
p=json.load(open("/tmp/pods06.json")); items=p if isinstance(p,list) else p.get("pods") or p.get("items") or []
active=[x for x in items if str(x.get("name","")).startswith("AQLEVON-") and str(x.get("desiredStatus") or x.get("status"))!="EXITED"]
assert not active,active
print("AQLEVON_AUTH06_NO_ACTIVE_PODS_PASS")
PY
curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl gpu list --output json >/tmp/gpus06.json
python3 - <<'PY'
import datetime,json
from pathlib import Path
a=json.load(open(".github/runpod-control/one-day-crystallization-manager-authorization-06-20260925.json"))
choices=[]
for g in json.load(open("/tmp/gpus06.json")):
    gid=str(g.get("gpuId",""))
    if gid not in set(a["permitted_gpu_ids"]) or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in g.get("dataCenterAvailability") or []:
        if str(d.get("stockStatus")).lower()!="none" and d.get("dataCenterId"):
            secs=min(int(a["max_billed_seconds"]),int(float(a["max_total_cost_usd"])*3600/price))
            if secs>=1200: choices.append((price,gid,str(d["dataCenterId"]),secs))
assert choices,"no_auth06_gpu_stock_at_paid_boundary"
price,gpu,dc,secs=sorted(choices)[0]
Path("/tmp/selected_gpu").write_text(gpu); Path("/tmp/selected_dc").write_text(dc)
out={"selected_gpu_id":gpu,"selected_datacenter":dc,"selected_price_hr":price,"dynamic_max_billed_seconds":secs,
     "paid_boundary_refresh_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
Path(".github/runpod-control/one-day-crystallization-live-selection-06.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH06_LIVE_SELECTION",gpu,dc,price,secs)
PY
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add .github/runpod-control/one-day-crystallization-live-selection-06.json
git commit -m "ops: persist Auth06 live selection before spend [skip ci]"
git push origin HEAD:ops/one-day-verified-trajectory-20260925

ssh-keygen -q -t ed25519 -N '' -f /tmp/auth06_key
PUBKEY="$(cat /tmp/auth06_key.pub)"
env_json="$(PUBKEY="$PUBKEY" python3 - <<'PY'
import json,os
print(json.dumps({"PUBLIC_KEY":os.environ["PUBKEY"]},separators=(",",":")))
PY
)"
runpodctl pod create --name AQLEVON-ONE-DAY-CRYSTALLIZATION-06   --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"   --gpu-id "$(cat /tmp/selected_gpu)" --gpu-count 1 --cloud-type SECURE   --data-center-ids "$(cat /tmp/selected_dc)" --container-disk-in-gb 40   --volume-in-gb 40 --volume-mount-path /workspace --ports 22/tcp --env "$env_json" --output json > /tmp/create06.json

python3 - <<'PY'
import json,time,datetime
from pathlib import Path
p=json.load(open("/tmp/create06.json")); pod=p.get("id") or p.get("podId"); assert pod
Path("/tmp/pod_id").write_text(str(pod)); Path("/tmp/pod_created_epoch").write_text(str(int(time.time())))
sel=json.load(open(".github/runpod-control/one-day-crystallization-live-selection-06.json"))
out={"authorization_id":"P4-ONE-DAY-CRYSTALLIZATION-20260925-06",
     "authorization_sha256":"271d954f40b5e9c67f75106cc1e0e480f9cb7b2ea12a1919383a79aa597cf327",
     "source_head":"f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb",
     "image_digest":"sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec",
     "pod_id":pod,"created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "single_use_consumed":True,"training_authorized":True,**sel}
Path(".github/runpod-control/one-day-crystallization-consumed-06.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH06_POD_CREATED",pod)
PY
pod="$(cat /tmp/pod_id)"
git add "$CONSUMED"
git commit -m "ops: consume Auth06 crystallization authorization [skip ci]"
git push origin HEAD:ops/one-day-verified-trajectory-20260925

ready=0
for i in $(seq 1 120); do
  curl -sS "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pod06.json || true
  if python3 - <<'PY'
import json,sys
try:p=json.load(open("/tmp/pod06.json"))
except Exception:sys.exit(1)
ip=p.get("publicIp");port=(p.get("portMappings") or {}).get("22")
if p.get("desiredStatus")=="RUNNING" and ip and port:
    open("/tmp/ssh_target","w").write(str(ip)+"|"+str(port))
    open("/tmp/live_rate","w").write(str(p.get("costPerHr")))
    sys.exit(0)
sys.exit(1)
PY
  then ready=1; break; fi
  elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch) ))
  [ "$elapsed" -lt 600 ] || break
  sleep 5
done
test "$ready" = 1
host="$(cut -d'|' -f1 /tmp/ssh_target)"; port="$(cut -d'|' -f2 /tmp/ssh_target)"

cat >/tmp/hw06.py <<'PY'
import subprocess
name=subprocess.check_output(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],text=True).splitlines()[0].strip()
free=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True).splitlines()[0])
assert free>=70000,(name,free)
print("AQLEVON_AUTH06_HARDWARE_PASS",name,free)
PY
scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/hw06.py root@"$host":/tmp/hw06.py
ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" python3 /tmp/hw06.py

scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null   /tmp/crystal-source.tgz /tmp/public-pack.json /tmp/w02.py /tmp/recovered-materialized-probe.json   .github/runpod-control/auth06-crystallization-remote-v2.sh root@"$host":/tmp/
ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"   'mkdir -p /workspace; rm -f /workspace/auth06.rc; nohup setsid bash /tmp/auth06-crystallization-remote-v2.sh >/workspace/auth06-supervisor.log 2>&1 < /dev/null &'
echo AQLEVON_AUTH06_REMOTE_START

rc=255
for i in $(seq 1 240); do
  if ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 root@"$host" 'test -s /workspace/auth06.rc' >/dev/null 2>&1; then
    rc="$(ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" 'cat /workspace/auth06.rc' | tail -n1)"
    break
  fi
  elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch) ))
  [ "$elapsed" -lt 1750 ] || { rc=125; break; }
  sleep 5
done
[[ "$rc" =~ ^[0-9]+$ ]] || rc=255

ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"   'cd /workspace && tar -czf /tmp/auth06-evidence.tgz auth06 auth06-supervisor.log auth06.rc 2>/dev/null' || true
ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"   'cat /workspace/auth06/train.log' >/tmp/auth06-train.log 2>/dev/null || true
scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null   root@"$host":/tmp/auth06-evidence.tgz /tmp/auth06-evidence.tgz 2>/dev/null || true
printf '%s\n' "$rc" >/tmp/crystal_rc

curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/stop06.json || true
for i in $(seq 1 30); do
  sleep 2
  code="$(curl -sS -o /tmp/stop06-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  [ "$code" = 404 ] && break
  python3 -c 'import json,sys; p=json.load(open("/tmp/stop06-probe.json")); sys.exit(0 if p.get("desiredStatus")=="EXITED" else 1)' && break || true
done
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/delete06.json || true
for i in $(seq 1 30); do
  code="$(curl -sS -o /tmp/final06.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  [ "$code" = 404 ] && { cleaned=1; break; }
  sleep 2
done
test "$cleaned" = 1

python3 - <<'PY'
import json,datetime,hashlib,tarfile
from pathlib import Path
def txt(p): return Path(p).read_text().strip() if Path(p).exists() else None
start=txt("/tmp/pod_created_epoch"); elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-int(start) if start else None
rate=txt("/tmp/live_rate"); rc=txt("/tmp/crystal_rc")
out={"kind":"AQLEVON_ONE_DAY_CRYSTALLIZATION_RUN_RECEIPT_V1",
     "authorization_id":"P4-ONE-DAY-CRYSTALLIZATION-20260925-06",
     "authorization_sha256":"271d954f40b5e9c67f75106cc1e0e480f9cb7b2ea12a1919383a79aa597cf327",
     "source_head":"f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb","pod_id":txt("/tmp/pod_id"),
     "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "true_exit_code":int(rc) if rc and rc.isdigit() else None,"rate_per_hour_usd":rate,
     "billed_seconds_estimate":elapsed,"compute_cost_estimate_usd":round(float(rate)*elapsed/3600,6) if rate and elapsed is not None else None,
     "evidence_archive_present":Path("/tmp/auth06-evidence.tgz").exists(),
     "training_log_sha256":hashlib.sha256(Path("/tmp/auth06-train.log").read_bytes()).hexdigest() if Path("/tmp/auth06-train.log").exists() else None,
     "pod_stopped_and_deleted":True,"sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False}
if Path("/tmp/auth06-evidence.tgz").exists():
    try:
        t=tarfile.open("/tmp/auth06-evidence.tgz","r:gz"); root="auth06/candidate/"
        rec=json.loads(t.extractfile(root+"training_run_receipt.json").read())
        man=json.loads(t.extractfile(root+"candidate_artifact_manifest.json").read())
        out.update({"candidate_status":man.get("candidate_status"),"public_shadow_gate_pass":man.get("public_shadow_gate_pass"),
                    "shadow_pre_successes":rec.get("shadow_pre_successes"),"shadow_post_successes":rec.get("shadow_post_successes"),
                    "shadow_gain_tasks":rec.get("shadow_gain_tasks"),"shadow_improvement":rec.get("shadow_improvement"),
                    "adapter_model_sha256":man.get("adapter_model_sha256"),"manifest_sha256":man.get("manifest_sha256")})
    except Exception as e: out["artifact_parse_error"]=repr(e)
Path(".github/runpod-control/one-day-crystallization-run-result-06.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH06_RESULT",json.dumps(out,sort_keys=True))
PY
git add "$RESULT"
git commit -m "ops: record Auth06 crystallization result [skip ci]" || true
git push origin HEAD:ops/one-day-verified-trajectory-20260925

if [ "$rc" != 0 ] || [ ! -s /tmp/auth06-evidence.tgz ]; then
  exit "$rc"
fi
echo AQLEVON_AUTH06_DRIVER_COMPLETE
