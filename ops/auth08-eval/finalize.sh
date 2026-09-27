#!/usr/bin/env bash
set -euo pipefail

RESULT=ops/auth08-eval/result.json
UPLOAD_OUTCOME="${UPLOAD_OUTCOME:-}"
ARTIFACT_ID="${ARTIFACT_ID:-}"
ARTIFACT_DIGEST="${ARTIFACT_DIGEST:-}"
RUNPOD_API_KEY="${RUNPOD_API_KEY:-}"

test "$UPLOAD_OUTCOME" = "success"
test -n "$ARTIFACT_ID"
test -n "$ARTIFACT_DIGEST"
case "$ARTIFACT_DIGEST" in
  sha256:[0-9a-fA-F][0-9a-fA-F]*|[0-9a-fA-F][0-9a-fA-F]*) ;;
  *) echo invalid_artifact_digest; exit 11;;
esac
test -f "$RESULT"
test -s /tmp/stopped-pod
pod="$(cat /tmp/stopped-pod)"
test -n "$pod"

python3 - <<'PY'
import json,os,re
p="ops/auth08-eval/result.json"
d=json.load(open(p))
assert d.get("final_stage")=="DONE",d
assert d.get("artifact_preservation_state")=="PENDING_DURABLE_UPLOAD",d
aid=os.environ["ARTIFACT_ID"]
digest=os.environ["ARTIFACT_DIGEST"]
assert aid
assert re.fullmatch(r"(?:sha256:)?[0-9a-fA-F]{64}",digest),digest
d["artifact_preservation_state"]="DURABLY_UPLOADED"
d["github_artifact_id"]=int(aid)
d["github_artifact_digest"]=digest
open(p,"w").write(json.dumps(d,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH08_EVAL_DURABLE_ARTIFACT_BEFORE_DELETE_PASS",aid)
PY

test -n "$RUNPOD_API_KEY"
curl -fsS -X DELETE "https://rest.runpod.io/v1/pods/$pod"   -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/delete.json || {
    echo AQLEVON_AUTH08_EVAL_DELETE_FAILED_POD_REMAINS_STOPPED "$pod"
    exit 12
  }

python3 - <<'PY'
import json
p="ops/auth08-eval/result.json"
d=json.load(open(p))
d["pod_stopped_and_deleted"]=True
open(p,"w").write(json.dumps(d,indent=2,sort_keys=True)+"\n")
PY

git config user.name "aqlevon-manager-bot"
git config user.email "aqlevon-manager-bot@users.noreply.github.com"
git add "$RESULT"
git commit -m "eval: finalize durable Auth08 public eval artifact [skip ci]"
git fetch origin manager/auth08-unified-eval-20260927
git rebase origin/manager/auth08-unified-eval-20260927
git push origin HEAD:manager/auth08-unified-eval-20260927
echo AQLEVON_AUTH08_EVAL_FINALIZER_DONE
