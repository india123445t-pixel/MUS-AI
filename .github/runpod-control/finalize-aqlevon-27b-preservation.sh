#!/usr/bin/env bash
set -euo pipefail

RESULT="${AQLEVON_RESULT_PATH:-.github/runpod-control/aqlevon-27b-r0-preserve-result-02.json}"
VERIFY_MARKER="${AQLEVON_VERIFY_MARKER_PATH:-/tmp/aq27-evidence-verified.json}"
POD_FILE="${AQLEVON_POD_FILE:-/tmp/aq27-pod}"
pod="$(cat "$POD_FILE" 2>/dev/null || true)"
outcome="${AQLEVON_PRESERVE_OUTCOME:-}"
artifact_id="${AQLEVON_ARTIFACT_ID:-}"
artifact_url="${AQLEVON_ARTIFACT_URL:-}"
artifact_digest="${AQLEVON_ARTIFACT_DIGEST:-}"

stop_pod() {
  if [ -n "$pod" ]; then
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" \
      -H "Authorization: Bearer ${RUNPOD_API_KEY:-}" \
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
  AQ_ARTIFACT_URL="$artifact_url" AQ_ARTIFACT_DIGEST="$artifact_digest" \
  AQ_VERIFY_MARKER="$VERIFY_MARKER" RESULT="$RESULT" \
  python3 - <<'PY'
import datetime
import json
import os
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
v=Path(os.environ.get("AQ_VERIFY_MARKER", "/tmp/aq27-evidence-verified.json"))
if v.exists():
    verification=json.loads(v.read_text())
    out["artifact_verification"]=verification
    if verification.get("runtime_versions"):
        out["runtime_versions"]=verification["runtime_versions"]
    if verification.get("runtime_versions_sha256"):
        out["runtime_versions_sha256"]=verification["runtime_versions_sha256"]
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

# Fail closed: upload success, durable artifact identity, and pre-upload SHA
# verification are mandatory before the pod may be deleted.
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

# Runtime package identity must be present in the verified evidence before
# deletion. This makes exact runtime versions durable in both artifact and result.
if ! python3 - "$VERIFY_MARKER" <<'PY'
import json
import sys

x=json.load(open(sys.argv[1]))
assert x.get("kind")=="AQLEVON_27B_ARTIFACT_VERIFICATION_V2"
rv=x.get("runtime_versions")
assert isinstance(rv,dict) and rv.get("kind")=="AQLEVON_27B_RUNTIME_VERSIONS_V1"
pkgs=rv.get("packages")
assert isinstance(pkgs,dict)
for name in ("torch","transformers","peft","accelerate","huggingface-hub","safetensors"):
    assert str(pkgs.get(name) or "").strip(), name
assert str(rv.get("python") or "").strip()
assert len(str(x.get("runtime_versions_sha256") or ""))==64
PY
then
  stop_pod
  record_result "RUNTIME_VERSION_RECEIPT_INVALID_POD_STOPPED_NOT_DELETED" "false"
  echo "AQLEVON_27B_RUNTIME_VERSION_RECEIPT_FAIL_CLOSED"
  exit 89
fi

# The execution step already stopped GPU billing. Delete only after the
# actions/upload-artifact step has completed successfully and all gates pass.
stop_pod
curl -sS -X DELETE "https://rest.runpod.io/v1/pods/$pod" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY:-}" >/tmp/aq27-finalize-delete.json || true
cleaned=0
for _ in $(seq 1 45); do
  code="$(curl -sS -o /tmp/aq27-finalize-status.json -w '%{http_code}' \
    "https://rest.runpod.io/v1/pods/$pod" -H "Authorization: Bearer ${RUNPOD_API_KEY:-}" || true)"
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
