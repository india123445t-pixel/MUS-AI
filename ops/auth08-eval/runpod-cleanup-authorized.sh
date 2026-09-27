#!/usr/bin/env bash
set -euo pipefail
AUTH="ops/auth08-eval/runpod-cleanup-authorization.json"
python3 - "$AUTH" <<'PY'
import json,sys
a=json.load(open(sys.argv[1]))
assert a["kind"]=="AQLEVON_RUNPOD_STORAGE_CLEANUP_AUTHORIZATION_V1"
assert a["authorization_id"]=="AQLEVON-RUNPOD-CLEANUP-20260927-01"
assert a["fresh_authorization"] is True and a["single_use"] is True
assert a["destructive_cleanup_authorized"] is True and a["consumed"] is False
assert a["delete_pod_ids"]==["a6hxcy4h40l5gd","v3njg70l4mtazn"]
assert a["protected_pod_id"]=="hjwspv5aqtnqxd"
assert a["no_gpu_start"] is True and a["no_inference"] is True and a["no_model_dispatch"] is True
print("AQLEVON_CLEANUP_AUTH_PASS")
PY

test -n "${RUNPOD_API_KEY:-}"
query_inventory() {
cat >/tmp/inv-q.json <<'JSON'
{"query":"query { myself { clientBalance currentSpendPerHr pods { id name desiredStatus volumeInGb volumeMountPath networkVolumeId } } }"}
JSON
curl -fsS -X POST -H "content-type: application/json"  --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY"  --data-binary @/tmp/inv-q.json
}
query_inventory >/tmp/pre.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/pre.json")); assert not d.get("errors"),d
me=d["data"]["myself"]; pods={p["id"]:p for p in me["pods"]}
for pid in ("a6hxcy4h40l5gd","v3njg70l4mtazn","hjwspv5aqtnqxd"):
    assert pid in pods, (pid,pods.keys())
    assert pods[pid]["desiredStatus"]=="EXITED", pods[pid]
p=pods["hjwspv5aqtnqxd"]
assert p["volumeInGb"]==100 and p["volumeMountPath"]=="/workspace"
print("AQLEVON_CLEANUP_PRECHECK_PASS",json.dumps({"balance":me["clientBalance"],"spend_per_hr":me["currentSpendPerHr"],"protected":p},sort_keys=True))
PY

claim="ops/auth08-eval/claims/AQLEVON-RUNPOD-CLEANUP-20260927-01.cleanup.consumed.json"
python3 - "$claim" <<'PY'
import json,os,sys,datetime
p=sys.argv[1]
obj={
 "kind":"AQLEVON_RUNPOD_STORAGE_CLEANUP_CLAIM_V1",
 "authorization_id":"AQLEVON-RUNPOD-CLEANUP-20260927-01",
 "consumed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "delete_pod_ids":["a6hxcy4h40l5gd","v3njg70l4mtazn"],
 "protected_pod_id":"hjwspv5aqtnqxd",
 "evidence_preconditions_verified":True
}
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f: json.dump(obj,f,indent=2); f.write("\n")
PY
git config user.name aqlevon-control
git config user.email aqlevon-control@users.noreply.github.com
git add "$claim"
git commit -m "ops: consume Runpod storage cleanup authorization"
git pull --rebase origin manager/auth08-unified-eval-20260927
git push origin HEAD:manager/auth08-unified-eval-20260927
echo AQLEVON_CLEANUP_CLAIM_DURABLE

for pid in a6hxcy4h40l5gd v3njg70l4mtazn; do
  code=$(curl -sS -o "/tmp/delete-$pid.out" -w "%{http_code}" -X DELETE     -H "Authorization: Bearer $RUNPOD_API_KEY"     "https://rest.runpod.io/v1/pods/$pid")
  echo "AQLEVON_CLEANUP_DELETE_RESPONSE $pid HTTP=$code BODY=$(cat /tmp/delete-$pid.out)"
  case "$code" in 200|202|204) ;; *) echo "unexpected delete status for $pid" >&2; exit 41;; esac
done

for i in 1 2 3 4 5 6; do
  query_inventory >/tmp/post.json
  if python3 - <<'PY'
import json
d=json.load(open("/tmp/post.json")); assert not d.get("errors"),d
me=d["data"]["myself"]; pods={p["id"]:p for p in me["pods"]}
ok=("a6hxcy4h40l5gd" not in pods and "v3njg70l4mtazn" not in pods and "hjwspv5aqtnqxd" in pods and pods["hjwspv5aqtnqxd"]["desiredStatus"]=="EXITED")
raise SystemExit(0 if ok else 1)
PY
  then break; fi
  sleep 5
done
python3 - <<'PY'
import json
d=json.load(open("/tmp/post.json")); assert not d.get("errors"),d
me=d["data"]["myself"]; pods={p["id"]:p for p in me["pods"]}
assert "a6hxcy4h40l5gd" not in pods, pods
assert "v3njg70l4mtazn" not in pods, pods
assert "hjwspv5aqtnqxd" in pods, pods
p=pods["hjwspv5aqtnqxd"]
assert p["desiredStatus"]=="EXITED"
assert p["volumeInGb"]==100 and p["volumeMountPath"]=="/workspace"
print("AQLEVON_CLEANUP_SUCCESS",json.dumps({"balance":me["clientBalance"],"spend_per_hr":me["currentSpendPerHr"],"remaining_pods":list(pods.values()),"protected":p},sort_keys=True))
PY
