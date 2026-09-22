#!/usr/bin/env bash
set -Eeuo pipefail

REPO_FULL="india123445t-pixel/MUS-AI"
WORKER_BRANCH="agent/03-p4-gene1-physical-trainer"
EXPECTED_W03_HEAD="3d305380ec124c2acb40070ed9e0b7c9cb95d7af"
AUTH="research/weight_factory/agent03/p4_a1_runpod_manager_authorization_retry18f_api_control_v1.json"
BIND="research/weight_factory/agent03/p4_a1_runtime_appliance_binding_retry18f_api_control_v1.json"
LAUNCH_PATH="research/weight_factory/agent03/p4_runpod_appliance_launch.sh"
POD_NAME="AQLEVON-P4-A1-R18F-API"
GPU_ID="NVIDIA GeForce RTX 4090"
IMAGE="ghcr.io/india123445t-pixel/mus-ai@sha256:ecfe9d199a56333da7655a63a750fc6466d27fd1ed91d60aaa3e2c4b0a3dd69d"
MAX_RATE="0.80"
MAX_EGRESS="5368709120"
HARD_SECONDS="1750"
ARTIFACT_MARGIN="90"
OUTDIR="retry18f-local"

mkdir -p "$OUTDIR"
POD_ID=""
SSH_FP=""
KEY="$RUNNER_TEMP/aqlevon-r18f"
POD_BIRTH="$(date +%s)"
RESULT="PRE_CREATE_FAILURE"
ARTIFACT_RECEIVED=false
ACTUAL_RATE=""

write_receipt() {
  python3 - "$OUTDIR/result.json" "$RESULT" "$ARTIFACT_RECEIVED" "$ACTUAL_RATE" <<'PY'
import json,sys
path,result,artifact,rate=sys.argv[1:]
obj={
 "schema_version":1,
 "run":"Retry18F",
 "authorization_id":"P4-A1-RUNPOD-4090-20260922-18F-API-CONTROL",
 "authorization_sha256":"1230f46291e2d1be22c7ac4c4d758666ef41348872488e528faceb3f21c69b57",
 "worker03_head":"3d305380ec124c2acb40070ed9e0b7c9cb95d7af",
 "runtime_image":"ghcr.io/india123445t-pixel/mus-ai@sha256:ecfe9d199a56333da7655a63a750fc6466d27fd1ed91d60aaa3e2c4b0a3dd69d",
 "result":result,
 "artifact_received":artifact.lower()=="true",
 "gpu_rate_usd_per_hr":rate,
 "max_authorized_cost_usd":"0.40",
 "max_authorized_billed_seconds":1800,
 "hard_cleanup_seconds":1750,
 "secret_exposed":False,
 "main_modified":False
}
with open(path,"w") as f:
    json.dump(obj,f,sort_keys=True,separators=(",",":"))
    f.write("\n")
PY
}

cleanup() {
  set +e
  if [ -n "$POD_ID" ]; then
    runpodctl pod delete "$POD_ID" >/dev/null 2>&1 || true
  fi
  if [ -n "$SSH_FP" ]; then
    runpodctl ssh remove-key --fingerprint "$SSH_FP" >/dev/null 2>&1 || true
  fi
  rm -f "$KEY" "$KEY.pub"
  write_receipt || true
}
trap cleanup EXIT INT TERM

test -n "${RUNPOD_API_KEY:-}" || { RESULT="NO_RUNPOD_KEY"; exit 20; }
test -f "$AUTH" -a -f "$BIND" || { RESULT="CONTRACT_FILES_MISSING"; exit 21; }

test "$(jq -r .authorization_id "$AUTH")" = "P4-A1-RUNPOD-4090-20260922-18F-API-CONTROL" || { RESULT="AUTH_ID_MISMATCH"; exit 22; }
test "$(jq -r .authorization_sha256 "$AUTH")" = "1230f46291e2d1be22c7ac4c4d758666ef41348872488e528faceb3f21c69b57" || { RESULT="AUTH_SHA_MISMATCH"; exit 23; }
test "$(jq -r .max_billed_seconds "$AUTH")" = "1800" || { RESULT="BILL_SECONDS_MISMATCH"; exit 24; }
test "$(jq -r .max_hourly_rate_usd "$AUTH")" = "0.80" || { RESULT="RATE_CEILING_MISMATCH"; exit 25; }
test "$(jq -r .max_total_cost_usd "$AUTH")" = "0.40" || { RESULT="COST_CEILING_MISMATCH"; exit 26; }
test "$(jq -r .profile_id "$AUTH")" = "p4-surrogate-1x24" || { RESULT="PROFILE_MISMATCH"; exit 27; }
test "$(jq -r .run_manifest_sha256 "$AUTH")" = "24e3d21155c3f1011ca92f90e6c622fe03f92bfd65656d31d87fa627886fad47" || { RESULT="MANIFEST_MISMATCH"; exit 28; }
test "$(jq -r .single_use "$AUTH")" = "true" || { RESULT="NOT_SINGLE_USE"; exit 29; }

test "$(jq -r .authorization_sha256 "$BIND")" = "1230f46291e2d1be22c7ac4c4d758666ef41348872488e528faceb3f21c69b57" || { RESULT="BIND_AUTH_MISMATCH"; exit 30; }
test "$(jq -r .run_manifest_sha256 "$BIND")" = "24e3d21155c3f1011ca92f90e6c622fe03f92bfd65656d31d87fa627886fad47" || { RESULT="BIND_MANIFEST_MISMATCH"; exit 31; }
test "$(jq -r .command_lock_sha256 "$BIND")" = "b07441e07d0f26191fc5bd20ebf61e61c88003c542205687a2679243d90623c2" || { RESULT="BIND_LOCK_MISMATCH"; exit 32; }
test "$(jq -r .runtime_appliance_image "$BIND")" = "$IMAGE" || { RESULT="IMAGE_BINDING_MISMATCH"; exit 33; }

LIVE_HEAD="$(git ls-remote "https://github.com/$REPO_FULL.git" "refs/heads/$WORKER_BRANCH" | awk '{print $1}')"
test "$LIVE_HEAD" = "$EXPECTED_W03_HEAD" || { RESULT="WORKER_HEAD_DRIFT"; exit 34; }

runpodctl user >/dev/null || { RESULT="RUNPOD_AUTH_FAILURE"; exit 35; }
EXISTING="$(runpodctl pod list --all --name "$POD_NAME")"
test "$(printf '%s' "$EXISTING" | jq 'length')" -eq 0 || { RESULT="DUPLICATE_POD_GUARD"; exit 36; }

GPU_JSON="$(runpodctl gpu list --include-unavailable)"
GPU_ROW="$(printf '%s' "$GPU_JSON" | jq -c --arg id "$GPU_ID" '.[] | select(.gpuId == $id)' | head -n1)"
test -n "$GPU_ROW" || { RESULT="GPU_CATALOG_MISSING"; exit 37; }
ACTUAL_RATE="$(printf '%s' "$GPU_ROW" | jq -r '.securePricePerHr // empty')"
test -n "$ACTUAL_RATE" || { RESULT="SECURE_RATE_MISSING"; exit 38; }
awk -v p="$ACTUAL_RATE" -v m="$MAX_RATE" 'BEGIN { exit !(p <= m) }' || { RESULT="RATE_ABOVE_CEILING"; exit 39; }
AVAILABLE="$(printf '%s' "$GPU_ROW" | jq -r 'if has("available") and .available == true then "true" elif ([.dataCenterAvailability[]? | select(((.stockStatus // "") | ascii_downcase) != "none")] | length) > 0 then "true" else "false" end')"
test "$AVAILABLE" = "true" || { RESULT="NO_4090_STOCK"; exit 40; }

docker manifest inspect "$IMAGE" >/dev/null 2>&1 || { RESULT="IMAGE_NOT_PULLABLE"; exit 41; }

ssh-keygen -q -t ed25519 -f "$KEY" -N ''
SSH_FP="$(ssh-keygen -lf "$KEY.pub" -E sha256 | awk '{print $2}')"
echo "::add-mask::$SSH_FP"
runpodctl ssh add-key --key-file "$KEY.pub" >/dev/null || { RESULT="SSH_KEY_ADD_FAILED"; exit 42; }

git show "$EXPECTED_W03_HEAD:$LAUNCH_PATH" > "$RUNNER_TEMP/p4_runpod_appliance_launch.sh"
chmod +x "$RUNNER_TEMP/p4_runpod_appliance_launch.sh"

CREATE_ERR="$RUNNER_TEMP/runpod-create.err"
set +e
CREATE_OUT="$(runpodctl pod create   --name "$POD_NAME"   --image "$IMAGE"   --gpu-id "$GPU_ID"   --gpu-count 1   --cloud-type SECURE   --container-disk-in-gb 40   --ports "22/tcp"   --ssh   --min-cuda-version 12.8   --docker-args "sleep infinity"   --wait   --wait-timeout 4m   2>"$CREATE_ERR")"
CREATE_RC=$?
set -e

if [ "$CREATE_RC" -ne 0 ]; then
  POD_ID="$(python3 - "$CREATE_ERR" <<'PY'
import json,sys
found=""
for line in open(sys.argv[1],errors="ignore"):
    try:
        o=json.loads(line)
        if o.get("id"): found=o["id"]
    except Exception:
        pass
print(found)
PY
)"
  if [ -n "$POD_ID" ]; then echo "::add-mask::$POD_ID"; fi
  RESULT="POD_CREATE_OR_WAIT_FAILED"
  exit 43
fi

POD_ID="$(printf '%s' "$CREATE_OUT" | jq -r '.id // empty')"
test -n "$POD_ID" || { RESULT="POD_ID_MISSING"; exit 44; }
echo "::add-mask::$POD_ID"\n\nPOD_JSON="$(runpodctl pod get "$POD_ID")"
POST_RATE="$(printf '%s' "$POD_JSON" | jq -r '.costPerHr // .costPerHrGpu // empty')"
if [ -n "$POST_RATE" ] && [ "$POST_RATE" != "null" ]; then
  awk -v p="$POST_RATE" -v m="$MAX_RATE" 'BEGIN { exit !(p <= m) }' || { RESULT="POST_CREATE_RATE_ABOVE_CEILING"; exit 45; }
  ACTUAL_RATE="$POST_RATE"
fi

SSH_INFO="$(runpodctl ssh info "$POD_ID")"
IP="$(printf '%s' "$SSH_INFO" | jq -r '.ip // empty')"
PORT="$(printf '%s' "$SSH_INFO" | jq -r '.port // empty')"
test -n "$IP" -a -n "$PORT" || { RESULT="SSH_INFO_MISSING"; exit 46; }
echo "::add-mask::$IP"
echo "::add-mask::$PORT"

SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -p "$PORT" "root@$IP")
SCP=(scp -q -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -P "$PORT")

CONNECTED=false
for _ in $(seq 1 12); do
  if "${SSH[@]}" 'echo SSH_READY' >/dev/null 2>&1; then CONNECTED=true; break; fi
  sleep 5
done
test "$CONNECTED" = "true" || { RESULT="SSH_AUTH_FAILED"; exit 47; }

"${SCP[@]}" "$RUNNER_TEMP/p4_runpod_appliance_launch.sh" "root@$IP:/tmp/p4_runpod_appliance_launch.sh"

REMOTE="$RUNNER_TEMP/retry18f-remote.sh"
cat > "$REMOTE" <<REMOTE_EOF
#!/usr/bin/env bash
set -uo pipefail
export AQLEVON_EXPECTED_W03_HEAD="$EXPECTED_W03_HEAD"
chmod +x /tmp/p4_runpod_appliance_launch.sh
set +e
timeout --signal=TERM --kill-after=20s "__REMOTE_BUDGET__"s bash /tmp/p4_runpod_appliance_launch.sh 2>&1 | tee /workspace/retry18f-console.log
RC=\${PIPESTATUS[0]}
set -e
printf '%s\n' "\$RC" > /workspace/retry18f-exit-code
cd /workspace
ITEMS=(retry18f-exit-code retry18f-console.log)
if [ -d aqlevon_p4 ]; then ITEMS+=(aqlevon_p4); fi
tar -czf retry18f-export.tar.gz "\${ITEMS[@]}"
BYTES=\$(stat -c%s retry18f-export.tar.gz)
if [ "\$BYTES" -gt "$MAX_EGRESS" ]; then
  echo "EGRESS_LIMIT_EXCEEDED" > retry18f-export-status
  exit 90
fi
sha256sum retry18f-export.tar.gz > retry18f-export.tar.gz.sha256
echo "EXPORT_READY"
exit 0
REMOTE_EOF

ELAPSED="$(( $(date +%s) - POD_BIRTH ))"
REMOTE_BUDGET="$(( HARD_SECONDS - ELAPSED - ARTIFACT_MARGIN ))"
test "$REMOTE_BUDGET" -ge 300 || { RESULT="INSUFFICIENT_AUTH_TIME_AFTER_STARTUP"; exit 48; }
sed -i "s/__REMOTE_BUDGET__/$REMOTE_BUDGET/g" "$REMOTE"
"${SCP[@]}" "$REMOTE" "root@$IP:/tmp/retry18f-remote.sh"

set +e
timeout --signal=TERM --kill-after=20s "$((REMOTE_BUDGET+30))"s "${SSH[@]}" 'bash /tmp/retry18f-remote.sh'
REMOTE_RC=$?
set -e
if [ "$REMOTE_RC" -ne 0 ]; then
  RESULT="REMOTE_CONTROL_FAILED"
  exit 49
fi

"${SCP[@]}" "root@$IP:/workspace/retry18f-export.tar.gz" "$OUTDIR/retry18f-export.tar.gz"
"${SCP[@]}" "root@$IP:/workspace/retry18f-export.tar.gz.sha256" "$OUTDIR/retry18f-export.tar.gz.sha256"

(
  cd "$OUTDIR"
  sha256sum -c retry18f-export.tar.gz.sha256
)
ARTIFACT_RECEIVED=true

mkdir -p "$OUTDIR/unpacked"
tar -xzf "$OUTDIR/retry18f-export.tar.gz" -C "$OUTDIR/unpacked"
TRAIN_RC="$(cat "$OUTDIR/unpacked/retry18f-exit-code")"
if [ "$TRAIN_RC" = "0" ]; then
  RESULT="SUCCESS"
  write_receipt
  exit 0
else
  RESULT="TRAINING_FAILED_RC_$TRAIN_RC"
  write_receipt
  exit 50
fi
