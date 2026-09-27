#!/usr/bin/env bash
set -euo pipefail

RESULT="${AQLEVON_RESULT_PATH:-.github/runpod-control/aqlevon-27b-r0-preserve-result-02.json}"
VERIFY_MARKER=/tmp/aq27-evidence-verified.json
pod="$(cat /tmp/aq27-pod 2>/dev/null || true)"
outcome="${AQLEVON_PRESERVE_OUTCOME:-}"
artifact_id="${AQLEVON_ARTIFACT_ID:-}"
artifact_url="${AQLEVON_ARTIFACT_URL:-}"
artifact_digest="${AQLEVON_ARTIFACT_DIGEST:-}"

stop_pod() {
  if [ -n "$pod" ]; then
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" \
      -H "Authorization: Bearer $RUNPOD_API_KEY" \
      -H 'Content-Type: application/json' -d '{}' >/tmp/aq27-finalize-stop.json || true
  fi
}

record_result() {
  local state="$1"
  local deleted="$2"
  if [ ! -f "$RESULT" ]; then
    return 0
  fi
  AQ_STATE="$state" AQ_DELETED="$deleted" AQ_ARTIFACT_ID="$artifact_id" \
  AQ_ARTIFACT_URL="$artifact_url" AQ_ARTIFACT_DIGEST="$artifact_digest" RESULT="$RESULT" \
  python3 - <<'PY'
import datetime,json,os
from pathlib import Path
p=Path(os.environ["RESULT"])
out=json.loads(p.read_text())
out["artifact_preservation_state"]=os.environ["AQ_STATE"]
out["pod_stopped_and_deleted"]=os.environ["AQ_DELETED"].lower()=="true"
out["preservation_checked_at_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
if os.environ.get("AQ_ARTIFACT_ID"):
    out["github_artifact_id"]=os.environ["AQ_ARTIFACT_ID"]
if os.environ.get("AQ_ARTIFACT_URL"):
    out["github_artifact_url"]=os.environ["AQ_ARTIFACT_URL"]
if os.environ.get("AQ_ARTIFACT_DIGEST"):
    out["github_artifact_digest"]=os.environ["AQ_ARTIFACT_DIGEST"]
v=Path("/tmp/aq27-evidence-verified.json")
if v.exists():
    out["artifact_verification"]=json.loads(v.read_text())
p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
PY
  git config user.name aqlevon-runpod-bot
  git config user.email actions@users.noreply.github.com
  git add "$RESULT"
  git commit -m "ops: record AQLEVON 27B artifact preservation state [skip ci]" || true
  git fetch origin ops/runpod-control-v1
  git rebase origin/ops/runpod-control-v1
  git push origin HEAD:ops/runpod-control-v1
}

# Fail closed: upload success, durable artifact identity, and pre-upload SHA verification
# are all mandatory before the pod may be deleted.
if [ "$outcome" != "success" ] || [ -z "$artifact_id" ] || [ ! -s "$VERIFY_MARKER" ]; then
  stop_pod
  record_result "DURABLE_UPLOAD_FAILED_POD_STOPPED_NOT_DELETED" "false"
  echo "AQLEVON_27B_PRESERVATION_FAIL_CLOSED"
  exit 86
fi
if ! printf '%s' "$artifact_digest" | grep -Eq '^(sha256:)?[0-9a-fA-F]{64}$'; then
  stop_pod
  record_result "DURABLE_UPLOAD_DIGEST_INVALID_POD_STOPPED_NOT_DELETED" "false"
  echo "AQLEVON_27B_PRESERVATION_DIGEST_FAIL_CLOSED"
  exit 87
fi

# The execution step already stopped GPU billing. Delete only after the
# actions/upload-artifact step has completed successfully.
stop_pod
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" >/tmp/aq27-finalize-delete.json || true
cleaned=0
for _ in $(seq 1 45); do
  code="$(curl -sS -o /tmp/aq27-finalize-status.json -w '%{http_code}' \
    "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer $RUNPOD_API_KEY" || true)"
  if [ "$code" = 404 ]; then
    cleaned=1
    break
  fi
  sleep 2
done
if [ "$cleaned" != 1 ]; then
  record_result "DURABLE_UPLOAD_VERIFIED_POD_DELETE_UNCONFIRMED" "false"
  echo "AQLEVON_27B_POD_DELETE_UNCONFIRMED"
  exit 88
fi

record_result "DURABLE_UPLOAD_VERIFIED_POD_DELETED" "true"
echo "AQLEVON_27B_DURABLE_ARTIFACT_BEFORE_DELETE_PASS artifact_id=$artifact_id"
