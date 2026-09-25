#!/usr/bin/env bash
set -euo pipefail

AUTH=".github/runpod-control/one-day-coverage-crystallization-manager-authorization-08-20260925.json"
FREE=".github/runpod-control/one-day-coverage-crystallization-free-result-08.json"
TRIGGER=".github/runpod-control/execute-one-day-coverage-crystallization-08.json"
CONSUMED=".github/runpod-control/one-day-coverage-crystallization-consumed-08.json"
RESULT=".github/runpod-control/one-day-coverage-crystallization-run-result-08.json"
SOURCE_HEAD="529e665ea140c2f8d6b96c02a42c100e9075c037"
W02_HEAD="abb94ef134e2e97036b6959dbc9db4278d3736b6"
AUTH_ID="P4-ONE-DAY-COVERAGE-CRYSTALLIZATION-20260925-08"
AUTH_SHA="67fb385b49b3f2f0764458311136c395c269e63567d8e23a714b7395100f6a6e"
IMAGE_DIGEST="sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec"
pod=""
cleaned=0

cleanup() {
  status=$?
  if [ -n "$pod" ] && [ "$cleaned" != 1 ]; then
    echo "AQLEVON_AUTH08_EXIT_CLEANUP pod=$pod status=$status"
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth08-exit-stop.json || true
    sleep 2
    curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/auth08-exit-delete.json || true
  fi
  exit "$status"
}
trap cleanup EXIT

test -n "${RUNPOD_API_KEY:-}"
test ! -e "$CONSUMED"

python3 - <<'PY'
import hashlib,json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-coverage-crystallization-manager-authorization-08-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/one-day-coverage-crystallization-free-result-08.json").read_text())
t=json.loads(Path(".github/runpod-control/execute-one-day-coverage-crystallization-08.json").read_text())
sha=hashlib.sha256(json.dumps({k:v for k,v in a.items() if k!="authorization_sha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert sha==a["authorization_sha256"]=="67fb385b49b3f2f0764458311136c395c269e63567d8e23a714b7395100f6a6e"
assert a["authorization_id"]==f["authorization_id"]==t["authorization_id"]=="P4-ONE-DAY-COVERAGE-CRYSTALLIZATION-20260925-08"
assert a["expected_source_head"]==f["source_head"]==t["expected_source_head"]=="529e665ea140c2f8d6b96c02a42c100e9075c037"
assert a["training_authorized"] is True and a["single_use"] is True
assert a["train_discovery_tasks"]==28 and a["train_families"]==14 and a["epochs"]==2 and a["optimizer_updates"]==56
assert a["public_shadow_tasks"]==28
assert f["paid_resource_created"] is False and f["active_aqlevon_pods"]==[]
assert float(a["fresh_authorization_spend_before_auth08_usd"])+float(a["max_total_cost_usd"])<=float(a["mission_max_total_usd"])
print("AQLEVON_AUTH08_DRIVER_CONTRACT_PASS")
PY

git fetch -q origin "$SOURCE_HEAD" "$W02_HEAD"
rm -rf /tmp/coverage-source
mkdir -p /tmp/coverage-source
git archive "$SOURCE_HEAD" | tar -x -C /tmp/coverage-source
printf "%s\n" "$SOURCE_HEAD" > /tmp/coverage-source/.aqlevon_source_head
test "$(cat /tmp/coverage-source/.aqlevon_source_head)" = "$SOURCE_HEAD"
git show "$W02_HEAD":research/weight_factory/agent02/gene1_training_visible_pack_v1.json > /tmp/public-pack.json
git show "$W02_HEAD":research/weight_factory/agent02/gene1_data_verifier_pack_v1.py > /tmp/w02.py
python3 -m py_compile /tmp/coverage-source/research/weight_factory/agent03/p4_one_day_recovered_materializer.py
python3 -m py_compile /tmp/coverage-source/research/weight_factory/agent03/p4_one_day_crystallize_coverage.py
python3 /tmp/coverage-source/research/weight_factory/agent03/p4_one_day_recovered_materializer.py \
  --recovered-decision /tmp/coverage-source/research/weight_factory/agent03/auth05_recovered_material_decision.json \
  --training-pack /tmp/public-pack.json --output /tmp/recovered-materialized-probe.json > /tmp/materializer08.log
grep -q 'train_targets=6 shadow_targets=0' /tmp/materializer08.log
python3 /tmp/coverage-source/research/weight_factory/agent03/p4_one_day_crystallize_coverage.py \
  --probe-result /tmp/recovered-materialized-probe.json --w02-module /tmp/w02.py \
  --training-pack /tmp/public-pack.json --preflight-only > /tmp/preflight08.log
grep -q 'train_verified=28 shadow=28 probe_decision=MATERIAL_LATENT_CAPABILITY' /tmp/preflight08.log

tar --owner=0 --group=0 --numeric-owner -czf /tmp/coverage-source.tgz -C /tmp/coverage-source .
sha256sum /tmp/coverage-source.tgz /tmp/public-pack.json /tmp/w02.py /tmp/recovered-materialized-probe.json > /tmp/auth08-input-sha256.txt
echo AQLEVON_AUTH08_EXACT_SOURCE_STAGED_BEFORE_BILLING

curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pods08.json
python3 - <<'PY'
import json
p=json.load(open("/tmp/pods08.json")); items=p if isinstance(p,list) else p.get("pods") or p.get("items") or []
active=[x for x in items if str(x.get("name","")).startswith("AQLEVON-") and str(x.get("desiredStatus") or x.get("status"))!="EXITED"]
assert not active,active
print("AQLEVON_AUTH08_NO_ACTIVE_PODS_PASS")
PY

curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl gpu list --output json >/tmp/gpus08.json
python3 - <<'PY'
import datetime,json
from pathlib import Path
a=json.load(open(".github/runpod-control/one-day-coverage-crystallization-manager-authorization-08-20260925.json"))
choices=[]
for g in json.load(open("/tmp/gpus08.json")):
    gid=str(g.get("gpuId",""))
    if gid not in set(a["permitted_gpu_ids"]) or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in g.get("dataCenterAvailability") or []:
        if str(d.get("stockStatus")).lower()!="none" and d.get("dataCenterId"):
            secs=min(int(a["max_billed_seconds"]),int(float(a["max_total_cost_usd"])*3600/price))
            if secs>=1200: choices.append((price,gid,str(d["dataCenterId"]),secs))
assert choices,"no_auth08_gpu_stock_at_paid_boundary"
price,gpu,dc,secs=sorted(choices)[0]
Path("/tmp/selected_gpu08").write_text(gpu); Path("/tmp/selected_dc08").write_text(dc)
out={"selected_gpu_id":gpu,"selected_datacenter":dc,"selected_price_hr":price,"dynamic_max_billed_seconds":secs,
     "paid_boundary_refresh_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
Path(".github/runpod-control/one-day-coverage-crystallization-live-selection-08.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH08_LIVE_SELECTION",gpu,dc,price,secs)
PY

git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add .github/runpod-control/one-day-coverage-crystallization-live-selection-08.json
git commit -m "ops: persist Auth08 live selection before spend [skip ci]"
git push origin HEAD:ops/one-day-verified-trajectory-20260925

ssh-keygen -q -t ed25519 -N '' -f /tmp/auth08_key
PUBKEY="$(cat /tmp/auth08_key.pub)"
env_json="$(PUBKEY="$PUBKEY" python3 - <<'PY'
import json,os
print(json.dumps({"PUBLIC_KEY":os.environ["PUBKEY"]},separators=(",",":")))
PY
)"
runpodctl pod create --name AQLEVON-ONE-DAY-COVERAGE-08 \
  --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST" \
  --gpu-id "$(cat /tmp/selected_gpu08)" --gpu-count 1 --cloud-type SECURE \
  --data-center-ids "$(cat /tmp/selected_dc08)" --container-disk-in-gb 40 \
  --volume-in-gb 40 --volume-mount-path /workspace --ports 22/tcp --env "$env_json" --output json > /tmp/create08.json

python3 - <<'PY'
import json,time,datetime
from pathlib import Path
p=json.load(open("/tmp/create08.json")); pod=p.get("id") or p.get("podId"); assert pod
Path("/tmp/pod_id08").write_text(str(pod)); Path("/tmp/pod_created_epoch08").write_text(str(int(time.time())))
sel=json.load(open(".github/runpod-control/one-day-coverage-crystallization-live-selection-08.json"))
out={"authorization_id":"P4-ONE-DAY-COVERAGE-CRYSTALLIZATION-20260925-08",
     "authorization_sha256":"67fb385b49b3f2f0764458311136c395c269e63567d8e23a714b7395100f6a6e",
     "source_head":"529e665ea140c2f8d6b96c02a42c100e9075c037",
     "image_digest":"sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec",
     "pod_id":pod,"created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "single_use_consumed":True,"training_authorized":True,**sel}
Path(".github/runpod-control/one-day-coverage-crystallization-consumed-08.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH08_POD_CREATED",pod)
PY
pod="$(cat /tmp/pod_id08)"
git add "$CONSUMED"
git commit -m "ops: consume Auth08 coverage crystallization authorization [skip ci]"
git push origin HEAD:ops/one-day-verified-trajectory-20260925

ready=0
for i in $(seq 1 120); do
  curl -sS "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pod08.json || true
  if python3 - <<'PY'
import json,sys
try:p=json.load(open("/tmp/pod08.json"))
except Exception:sys.exit(1)
ip=p.get("publicIp");port=(p.get("portMappings") or {}).get("22")
if p.get("desiredStatus")=="RUNNING" and ip and port:
    open("/tmp/ssh_target08","w").write(str(ip)+"|"+str(port))
    open("/tmp/live_rate08","w").write(str(p.get("costPerHr")))
    sys.exit(0)
sys.exit(1)
PY
  then ready=1; break; fi
  elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch08) ))
  [ "$elapsed" -lt 600 ] || break
  sleep 5
done
test "$ready" = 1
host="$(cut -d'|' -f1 /tmp/ssh_target08)"; port="$(cut -d'|' -f2 /tmp/ssh_target08)"

cat >/tmp/hw08.py <<'PY'
import subprocess
name=subprocess.check_output(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],text=True).splitlines()[0].strip()
free=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True).splitlines()[0])
assert free>=40000,(name,free)
print("AQLEVON_AUTH08_HARDWARE_PASS",name,free)
PY
scp -q -i /tmp/auth08_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/hw08.py root@"$host":/tmp/hw08.py
ssh -i /tmp/auth08_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" python3 /tmp/hw08.py

scp -q -i /tmp/auth08_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  /tmp/coverage-source.tgz /tmp/public-pack.json /tmp/w02.py /tmp/recovered-materialized-probe.json \
  .github/runpod-control/auth08-coverage-crystallization-remote-v1.sh root@"$host":/tmp/
ssh -i /tmp/auth08_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" \
  'mkdir -p /workspace; rm -f /workspace/auth08.rc; nohup setsid bash /tmp/auth08-coverage-crystallization-remote-v1.sh >/workspace/auth08-supervisor.log 2>&1 < /dev/null &'
echo AQLEVON_AUTH08_REMOTE_START

rc=255
for i in $(seq 1 300); do
  if ssh -i /tmp/auth08_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 root@"$host" 'test -s /workspace/auth08.rc' >/dev/null 2>&1; then
    rc="$(ssh -i /tmp/auth08_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" 'cat /workspace/auth08.rc' | tail -n1)"
    break
  fi
  elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch08) ))
  [ "$elapsed" -lt 1750 ] || { rc=125; break; }
  sleep 5
done
[[ "$rc" =~ ^[0-9]+$ ]] || rc=255

ssh -i /tmp/auth08_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" \
  'cd /workspace && tar -czf /tmp/auth08-evidence.tgz auth08 auth08-supervisor.log auth08.rc 2>/dev/null' || true
ssh -i /tmp/auth08_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" \
  'cat /workspace/auth08/train.log' >/tmp/auth08-train.log 2>/dev/null || true
scp -q -i /tmp/auth08_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  root@"$host":/tmp/auth08-evidence.tgz /tmp/auth08-evidence.tgz 2>/dev/null || true
printf '%s\n' "$rc" >/tmp/auth08_rc

curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/stop08.json || true
for i in $(seq 1 30); do
  sleep 2
  code="$(curl -sS -o /tmp/stop08-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  [ "$code" = 404 ] && break
  python3 -c 'import json,sys; p=json.load(open("/tmp/stop08-probe.json")); sys.exit(0 if p.get("desiredStatus")=="EXITED" else 1)' && break || true
done
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/delete08.json || true
for i in $(seq 1 30); do
  code="$(curl -sS -o /tmp/final08.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  [ "$code" = 404 ] && { cleaned=1; break; }
  sleep 2
done
test "$cleaned" = 1

python3 - <<'PY'
import json,datetime,hashlib,tarfile
from pathlib import Path
def txt(p): return Path(p).read_text().strip() if Path(p).exists() else None
start=txt("/tmp/pod_created_epoch08"); elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-int(start) if start else None
rate=txt("/tmp/live_rate08"); rc=txt("/tmp/auth08_rc")
out={"kind":"AQLEVON_ONE_DAY_COVERAGE_CRYSTALLIZATION_RUN_RECEIPT_V1",
     "authorization_id":"P4-ONE-DAY-COVERAGE-CRYSTALLIZATION-20260925-08",
     "authorization_sha256":"67fb385b49b3f2f0764458311136c395c269e63567d8e23a714b7395100f6a6e",
     "source_head":"529e665ea140c2f8d6b96c02a42c100e9075c037","pod_id":txt("/tmp/pod_id08"),
     "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "true_exit_code":int(rc) if rc and rc.isdigit() else None,"rate_per_hour_usd":rate,
     "billed_seconds_estimate":elapsed,"compute_cost_estimate_usd":round(float(rate)*elapsed/3600,6) if rate and elapsed is not None else None,
     "evidence_archive_present":Path("/tmp/auth08-evidence.tgz").exists(),
     "training_log_sha256":hashlib.sha256(Path("/tmp/auth08-train.log").read_bytes()).hexdigest() if Path("/tmp/auth08-train.log").exists() else None,
     "pod_stopped_and_deleted":True,"sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False}
if Path("/tmp/auth08-evidence.tgz").exists():
    try:
        t=tarfile.open("/tmp/auth08-evidence.tgz","r:gz"); root="auth08/candidate/"
        rec=json.loads(t.extractfile(root+"training_run_receipt.json").read())
        man=json.loads(t.extractfile(root+"candidate_artifact_manifest.json").read())
        out.update({"candidate_status":man.get("candidate_status"),"public_shadow_gate_pass":man.get("public_shadow_gate_pass"),
                    "shadow_pre_successes":rec.get("shadow_pre_successes"),"shadow_post_successes":rec.get("shadow_post_successes"),
                    "shadow_gain_tasks":rec.get("shadow_gain_tasks"),"shadow_improvement":rec.get("shadow_improvement"),
                    "shadow_regressions":rec.get("shadow_regressions"),"adapter_model_sha256":man.get("adapter_model_sha256"),
                    "manifest_sha256":man.get("manifest_sha256"),"optimizer_updates":rec.get("optimizer_updates"),
                    "epochs":rec.get("epochs")})
    except Exception as e: out["artifact_parse_error"]=repr(e)
Path(".github/runpod-control/one-day-coverage-crystallization-run-result-08.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH08_RESULT",json.dumps(out,sort_keys=True))
PY

git add "$RESULT"
git commit -m "ops: record Auth08 coverage crystallization result [skip ci]" || true
git fetch origin ops/one-day-verified-trajectory-20260925
git rebase origin/ops/one-day-verified-trajectory-20260925 || { git rebase --abort || true; echo AQLEVON_AUTH08_RESULT_BRANCH_PUSH_SKIPPED; }
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || echo AQLEVON_AUTH08_RESULT_PUSH_NONFATAL

if [ "$rc" != 0 ] || [ ! -s /tmp/auth08-evidence.tgz ]; then
  exit "$rc"
fi
echo AQLEVON_AUTH08_DRIVER_COMPLETE
