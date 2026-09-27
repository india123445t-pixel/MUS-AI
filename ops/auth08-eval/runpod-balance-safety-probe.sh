#!/usr/bin/env bash
set -euo pipefail
test -n "${RUNPOD_API_KEY:-}"
cat >/tmp/q.json <<'JSON'
{"query":"query { myself { clientBalance underBalance minBalance currentSpendPerHr activeMigrations { id } } pod(input: { podId: \"hjwspv5aqtnqxd\" }) { id desiredStatus networkVolumeId volumeInGb volumeMountPath } }"}
JSON
curl -fsS -X POST -H "content-type: application/json" \
  --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  --data-binary @/tmp/q.json >/tmp/account.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/account.json"))
assert not d.get("errors"), d
me=d["data"]["myself"]; p=d["data"]["pod"]
out={
 "clientBalance":me.get("clientBalance"),
 "underBalance":me.get("underBalance"),
 "minBalance":me.get("minBalance"),
 "currentSpendPerHr":me.get("currentSpendPerHr"),
 "activeMigrationCount":len(me.get("activeMigrations") or []),
 "podId":p.get("id"),
 "podDesiredStatus":p.get("desiredStatus"),
 "networkVolumeId":p.get("networkVolumeId"),
 "volumeInGb":p.get("volumeInGb"),
 "volumeMountPath":p.get("volumeMountPath")
}
print("AQLEVON_RUNPOD_BALANCE_SAFETY",json.dumps(out,sort_keys=True))
PY
