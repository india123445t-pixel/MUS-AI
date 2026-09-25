#!/usr/bin/env bash
set -euo pipefail

AUTH=".github/runpod-control/one-day-crystallization-manager-authorization-07-20260925.json"
FREE=".github/runpod-control/one-day-crystallization-free-result-07.json"
TRIGGER=".github/runpod-control/execute-one-day-crystallization-07.json"
CONSUMED=".github/runpod-control/one-day-crystallization-consumed-07.json"
SELECT=".github/runpod-control/one-day-crystallization-live-selection-07.json"
AUTH_ID="P4-ONE-DAY-CRYSTALLIZATION-20260925-07"
AUTH_SHA="8f5e7ce1ca79e4d8f0e8e041dc2b656bc57c2cbea918f4e888581c28f4dbf9df"
SOURCE_HEAD="f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb"
W02_HEAD="abb94ef134e2e97036b6959dbc9db4278d3736b6"
IMAGE_DIGEST="sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec"
CONTROL_BRANCH="ops/auth07-crystallization-frozen-20260925"
pod=""
host=""
port=""
cleaned=0

on_exit() {
  status=$?
  set +e
  printf '%s\n' "$status" >/tmp/auth07_driver_rc
  if [ -n "$pod" ] && [ "$cleaned" != 1 ]; then
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth07-exit-stop.json || true
    sleep 2
    curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/auth07-exit-delete.json || true
  fi
  exit "$status"
}
trap on_exit EXIT

test -n "${RUNPOD_API_KEY:-}"
test ! -e "$CONSUMED"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
a=json.loads(Path('.github/runpod-control/one-day-crystallization-manager-authorization-07-20260925.json').read_text())
f=json.loads(Path('.github/runpod-control/one-day-crystallization-free-result-07.json').read_text())
t=json.loads(Path('.github/runpod-control/execute-one-day-crystallization-07.json').read_text())
sha=hashlib.sha256(json.dumps({k:v for k,v in a.items() if k!='authorization_sha256'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert sha==a['authorization_sha256']=='8f5e7ce1ca79e4d8f0e8e041dc2b656bc57c2cbea918f4e888581c28f4dbf9df'
assert a['authorization_id']==f['authorization_id']==t['authorization_id']=='P4-ONE-DAY-CRYSTALLIZATION-20260925-07'
assert a['expected_source_head']==f['source_head']==t['expected_source_head']=='f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb'
assert a['training_authorized'] is True and a['single_use'] is True
assert a['training_examples']==6 and a['public_shadow_tasks']==28
assert f['paid_resource_created'] is False and f['active_aqlevon_pods']==[]
assert float(a['fresh_authorization_spend_before_auth07_usd'])+float(a['max_total_cost_usd'])<=5.0
print('AQLEVON_AUTH07_PRESPEND_CONTRACT_PASS')
PY

git fetch -q origin "$SOURCE_HEAD" "$W02_HEAD"
rm -rf /tmp/auth07-stage && mkdir -p /tmp/auth07-stage/source
git archive "$SOURCE_HEAD" | tar -x -C /tmp/auth07-stage/source
printf '%s\n' "$SOURCE_HEAD" >/tmp/auth07-stage/source/.aqlevon_source_head
git show "$W02_HEAD":research/weight_factory/agent02/gene1_training_visible_pack_v1.json >/tmp/auth07-stage/public-pack.json
git show "$W02_HEAD":research/weight_factory/agent02/gene1_data_verifier_pack_v1.py >/tmp/auth07-stage/w02.py
python3 /tmp/auth07-stage/source/research/weight_factory/agent03/p4_one_day_recovered_materializer.py   --recovered-decision /tmp/auth07-stage/source/research/weight_factory/agent03/auth05_recovered_material_decision.json   --training-pack /tmp/auth07-stage/public-pack.json   --output /tmp/auth07-stage/probe.json | tee /tmp/auth07-materializer.log
grep -q 'train_targets=6 shadow_targets=0' /tmp/auth07-materializer.log
python3 /tmp/auth07-stage/source/research/weight_factory/agent03/p4_one_day_crystallize.py   --probe-result /tmp/auth07-stage/probe.json   --w02-module /tmp/auth07-stage/w02.py   --training-pack /tmp/auth07-stage/public-pack.json   --preflight-only | tee /tmp/auth07-preflight.log
grep -q 'train_verified=6 shadow=28 probe_decision=MATERIAL_LATENT_CAPABILITY' /tmp/auth07-preflight.log
tar --owner=1001 --group=1001 -czf /tmp/crystal-source-07.tgz -C /tmp/auth07-stage/source .
sha256sum /tmp/crystal-source-07.tgz /tmp/auth07-stage/public-pack.json /tmp/auth07-stage/w02.py /tmp/auth07-stage/probe.json >/tmp/auth07-input-sha256.txt
echo AQLEVON_AUTH07_EXACT_INPUTS_STAGED_BEFORE_BILLING

curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/auth07-pods-pre.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/auth07-pods-pre.json')); items=p if isinstance(p,list) else p.get('pods') or p.get('items') or []
active=[x for x in items if str(x.get('name','')).startswith('AQLEVON-') and str(x.get('desiredStatus') or x.get('status'))!='EXITED']
assert not active,active
print('AQLEVON_AUTH07_NO_ACTIVE_PODS_PASS')
PY
curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl gpu list --output json >/tmp/auth07-gpus.json
python3 - <<'PY'
import datetime,json
from pathlib import Path
a=json.load(open('.github/runpod-control/one-day-crystallization-manager-authorization-07-20260925.json'))
choices=[]; allowed=set(a['permitted_gpu_ids'])
for g in json.load(open('/tmp/auth07-gpus.json')):
    gid=str(g.get('gpuId',''))
    if gid not in allowed or not g.get('secureCloud'): continue
    price=float(g.get('securePricePerHr') or 999)
    if price>float(a['max_hourly_rate_usd']): continue
    for d in g.get('dataCenterAvailability') or []:
        if str(d.get('stockStatus')).lower()!='none' and d.get('dataCenterId'):
            secs=min(int(a['max_billed_seconds']),int(float(a['max_total_cost_usd'])*3600/price))
            if secs>=1200: choices.append((price,gid,str(d['dataCenterId']),secs))
assert choices,'no_auth07_gpu_stock_at_paid_boundary'
price,gpu,dc,secs=sorted(choices)[0]
Path('/tmp/auth07_gpu').write_text(gpu); Path('/tmp/auth07_dc').write_text(dc)
out={'selected_gpu_id':gpu,'selected_datacenter':dc,'selected_price_hr':price,
     'dynamic_max_billed_seconds':secs,'paid_boundary_refresh_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
Path('.github/runpod-control/one-day-crystallization-live-selection-07.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print('AQLEVON_AUTH07_LIVE_SELECTION',gpu,dc,price,secs)
PY
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$SELECT"
git commit -m "ops: persist Auth07 live selection before spend [skip ci]"
git push origin HEAD:"$CONTROL_BRANCH"

ssh-keygen -q -t ed25519 -N '' -f /tmp/auth07_key
PUBKEY="$(cat /tmp/auth07_key.pub)"
env_json="$(PUBKEY="$PUBKEY" python3 - <<'PY'
import json,os
print(json.dumps({'PUBLIC_KEY':os.environ['PUBKEY']},separators=(',',':')))
PY
)"
runpodctl pod create --name AQLEVON-ONE-DAY-CRYSTALLIZATION-07   --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"   --gpu-id "$(cat /tmp/auth07_gpu)" --gpu-count 1 --cloud-type SECURE   --data-center-ids "$(cat /tmp/auth07_dc)" --container-disk-in-gb 40   --volume-in-gb 40 --volume-mount-path /workspace --ports 22/tcp --env "$env_json" --output json >/tmp/auth07-create.json
python3 - <<'PY'
import datetime,json,time
from pathlib import Path
p=json.load(open('/tmp/auth07-create.json')); pod=p.get('id') or p.get('podId'); assert pod
Path('/tmp/auth07_pod_id').write_text(str(pod)); Path('/tmp/auth07_pod_epoch').write_text(str(int(time.time())))
sel=json.load(open('.github/runpod-control/one-day-crystallization-live-selection-07.json'))
out={'authorization_id':'P4-ONE-DAY-CRYSTALLIZATION-20260925-07',
     'authorization_sha256':'8f5e7ce1ca79e4d8f0e8e041dc2b656bc57c2cbea918f4e888581c28f4dbf9df',
     'source_head':'f3a2ca4c894e81cf9dffa1dd9935a3774b854cdb',
     'image_digest':'sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec',
     'pod_id':pod,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'single_use_consumed':True,'training_authorized':True,**sel}
Path('.github/runpod-control/one-day-crystallization-consumed-07.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print('AQLEVON_AUTH07_POD_CREATED',pod)
PY
pod="$(cat /tmp/auth07_pod_id)"
git add "$CONSUMED"
git commit -m "ops: consume Auth07 crystallization authorization [skip ci]"
git push origin HEAD:"$CONTROL_BRANCH"

ready=0
for i in $(seq 1 150); do
  curl -sS "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/auth07-pod.json || true
  if python3 - <<'PY'
import json,sys
try:p=json.load(open('/tmp/auth07-pod.json'))
except Exception:sys.exit(1)
ip=p.get('publicIp'); port=(p.get('portMappings') or {}).get('22')
if p.get('desiredStatus')=='RUNNING' and ip and port:
    open('/tmp/auth07_ssh','w').write(str(ip)+'|'+str(port))
    open('/tmp/auth07_rate','w').write(str(p.get('costPerHr')))
    sys.exit(0)
sys.exit(1)
PY
  then ready=1; break; fi
  elapsed=$(( $(date +%s) - $(cat /tmp/auth07_pod_epoch) ))
  [ "$elapsed" -lt 750 ] || break
  sleep 5
done
test "$ready" = 1
host="$(cut -d'|' -f1 /tmp/auth07_ssh)"; port="$(cut -d'|' -f2 /tmp/auth07_ssh)"

cat >/tmp/auth07-hw.py <<'PY'
import subprocess
name=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).splitlines()[0].strip()
free=float(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).splitlines()[0])
assert free>=70000,(name,free)
print('AQLEVON_AUTH07_HARDWARE_PASS',name,free)
PY
scp -q -i /tmp/auth07_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/auth07-hw.py root@"$host":/tmp/auth07-hw.py
ssh -i /tmp/auth07_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" python3 /tmp/auth07-hw.py

scp -q -i /tmp/auth07_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null   /tmp/crystal-source-07.tgz /tmp/auth07-stage/public-pack.json /tmp/auth07-stage/w02.py /tmp/auth07-stage/probe.json   .github/runpod-control/auth07-crystallization-remote.sh root@"$host":/tmp/
ssh -i /tmp/auth07_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"   'rm -f /tmp/auth07.rc /tmp/auth07-supervisor.log; nohup setsid bash /tmp/auth07-crystallization-remote.sh >/tmp/auth07-supervisor.log 2>&1 < /dev/null &'
echo AQLEVON_AUTH07_REMOTE_START

set +e
rc=255
for i in $(seq 1 240); do
  if ssh -i /tmp/auth07_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 root@"$host" 'test -s /tmp/auth07.rc' >/dev/null 2>&1; then
    rc="$(ssh -i /tmp/auth07_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" 'cat /tmp/auth07.rc' | tail -n1)"
    break
  fi
  elapsed=$(( $(date +%s) - $(cat /tmp/auth07_pod_epoch) ))
  [ "$elapsed" -lt 1750 ] || { rc=125; break; }
  sleep 5
done
[[ "$rc" =~ ^[0-9]+$ ]] || rc=255

ssh -i /tmp/auth07_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"   'tar --no-same-owner -czf /tmp/auth07-evidence.tgz -C /tmp auth07-runtime auth07-supervisor.log auth07.rc 2>/dev/null' || true
ssh -i /tmp/auth07_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"   'cat /tmp/auth07-runtime/train.log' >/tmp/auth07-train.log 2>/dev/null || true
scp -q -i /tmp/auth07_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null   root@"$host":/tmp/auth07-evidence.tgz /tmp/auth07-evidence.tgz 2>/dev/null || true
printf '%s\n' "$rc" >/tmp/auth07_remote_rc
set -e

if [ "$rc" = 0 ] && [ -s /tmp/auth07-evidence.tgz ]; then
python3 - <<'PY'
import json,re,tarfile
t=tarfile.open('/tmp/auth07-evidence.tgz','r:gz')
root='auth07-runtime/candidate/'
names=set(t.getnames())
required=['candidate_artifact/adapter_config.json','candidate_artifact/adapter_model.safetensors',
          'candidate_artifact_manifest.json','training_run_receipt.json','shadow_pre_eval.json',
          'shadow_post_eval.json','verified_discovery_trajectories.json','worker05_handoff_index.json']
assert all(root+x in names for x in required),sorted(names)
def read(p): return t.extractfile(root+p).read()
receipt=json.loads(read('training_run_receipt.json'))
manifest=json.loads(read('candidate_artifact_manifest.json'))
handoff=json.loads(read('worker05_handoff_index.json'))
assert receipt['train_examples']==6 and receipt['optimizer_updates']==6
assert receipt['changed_lora_B_elements']>0 and receipt['save_reload_hash_match'] is True
assert receipt['recovered_materialization'] is True
assert receipt['sealed_eval_consumed'] is False and receipt['worker05_used_for_tuning'] is False
assert manifest['save_reload_hash_match'] is True
weights=read('candidate_artifact/adapter_model.safetensors'); assert len(weights)>1000
length=int.from_bytes(weights[:8],'little'); header=json.loads(weights[8:8+length])
keys=[k for k in header if k!='__metadata__']; assert len(keys)==32,len(keys)
log=open('/tmp/auth07-train.log',errors='replace').read()
updates=[int(x) for x in re.findall(r'AQLEVON_CRYSTALLIZE_UPDATE=(\d+)/6',log)]
assert updates==list(range(1,7)),updates
assert 'AQLEVON_CRYSTALLIZE_PACKAGE_PASS' in log
print('AQLEVON_AUTH07_ARTIFACT_GATE_PASS',handoff['candidate_status'],receipt['shadow_pre_successes'],receipt['shadow_post_successes'])
PY
fi

curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth07-stop.json || true
for i in $(seq 1 30); do
  sleep 2
  code="$(curl -sS -o /tmp/auth07-stop-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  [ "$code" = 404 ] && break
  python3 -c 'import json,sys; p=json.load(open("/tmp/auth07-stop-probe.json")); sys.exit(0 if p.get("desiredStatus")=="EXITED" else 1)' && break || true
done
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/auth07-delete.json || true
for i in $(seq 1 30); do
  code="$(curl -sS -o /tmp/auth07-final-pod.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  if [ "$code" = 404 ]; then cleaned=1; break; fi
  sleep 2
done
test "$cleaned" = 1
echo AQLEVON_AUTH07_POD_STOP_DELETE_PASS
printf '%s\n' "$rc" >/tmp/auth07_remote_rc
test "$rc" = 0
test -s /tmp/auth07-evidence.tgz
echo AQLEVON_AUTH07_DRIVER_COMPLETE
