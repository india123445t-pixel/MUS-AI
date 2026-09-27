#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

bash -n .github/runpod-control/run-aqlevon-27b-r0-budget8.sh
bash -n .github/runpod-control/finalize-aqlevon-27b-preservation.sh
bash -n .github/runpod-control/aqlevon-27b-r0-bootstrap.sh
python3 -m py_compile \
  .github/runpod-control/verify-aqlevon-27b-evidence.py \
  .github/runpod-control/aqlevon-27b-reservation.py

python3 - <<'PY'
from pathlib import Path
wf=Path(".github/workflows/runpod-control-v1.yml").read_text()
run=Path(".github/runpod-control/run-aqlevon-27b-r0-budget8.sh").read_text()
fin=Path(".github/runpod-control/finalize-aqlevon-27b-preservation.sh").read_text()
boot=Path(".github/runpod-control/aqlevon-27b-r0-bootstrap.sh").read_text()
ver=Path(".github/runpod-control/verify-aqlevon-27b-evidence.py").read_text()

assert "group: aqlevon-runpod-control-v1-paid-single-flight" in wf
assert "cancel-in-progress: false" in wf
assert "execute_27b:\n    needs: status" in wf
assert "id: preserve_27b" in wf
assert "if-no-files-found: error" in wf
assert wf.index("uses: actions/upload-artifact@v4") < wf.index("Finalize AQLEVON 27B preservation and pod deletion")
assert " -X DELETE " not in run
assert "aqlevon-27b-reservation.py reserve" in run
assert "AQLEVON_27B_PRECREATE_RESERVATION_PUSH_CONFLICT" in run
assert "git push origin HEAD:ops/runpod-control-v1" in run
assert run.index("aqlevon-27b-reservation.py verify") < run.index("runpodctl pod create")
assert "DURABLE_UPLOAD_FAILED_POD_STOPPED_NOT_DELETED" in fin
assert "RUNTIME_VERSION_RECEIPT_INVALID_POD_STOPPED_NOT_DELETED" in fin
assert " -X DELETE " in fin
assert "runtime_versions.json" in boot
assert '"runtime_versions"' in run
assert "runtime_versions_sha256" in fin
assert "runtime_versions.json" in ver
print("AQLEVON_27B_CONTROL_ORDER_STATIC_PASS")
PY

# Scientific recipe is frozen: exact trainer blob must remain untouched.
trainer_blob="$(git rev-parse HEAD:research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py)"
test "$trainer_blob" = "9085e692d43110600e7bf214ffdab910f4821f1c"
echo AQLEVON_27B_SCIENTIFIC_CONSTANTS_UNCHANGED_PASS

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Evidence verifier: adapter integrity + mandatory structured runtime versions.
mkdir -p "$tmp/evidence/candidate/adapter"
printf 'aqlevon-test-adapter-bytes' >"$tmp/evidence/candidate/adapter/adapter_model.safetensors"
printf '{"r":4}\n' >"$tmp/evidence/candidate/adapter/adapter_config.json"
printf 'torch 2.8.0\ntransformers 5.17.0\npeft 0.21.0\naccelerate 1.15.0\n' >"$tmp/evidence/versions.txt"
cat >"$tmp/evidence/runtime_versions.json" <<'JSON'
{
  "kind": "AQLEVON_27B_RUNTIME_VERSIONS_V1",
  "packages": {
    "accelerate": "1.15.0",
    "huggingface-hub": "0.test",
    "peft": "0.21.0",
    "safetensors": "0.test",
    "torch": "2.8.0",
    "transformers": "5.17.0"
  },
  "python": "3.12.0",
  "torch_cuda": "12.8"
}
JSON
sha="$(sha256sum "$tmp/evidence/candidate/adapter/adapter_model.safetensors" | awk '{print $1}')"
SHA="$sha" python3 - "$tmp/evidence" <<'PY'
import json,os,sys
from pathlib import Path
root=Path(sys.argv[1])
sha=os.environ["SHA"]
base={"adapter_sha256":sha,"base_repo":"Qwen/Qwen3.8-27B","base_revision":"test-revision"}
(root/"candidate/candidate_manifest.json").write_text(json.dumps({**base,"manifest_sha256":"test-manifest"})+"\n")
(root/"candidate/training_receipt.json").write_text(json.dumps({**base,"reload_hash_match":True})+"\n")
PY
tar -C "$tmp/evidence" -czf "$tmp/evidence.tgz" candidate versions.txt runtime_versions.json
python3 .github/runpod-control/verify-aqlevon-27b-evidence.py \
  --archive "$tmp/evidence.tgz" --expected-adapter-sha256 "$sha" \
  --output "$tmp/verified.json"
python3 - "$tmp/verified.json" "$sha" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["verified"] is True
assert x["adapter_sha256"]==sys.argv[2]
assert x["runtime_versions"]["packages"]["torch"]=="2.8.0"
assert len(x["runtime_versions_sha256"])==64
PY

tar -C "$tmp/evidence" -czf "$tmp/no-runtime.tgz" candidate versions.txt
if python3 .github/runpod-control/verify-aqlevon-27b-evidence.py --archive "$tmp/no-runtime.tgz" >/dev/null 2>&1; then
  echo "missing runtime version receipt unexpectedly verified" >&2
  exit 1
fi
printf 'tamper' >>"$tmp/evidence/candidate/adapter/adapter_model.safetensors"
tar -C "$tmp/evidence" -czf "$tmp/tampered.tgz" candidate versions.txt runtime_versions.json
if python3 .github/runpod-control/verify-aqlevon-27b-evidence.py --archive "$tmp/tampered.tgz" >/dev/null 2>&1; then
  echo "tampered adapter unexpectedly verified" >&2
  exit 1
fi
echo AQLEVON_27B_RUNTIME_VERSION_RECEIPT_REQUIRED_PASS

# Reservation helper: missing/invalid claims fail closed.
cat >"$tmp/auth.json" <<'JSON'
{
  "authorization_id": "TEST-FRESH-AUTH",
  "single_use": true,
  "training_authorized": true,
  "automatic_cleanup_required": true,
  "artifact_preservation_required": true,
  "no_main_merge": true,
  "sealed_eval_forbidden": true
}
JSON
SRC="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
python3 .github/runpod-control/aqlevon-27b-reservation.py reserve \
  --authorization "$tmp/auth.json" --reservation "$tmp/reservation.json" --consumed "$tmp/consumed.json" \
  --run-id 101 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH
python3 .github/runpod-control/aqlevon-27b-reservation.py verify \
  --authorization "$tmp/auth.json" --reservation "$tmp/reservation.json" --consumed "$tmp/consumed.json" \
  --run-id 101 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH --require-precreate
if python3 .github/runpod-control/aqlevon-27b-reservation.py reserve \
  --authorization "$tmp/auth.json" --reservation "$tmp/reservation.json" --consumed "$tmp/consumed.json" \
  --run-id 102 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH >/dev/null 2>&1; then
  echo "second local reservation unexpectedly passed" >&2
  exit 1
fi
if python3 .github/runpod-control/aqlevon-27b-reservation.py verify \
  --authorization "$tmp/auth.json" --reservation "$tmp/missing.json" --consumed "$tmp/consumed.json" \
  --run-id 101 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH >/dev/null 2>&1; then
  echo "missing reservation unexpectedly verified" >&2
  exit 1
fi
cp "$tmp/reservation.json" "$tmp/invalid-reservation.json"
python3 - "$tmp/invalid-reservation.json" <<'PY'
import json,sys
p=sys.argv[1]; x=json.load(open(p)); x["run_id"]="999"; open(p,"w").write(json.dumps(x)+"\n")
PY
if python3 .github/runpod-control/aqlevon-27b-reservation.py verify \
  --authorization "$tmp/auth.json" --reservation "$tmp/invalid-reservation.json" --consumed "$tmp/consumed.json" \
  --run-id 101 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH >/dev/null 2>&1; then
  echo "invalid reservation unexpectedly verified" >&2
  exit 1
fi
echo AQLEVON_27B_MISSING_INVALID_RESERVATION_BLOCK_PASS

# Two stale logical starts cannot both durably publish the authorization claim:
# ordinary non-force Git push is the cross-run compare-and-swap.
git init --bare "$tmp/origin.git" >/dev/null
git clone "$tmp/origin.git" "$tmp/seed" >/dev/null 2>&1
(
  cd "$tmp/seed"
  git config user.name test
  git config user.email test@example.invalid
  cp "$tmp/auth.json" auth.json
  git add auth.json
  git commit -m seed >/dev/null
  git branch -M control
  git push origin control >/dev/null
)
git clone --branch control "$tmp/origin.git" "$tmp/r1" >/dev/null 2>&1
git clone --branch control "$tmp/origin.git" "$tmp/r2" >/dev/null 2>&1
for runner in r1 r2; do
  git -C "$tmp/$runner" config user.name test
  git -C "$tmp/$runner" config user.email test@example.invalid
done
python3 .github/runpod-control/aqlevon-27b-reservation.py reserve \
  --authorization "$tmp/r1/auth.json" --reservation "$tmp/r1/reservation.json" --consumed "$tmp/r1/consumed.json" \
  --run-id 201 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH >/dev/null
python3 .github/runpod-control/aqlevon-27b-reservation.py reserve \
  --authorization "$tmp/r2/auth.json" --reservation "$tmp/r2/reservation.json" --consumed "$tmp/r2/consumed.json" \
  --run-id 202 --run-attempt 1 --source-sha "$SRC" --expected-authorization-id TEST-FRESH-AUTH >/dev/null
git -C "$tmp/r1" add reservation.json consumed.json
git -C "$tmp/r1" commit -m r1 >/dev/null
git -C "$tmp/r2" add reservation.json consumed.json
git -C "$tmp/r2" commit -m r2 >/dev/null
git -C "$tmp/r1" push origin HEAD:control >/dev/null
if git -C "$tmp/r2" push origin HEAD:control >/dev/null 2>&1; then
  echo "second concurrent durable reservation unexpectedly published" >&2
  exit 1
fi
git --git-dir="$tmp/origin.git" show control:reservation.json >"$tmp/winner.json"
python3 - "$tmp/winner.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["run_id"]=="201"
assert x["state"]=="RESERVED_BEFORE_PROVIDER_CREATE"
PY
echo AQLEVON_27B_SINGLE_FLIGHT_RESERVATION_CAS_PASS

# Artifact upload failure and invalid runtime receipt must never reach DELETE.
mkdir -p "$tmp/fakebin"
cat >"$tmp/fakebin/curl" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$AQ_CURL_LOG"
if [[ " $* " == *" -w "* ]]; then printf '404'; fi
exit 0
SH
chmod +x "$tmp/fakebin/curl"
printf 'fake-pod\n' >"$tmp/pod"
: >"$tmp/curl.log"
if PATH="$tmp/fakebin:$PATH" AQ_CURL_LOG="$tmp/curl.log" AQLEVON_POD_FILE="$tmp/pod" \
  AQLEVON_RESULT_PATH="$tmp/no-result.json" AQLEVON_VERIFY_MARKER_PATH="$tmp/missing-marker.json" \
  AQLEVON_PRESERVE_OUTCOME=failure \
  bash .github/runpod-control/finalize-aqlevon-27b-preservation.sh >/dev/null 2>&1; then
  echo "upload failure unexpectedly finalized" >&2
  exit 1
fi
if grep -q -- '-X DELETE' "$tmp/curl.log"; then
  echo "DELETE attempted after upload failure" >&2
  exit 1
fi
printf '{}\n' >"$tmp/invalid-marker.json"
: >"$tmp/curl.log"
if PATH="$tmp/fakebin:$PATH" AQ_CURL_LOG="$tmp/curl.log" AQLEVON_POD_FILE="$tmp/pod" \
  AQLEVON_RESULT_PATH="$tmp/no-result.json" AQLEVON_VERIFY_MARKER_PATH="$tmp/invalid-marker.json" \
  AQLEVON_PRESERVE_OUTCOME=success AQLEVON_ARTIFACT_ID=123 \
  AQLEVON_ARTIFACT_DIGEST=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  bash .github/runpod-control/finalize-aqlevon-27b-preservation.sh >/dev/null 2>&1; then
  echo "invalid runtime receipt unexpectedly finalized" >&2
  exit 1
fi
if grep -q -- '-X DELETE' "$tmp/curl.log"; then
  echo "DELETE attempted with invalid runtime receipt" >&2
  exit 1
fi
echo AQLEVON_27B_UPLOAD_FAILURE_NO_DELETE_PASS
echo AQLEVON_27B_ARTIFACT_DURABILITY_FREE_TEST_PASS
echo AQLEVON_27B_CONTROL_PLANE_FREE_TEST_PASS
