#!/usr/bin/env bash
set -uo pipefail

AUTH_ID="P4-ONE-DAY-CRYSTALLIZE-20260925-06"
AUTH_SHA="421795be22ddc505daade0e763a19e642f5ac115dfe1f877df8f0c99cb9dda48"
SOURCE_HEAD="b3bb3901b7f50e028e5939c55195ebf347551777"
W02_HEAD="abb94ef134e2e97036b6959dbc9db4278d3736b6"
IMAGE_DIGEST="sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec"
AUTH=".github/runpod-control/one-day-crystallize-manager-authorization-06-20260925.json"
FREE=".github/runpod-control/auth06-crystallize-free-result.json"
TRIGGER=".github/runpod-control/execute-one-day-crystallize-06.json"
CONSUMED=".github/runpod-control/one-day-crystallize-consumed-06.json"
RESULT=".github/runpod-control/one-day-crystallize-run-result-06.json"
REMOTE=".github/runpod-control/remote-one-day-crystallize-06.sh"

die(){ echo "FAIL_CLOSED_AUTH06 $*" >&2; exit 1; }
test -n "${RUNPOD_API_KEY:-}" || die no_runpod_key
test ! -e "$CONSUMED" || die authorization_already_consumed

python3 - <<'PY' || exit 1
import hashlib,json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-crystallize-manager-authorization-06-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/auth06-crystallize-free-result.json").read_text())
raw={k:v for k,v in a.items() if k!="authorization_sha256"}
sha=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert sha==a["authorization_sha256"]==f["authorization_sha256"]=="421795be22ddc505daade0e763a19e642f5ac115dfe1f877df8f0c99cb9dda48"
assert a["authorization_id"]==f["authorization_id"]=="P4-ONE-DAY-CRYSTALLIZE-20260925-06"
assert a["crystallization_source_head"]==f["source_head"]=="b3bb3901b7f50e028e5939c55195ebf347551777"
assert a["training_authorized"] is True and a["single_use"] is True
assert a["sealed_eval_consumed"] is False and a["worker05_used_for_tuning"] is False
assert f["paid_resource_created"] is False and not f["active_aqlevon_pods"]
assert float(a["fresh_authorization_spend_before_auth06_usd"])+float(a["max_total_cost_usd"]) <= float(a["owner_fresh_mission_authorization_usd"])
print("AQLEVON_AUTH06_PRESPEND_AUTH_PASS",sha)
PY

remote_head="$(git ls-remote https://github.com/$GITHUB_REPOSITORY.git refs/heads/agent/03-one-day-crystallization-20260925 | cut -f1)"
test "$remote_head" = "$SOURCE_HEAD" || die crystallization_source_head_moved

git fetch -q origin "$SOURCE_HEAD" "$W02_HEAD" || die git_fetch_failed
rm -rf /tmp/crystallize-payload
mkdir -p /tmp/crystallize-payload
git show "$SOURCE_HEAD":research/weight_factory/agent03/p4_one_day_crystallize.py >/tmp/crystallize-payload/crystallize.py || die crystallize_stage_failed
git show "$SOURCE_HEAD":research/weight_factory/agent03/p4_one_day_recovered_materializer.py >/tmp/crystallize-payload/materializer.py || die materializer_stage_failed
git show "$SOURCE_HEAD":research/weight_factory/agent03/auth05_recovered_material_decision.json >/tmp/crystallize-payload/auth05-recovered.json || die recovery_stage_failed
git show "$W02_HEAD":research/weight_factory/agent02/gene1_data_verifier_pack_v1.py >/tmp/crystallize-payload/w02.py || die w02_stage_failed
git show "$W02_HEAD":research/weight_factory/agent02/gene1_training_visible_pack_v1.json >/tmp/crystallize-payload/public-pack.json || die pack_stage_failed
cp "$REMOTE" /tmp/crystallize-payload/remote-runner.sh
python3 -m py_compile /tmp/crystallize-payload/crystallize.py /tmp/crystallize-payload/materializer.py || die py_compile_failed
python3 /tmp/crystallize-payload/materializer.py   --recovered-decision /tmp/crystallize-payload/auth05-recovered.json   --training-pack /tmp/crystallize-payload/public-pack.json   --output /tmp/crystallize-payload/materialized-probe.json >/tmp/materializer-preflight.log 2>&1 || die materializer_preflight_failed
python3 /tmp/crystallize-payload/crystallize.py   --probe-result /tmp/crystallize-payload/materialized-probe.json   --w02-module /tmp/crystallize-payload/w02.py   --training-pack /tmp/crystallize-payload/public-pack.json   --preflight-only >/tmp/crystallize-preflight.log 2>&1 || die crystallize_preflight_failed
grep -q 'train_verified=6 shadow=28 probe_decision=MATERIAL_LATENT_CAPABILITY' /tmp/crystallize-preflight.log || die preflight_contract_mismatch
python3 - <<'PY' || exit 1
import json
p=json.load(open("/tmp/crystallize-payload/materialized-probe.json"))
assert p["recovered_materialization"] is True
assert p["sealed_eval_consumed"] is False and p["worker05_used_for_tuning"] is False
d=[r for r in p["records"] if r["public_split"]=="discovery" and r["candidates"]]
s=[r for r in p["records"] if r["public_split"]=="shadow"]
assert len(d)==6 and len(s)==28 and all(not r["candidates"] for r in s)
print("AQLEVON_AUTH06_PUBLIC_BOUNDARY_PASS",len(d),len(s))
PY
sha256sum /tmp/crystallize-payload/* | tee /tmp/auth06-payload-sha256.txt
tar -czf /tmp/aqlevon-crystallize-payload.tgz -C /tmp/crystallize-payload .
test "$(stat -c %s /tmp/aqlevon-crystallize-payload.tgz)" -lt 20000000 || die payload_too_large
echo AQLEVON_AUTH06_SOURCE_STAGED_BEFORE_BILLING

if [ "${AQLEVON_FREE_CONTRACT_ONLY:-0}" = "1" ]; then
  echo AQLEVON_AUTH06_DRIVER_FREE_CONTRACT_PASS
  exit 0
fi

test -e "$TRIGGER" || die paid_trigger_missing
python3 - <<'PY' || exit 1
import json
a=json.load(open(".github/runpod-control/one-day-crystallize-manager-authorization-06-20260925.json"))
f=json.load(open(".github/runpod-control/auth06-crystallize-free-result.json"))
t=json.load(open(".github/runpod-control/execute-one-day-crystallize-06.json"))
assert t["authorization_id"]==a["authorization_id"]==f["authorization_id"]
assert t["authorization_sha256"]==a["authorization_sha256"]==f["authorization_sha256"]
assert t["expected_source_head"]==a["crystallization_source_head"]
assert t["training_authorized"] is True
print("AQLEVON_AUTH06_TRIGGER_PASS")
PY

curl -fsS https://rest.runpod.io/v1/pods -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pre-pods.json || die pod_inventory_failed
python3 - <<'PY' || exit 1
import json
pods=json.load(open("/tmp/pre-pods.json")); pods=pods if isinstance(pods,list) else pods.get("pods") or pods.get("items") or []
active=[p for p in pods if str(p.get("name","")).startswith("AQLEVON-") and str(p.get("desiredStatus") or p.get("status"))!="EXITED"]
assert not active,active
print("AQLEVON_AUTH06_NO_ACTIVE_PODS_PASS")
PY

curl -sSL https://cli.runpod.net | sudo bash >/dev/null || die runpodctl_install_failed
runpodctl gpu list --output json >/tmp/pre-gpus.json || die gpu_inventory_failed
python3 - <<'PY' || exit 1
import datetime,json
from pathlib import Path
a=json.load(open(".github/runpod-control/one-day-crystallize-manager-authorization-06-20260925.json"))
f=json.load(open(".github/runpod-control/auth06-crystallize-free-result.json"))
choices=[]; allowed=set(a["permitted_gpu_ids"])
for g in json.load(open("/tmp/pre-gpus.json")):
    gid=str(g.get("gpuId",""))
    if gid not in allowed or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in (g.get("dataCenterAvailability") or []):
        if str(d.get("stockStatus")).lower()!="none":
            seconds=min(int(a["max_billed_seconds"]),int(float(a["max_total_cost_usd"])*3600/price))
            if seconds>=1200: choices.append((price,gid,d.get("dataCenterId"),seconds))
assert choices,"no_permitted_live_stock_at_paid_boundary"
price,gpu,dc,seconds=sorted(choices)[0]
open("/tmp/selected_gpu","w").write(gpu)
open("/tmp/selected_dc","w").write(str(dc))
open("/tmp/selected_rate","w").write(str(price))
f.update({"selected_gpu_id":gpu,"selected_datacenter":dc,"selected_price_hr":price,
          "dynamic_max_billed_seconds":seconds,
          "paid_boundary_refresh_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "paid_boundary_refresh_committed_before_pod":True})
Path(".github/runpod-control/auth06-crystallize-free-result.json").write_text(json.dumps(f,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH06_LIVE_CAPACITY_SELECTED",gpu,dc,price,seconds)
PY
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$FREE"
if ! git diff --cached --quiet; then
  git commit -m "ops: persist Auth06 live GPU selection before spend [skip ci]" || die live_selection_commit_failed
  git push origin HEAD:ops/one-day-verified-trajectory-20260925 || die live_selection_push_failed
fi
test -z "$(git status --porcelain)" || die dirty_tree_before_auth06_pod

if [ "${AQLEVON_PRESPEND_ONLY:-0}" = "1" ]; then
  echo AQLEVON_AUTH06_PRESPEND_REFRESH_PASS
  exit 0
fi

ssh-keygen -q -t ed25519 -N '' -f /tmp/auth06_key || die ssh_key_failed
PUBKEY="$(cat /tmp/auth06_key.pub)"; export PUBKEY
env_json="$(python3 - <<'PY'
import json,os
print(json.dumps({"PUBLIC_KEY":os.environ["PUBKEY"]},separators=(",",":")))
PY
)"
runpodctl pod create --name AQLEVON-ONE-DAY-CRYSTALLIZE-06-20260925   --image "ghcr.io/india123445t-pixel/mus-ai@$IMAGE_DIGEST"   --gpu-id "$(cat /tmp/selected_gpu)" --gpu-count 1 --cloud-type SECURE   --data-center-ids "$(cat /tmp/selected_dc)" --container-disk-in-gb 40   --ports 22/tcp --env "$env_json" --output json >/tmp/create.json
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
echo "AQLEVON_AUTH06_POD_CREATED $pod"

emergency_stop_on_exit() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "${pod:-}" ]; then
    echo "AQLEVON_AUTH06_EXIT_TRAP_STOP pod=$pod status=$status"
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth06-exit-trap-stop.json || true
  fi
  return "$status"
}
trap emergency_stop_on_exit EXIT

python3 - <<'PY'
import datetime,json
from pathlib import Path
out={"authorization_id":"P4-ONE-DAY-CRYSTALLIZE-20260925-06",
     "authorization_sha256":"421795be22ddc505daade0e763a19e642f5ac115dfe1f877df8f0c99cb9dda48",
     "source_head":"b3bb3901b7f50e028e5939c55195ebf347551777",
     "image_digest":"sha256:ad4f48dd206b317e09d8fe1a834e57e79c444f9f581ebd45179c4072cb0d66ec",
     "pod_id":Path("/tmp/pod_id").read_text().strip(),
     "created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "single_use_consumed":True,"training_authorized":True}
Path(".github/runpod-control/one-day-crystallize-consumed-06.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
PY
git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$CONSUMED"
git commit -m "ops: consume Auth06 crystallization authorization [skip ci]" || die consumed_commit_failed
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || die consumed_push_failed

final_rc=255
remote_rc=255
result_ok=0
stop_ok=0
deleted=0
egress_ok=0

ready=0
for i in $(seq 1 180); do
  curl -sS "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/pod.json || true
  python3 - <<'PY'
import json,sys
try:p=json.load(open("/tmp/pod.json"))
except Exception:sys.exit(1)
rate=float(p.get("costPerHr") or 999)
if rate>2.00: sys.exit(2)
ip=p.get("publicIp"); port=(p.get("portMappings") or {}).get("22")
if p.get("desiredStatus")=="RUNNING" and ip and port:
    open("/tmp/ssh_target","w").write(str(ip)+"|"+str(port)); open("/tmp/live_rate","w").write(str(rate)); sys.exit(0)
sys.exit(1)
PY
  state=$?
  if [ "$state" -eq 0 ]; then ready=1; break; fi
  if [ "$state" -eq 2 ]; then final_rc=97; break; fi
  elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch) ))
  [ "$elapsed" -lt 900 ] || break
  sleep 5
done

if [ "$ready" -eq 1 ]; then
  rate="$(cat /tmp/live_rate)"
  dynamic="$(python3 - <<PY
rate=float("$rate")
print(min(1800,int(1.00*3600/rate)))
PY
)"
  printf '%s' "$dynamic" >/tmp/dynamic_seconds
  host="$(cut -d'|' -f1 /tmp/ssh_target)"; port="$(cut -d'|' -f2 /tmp/ssh_target)"
  cat >/tmp/hardware.py <<'PY'
import subprocess,torch
import transformers,peft,safetensors,huggingface_hub
name=subprocess.check_output(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],text=True).splitlines()[0].strip()
total=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],text=True).splitlines()[0])
assert total>=40000,(name,total)
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(),name
print("AQLEVON_AUTH06_HARDWARE_PASS",name,total,transformers.__version__,peft.__version__)
PY
  scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/hardware.py root@"$host":/tmp/hardware.py
  hw_rc=$?
  if [ "$hw_rc" -eq 0 ]; then
    ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host" python3 /tmp/hardware.py
    hw_rc=$?
  fi
  if [ "$hw_rc" -eq 0 ]; then
    scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/aqlevon-crystallize-payload.tgz root@"$host":/tmp/aqlevon-crystallize-payload.tgz
    payload_rc=$?
    if [ "$payload_rc" -eq 0 ]; then
      scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$REMOTE" root@"$host":/tmp/run-auth06.sh
      payload_rc=$?
    fi
    if [ "$payload_rc" -eq 0 ]; then
      ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"         'mkdir -p /workspace/aqlevon_one_day_crystallize; rm -f /workspace/aqlevon_one_day_crystallize/run.rc; nohup setsid bash /tmp/run-auth06.sh >/workspace/aqlevon_one_day_crystallize/supervisor.log 2>&1 < /dev/null &'
      launch_rc=$?
    else launch_rc=92; fi
    if [ "$launch_rc" -eq 0 ]; then
      echo AQLEVON_AUTH06_REMOTE_START
      for i in $(seq 1 180); do
        if ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 root@"$host"           'test -s /workspace/aqlevon_one_day_crystallize/run.rc' >/dev/null 2>&1; then
          remote_rc="$(ssh -i /tmp/auth06_key -p "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$host"             'cat /workspace/aqlevon_one_day_crystallize/run.rc' | tail -n1)"
          break
        fi
        elapsed=$(( $(date +%s) - $(cat /tmp/pod_created_epoch) ))
        if [ "$elapsed" -gt $((dynamic-60)) ]; then remote_rc=125; echo "FAIL_CLOSED_AUTH06_BILLING_WATCHDOG seconds=$elapsed"; break; fi
        sleep 8
      done
      [[ "$remote_rc" =~ ^[0-9]+$ ]] || remote_rc=255
      for file in train.log materializer.log model-stage.log supervisor.log; do
        scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null           root@"$host":/workspace/aqlevon_one_day_crystallize/$file /tmp/auth06-$file 2>/dev/null || true
      done
      scp -q -i /tmp/auth06_key -P "$port" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null         root@"$host":/workspace/aqlevon_one_day_crystallize/evidence.tgz /tmp/auth06-evidence.tgz 2>/tmp/auth06-egress.err && egress_ok=1 || true
      if [ "$remote_rc" -eq 0 ] && [ "$egress_ok" -eq 1 ]; then
        final_rc=0; result_ok=1
      else
        final_rc="$remote_rc"
      fi
    else final_rc="$launch_rc"; fi
  else final_rc="$hw_rc"; fi
else
  [ "$final_rc" -ne 255 ] || final_rc=90
fi

printf '%s\n' "$remote_rc" >/tmp/auth06_remote_rc
printf '%s\n' "$final_rc" >/tmp/auth06_final_rc

# stop exact paid Pod regardless of scientific outcome
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

# durable egress exists even for scientific FAIL if logs or evidence were copied
if [ "$stop_ok" -eq 1 ] && { [ "$egress_ok" -eq 1 ] || [ -s /tmp/auth06-train.log ] || [ -s /tmp/auth06-supervisor.log ]; }; then
  curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/delete.json || true
  for i in $(seq 1 20); do
    code="$(curl -sS -o /tmp/delete-probe.json -w '%{http_code}' "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
    if [ "$code" = "404" ]; then deleted=1; break; fi
    sleep 2
  done
fi

candidate_status=null
public_gate=null
if [ -s /tmp/auth06-evidence.tgz ]; then
  rm -rf /tmp/auth06-evidence
  mkdir -p /tmp/auth06-evidence
  tar -xzf /tmp/auth06-evidence.tgz -C /tmp/auth06-evidence || final_rc=98
  python3 - <<'PY' >/tmp/auth06-gate.txt || exit 98
import json
from pathlib import Path
root=Path("/tmp/auth06-evidence/output")
r=json.loads((root/"training_run_receipt.json").read_text())
m=json.loads((root/"candidate_artifact_manifest.json").read_text())
h=json.loads((root/"worker05_handoff_index.json").read_text())
assert r["sealed_eval_consumed"] is False and r["worker05_used_for_tuning"] is False
assert r["optimizer_updates"]==6 and r["target_modules"]==16 and r["adapter_tensors"]==32
assert r["changed_lora_B_elements"]>0 and r["save_reload_hash_match"] is True
assert m["sealed_eval_consumed"] is False and m["worker05_used_for_tuning"] is False
assert m["candidate_status"] in ("READY_FOR_WORKER05_EVALUATION","PUBLIC_SHADOW_GATE_FAILED")
assert h["candidate_status"]==m["candidate_status"]
print(m["candidate_status"])
print("true" if m["public_shadow_gate_pass"] else "false")
print("AQLEVON_AUTH06_ARTIFACT_GATE_PASS",m["candidate_status"],r["shadow_pre_pass_at_1"],r["shadow_post_pass_at_1"])
PY
  candidate_status="$(sed -n '1p' /tmp/auth06-gate.txt)"
  public_gate="$(sed -n '2p' /tmp/auth06-gate.txt)"
fi

python3 - <<PY
import datetime,hashlib,json
from pathlib import Path
def get(p):
    q=Path(p); return q.read_text().strip() if q.exists() else None
start=get("/tmp/pod_created_epoch")
elapsed=int(datetime.datetime.now(datetime.timezone.utc).timestamp())-int(start) if start else None
rate=get("/tmp/live_rate") or get("/tmp/selected_rate")
receipt=None; manifest=None
if Path("/tmp/auth06-evidence/output/training_run_receipt.json").exists():
    receipt=json.load(open("/tmp/auth06-evidence/output/training_run_receipt.json"))
if Path("/tmp/auth06-evidence/output/candidate_artifact_manifest.json").exists():
    manifest=json.load(open("/tmp/auth06-evidence/output/candidate_artifact_manifest.json"))
out={"kind":"AQLEVON_AUTH06_CRYSTALLIZATION_RUN_RECEIPT_V1","authorization_id":"$AUTH_ID","authorization_sha256":"$AUTH_SHA",
     "source_head":"$SOURCE_HEAD","w02_head":"$W02_HEAD","image_digest":"$IMAGE_DIGEST","pod_id":"$pod",
     "gpu_type":get("/tmp/selected_gpu"),"rate_per_hour_usd":rate,"billed_seconds_estimate":elapsed,
     "compute_cost_estimate_usd":round(float(rate)*elapsed/3600,6) if rate and elapsed is not None else None,
     "remote_exit_code":int(get("/tmp/auth06_remote_rc")) if get("/tmp/auth06_remote_rc") and get("/tmp/auth06_remote_rc").isdigit() else None,
     "final_exit_code":int(get("/tmp/auth06_final_rc")) if get("/tmp/auth06_final_rc") and get("/tmp/auth06_final_rc").isdigit() else None,
     "pod_status":(json.load(open("/tmp/stop-probe.json")).get("desiredStatus") if Path("/tmp/stop-probe.json").exists() else None),
     "pod_deleted_after_egress":bool($deleted),"evidence_present":Path("/tmp/auth06-evidence.tgz").exists(),
     "evidence_sha256":hashlib.sha256(Path("/tmp/auth06-evidence.tgz").read_bytes()).hexdigest() if Path("/tmp/auth06-evidence.tgz").exists() else None,
     "candidate_status":(manifest or {}).get("candidate_status"),"public_shadow_gate_pass":(manifest or {}).get("public_shadow_gate_pass"),
     "shadow_pre_pass_at_1":(receipt or {}).get("shadow_pre_pass_at_1"),"shadow_post_pass_at_1":(receipt or {}).get("shadow_post_pass_at_1"),
     "shadow_gain_tasks":(receipt or {}).get("shadow_gain_tasks"),"save_reload_hash_match":(receipt or {}).get("save_reload_hash_match"),
     "sealed_eval_consumed":False,"worker05_used_for_tuning":False,"capability_gain_claim":False,
     "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
Path("$RESULT").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH06_RUN_RECEIPT",json.dumps(out,sort_keys=True))
PY

git add "$RESULT"
git commit -m "ops: record Auth06 crystallization result [skip ci]" || true
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || true

test "$final_rc" -eq 0 || exit "$final_rc"
test "$stop_ok" -eq 1 || exit 97
test "$deleted" -eq 1 || exit 96
test "$result_ok" -eq 1 || exit 95
