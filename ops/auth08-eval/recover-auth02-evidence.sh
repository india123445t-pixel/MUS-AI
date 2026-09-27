#!/usr/bin/env bash
set -euo pipefail

POD_ID="hjwspv5aqtnqxd"
AUTH="ops/auth08-eval/recovery-authorization.json"
CLAIMS_DIR="ops/auth08-eval/claims"
MAX_RUNTIME_SECONDS=300
OUT="/tmp/auth08-recovery"
STARTED=0

cleanup() {
  rc=$?
  set +e
  if [ "$STARTED" = 1 ]; then
    curl -fsS -X POST "https://rest.runpod.io/v1/pods/$POD_ID/stop" \
      -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/recovery-stop.json 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT

test -n "${RUNPOD_API_KEY:-}"
test -n "${GH_TOKEN:-}"
test -n "${GITHUB_RUN_ID:-}"
test -f "$AUTH"
mkdir -p "$OUT"

python3 - <<'PY'
import json
a=json.load(open("ops/auth08-eval/recovery-authorization.json"))
assert a["kind"]=="AQLEVON_AUTH08_EVIDENCE_RECOVERY_AUTHORIZATION_V1"
assert a["fresh_authorization"] is True
assert a["single_use"] is True
assert a["artifact_recovery_authorized"] is True
assert a["no_inference"] is True and a["no_model_dispatch"] is True
assert a["target_pod_id"]=="hjwspv5aqtnqxd"
assert float(a["max_total_cost_usd"]) <= 0.20
assert float(a["max_hourly_rate_usd"]) <= 1.60
assert int(a["max_billed_seconds"]) <= 300
assert a["consumed"] is False
print("AQLEVON_AUTH02_RECOVERY_AUTH_PASS")
PY

AUTH_ID="$(python3 -c 'import json; print(json.load(open("ops/auth08-eval/recovery-authorization.json"))["authorization_id"])')"
test -n "$AUTH_ID"
CLAIM="$CLAIMS_DIR/$AUTH_ID.recovery.consumed.json"
test ! -e "$CLAIM"
python3 - "$CLAIM" "$AUTH_ID" "$GITHUB_RUN_ID" <<'PY'
import json,os,sys,tempfile,datetime as dt
p,aid,run_id=sys.argv[1:]
os.makedirs(os.path.dirname(p),exist_ok=True)
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f:
    json.dump({
      "kind":"AQLEVON_AUTH08_EVIDENCE_RECOVERY_CONSUMPTION_V1",
      "authorization_id":aid,
      "run_id":run_id,
      "target_pod_id":"hjwspv5aqtnqxd",
      "consumed_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "no_inference":True,
      "no_model_dispatch":True,
      "state":"CONSUMED_BEFORE_PROVIDER_START"
    },f,indent=2,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
PY

git config user.name "aqlevon-manager-bot"
git config user.email "aqlevon-manager-bot@users.noreply.github.com"
git add "$CLAIM"
git commit -m "eval: consume Auth02 evidence-recovery authorization [skip ci]"
git fetch origin manager/auth08-unified-eval-20260927
git rebase origin/manager/auth08-unified-eval-20260927
git push origin HEAD:manager/auth08-unified-eval-20260927
echo AQLEVON_AUTH02_RECOVERY_CLAIM_DURABLE

curl -fsS "https://rest.runpod.io/v1/pods/$POD_ID" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" >"$OUT/pod-before.json"
python3 - "$OUT/pod-before.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("desiredStatus")=="EXITED",d
assert float(d.get("costPerHr") or 999) <= 1.60,d
assert int(d.get("volumeInGb") or 0) == 100,d
assert d.get("volumeMountPath")=="/workspace",d
print("AQLEVON_AUTH02_RECOVERY_STOPPED_VOLUME_PASS")
PY

cat > /tmp/recovery-patch.json <<'JSON'
{
  "dockerEntrypoint": ["/bin/bash", "-lc"],
  "dockerStartCmd": ["exec python3 -m http.server 8000 --directory /workspace/aqlevon-auth08-eval"],
  "ports": ["8000/http"],
  "volumeInGb": 100,
  "volumeMountPath": "/workspace"
}
JSON

curl -fsS -X PATCH "https://rest.runpod.io/v1/pods/$POD_ID" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/recovery-patch.json >"$OUT/pod-patch.json"
python3 - "$OUT/pod-patch.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
cmd=d.get("dockerStartCmd") or []
assert any("http.server 8000" in str(x) for x in cmd),d
assert int(d.get("volumeInGb") or 0)==100,d
assert d.get("volumeMountPath")=="/workspace",d
print("AQLEVON_AUTH02_RECOVERY_NO_INFERENCE_BOOT_PASS")
PY

cat > /tmp/zero-gpu-resume.json <<'JSON'
{"query":"mutation { podResume(input: { podId: \"hjwspv5aqtnqxd\", gpuCount: 0 }) { id desiredStatus imageName } }"}
JSON
curl -fsS -X POST \
  -H "content-type: application/json" \
  --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  --data-binary @/tmp/zero-gpu-resume.json >"$OUT/pod-start-zero-gpu.json"
python3 - "$OUT/pod-start-zero-gpu.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert not d.get("errors"),d
p=(d.get("data") or {}).get("podResume")
assert p and p.get("id")=="hjwspv5aqtnqxd",d
assert p.get("desiredStatus")=="RUNNING",d
print("AQLEVON_AUTH02_RECOVERY_ZERO_GPU_RESUME_ACCEPTED")
PY
STARTED=1
date +%s >/tmp/recovery-start

cat > /tmp/zero-gpu-runtime-query.json <<'JSON'
{"query":"query { pod(input: { podId: \"hjwspv5aqtnqxd\" }) { id desiredStatus runtime { uptimeInSeconds gpus { id } } } }"}
JSON
zero_gpu_ready=0
for _ in $(seq 1 30); do
  curl -fsS -X POST \
    -H "content-type: application/json" \
    --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
    --data-binary @/tmp/zero-gpu-runtime-query.json >"$OUT/pod-runtime.json" || true
  if python3 - "$OUT/pod-runtime.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
if d.get("errors"):
    raise SystemExit(1)
p=(d.get("data") or {}).get("pod") or {}
rt=p.get("runtime")
if not rt:
    raise SystemExit(1)
gpus=rt.get("gpus")
if gpus is None:
    raise SystemExit(1)
if len(gpus) != 0:
    raise SystemExit(2)
print("AQLEVON_AUTH02_RECOVERY_RUNTIME_ZERO_GPU_VERIFIED")
PY
  then
    zero_gpu_ready=1
    break
  else
    rc=$?
    if [ "$rc" = "2" ]; then
      echo AQLEVON_AUTH02_RECOVERY_GPU_PRESENT_FAIL
      exit 52
    fi
  fi
  sleep 2
done
test "$zero_gpu_ready" = 1
proxy="https://$POD_ID-8000.proxy.runpod.net"

ready=0
for _ in $(seq 1 60); do
  now="$(date +%s)"
  elapsed=$((now-$(cat /tmp/recovery-start)))
  if [ "$elapsed" -ge "$MAX_RUNTIME_SECONDS" ]; then break; fi
  if curl -fsS --connect-timeout 5 --max-time 10 "$proxy/" -o "$OUT/root-listing.html" 2>/dev/null; then
    ready=1; break
  fi
  sleep 5
done
test "$ready" = 1

fetch_optional() {
  local path="$1" dest="$2"
  if curl -fsS --connect-timeout 5 --max-time 120 "$proxy/$path" -o "$OUT/$dest" 2>/dev/null; then
    test -s "$OUT/$dest" || rm -f "$OUT/$dest"
  else
    rm -f "$OUT/$dest"
  fi
}

fetch_optional "status.json" "status.json"
fetch_optional "eval.log" "eval.log"
fetch_optional "evidence.tgz" "evidence.tgz"
fetch_optional "evidence.sha256" "evidence.sha256"
fetch_optional "results/generalization-results.json" "generalization-results.json"
fetch_optional "results/paired-public-results.jsonl" "paired-public-results.jsonl"
fetch_optional "results/runtime-receipt.json" "runtime-receipt.json"

python3 - "$OUT" <<'PY'
from pathlib import Path
import json,hashlib,sys,time
root=Path(sys.argv[1])
names=["status.json","eval.log","evidence.tgz","evidence.sha256","generalization-results.json","paired-public-results.jsonl","runtime-receipt.json"]
files={}
for n in names:
    p=root/n
    if p.is_file():
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        files[n]={"size":p.stat().st_size,"sha256":h}
report={
  "kind":"AQLEVON_AUTH02_EVIDENCE_RECOVERY_REPORT_V1",
  "target_pod_id":"hjwspv5aqtnqxd",
  "no_inference":True,
  "no_model_dispatch":True,
  "files":files,
  "full_evidence_present":"evidence.tgz" in files,
  "complete_result_triplet_present":all(x in files for x in ["generalization-results.json","paired-public-results.jsonl","runtime-receipt.json"]),
  "generated_at_epoch":time.time()
}
(root/"recovery-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
(root/"full-evidence.flag").write_text("1\n" if report["full_evidence_present"] else "0\n")
print("AQLEVON_AUTH02_RECOVERY_REPORT",json.dumps(report,sort_keys=True))
PY

curl -fsS -X POST "https://rest.runpod.io/v1/pods/$POD_ID/stop" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" >"$OUT/pod-stop.json" || true
STARTED=0
trap - EXIT
echo AQLEVON_AUTH02_RECOVERY_STOPPED
