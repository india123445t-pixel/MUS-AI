#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

bash -n .github/runpod-control/run-aqlevon-27b-r0-budget8.sh
bash -n .github/runpod-control/finalize-aqlevon-27b-preservation.sh
python3 -m py_compile .github/runpod-control/verify-aqlevon-27b-evidence.py

python3 - <<'PY'
from pathlib import Path
wf=Path(".github/workflows/runpod-control-v1.yml").read_text()
run=Path(".github/runpod-control/run-aqlevon-27b-r0-budget8.sh").read_text()
fin=Path(".github/runpod-control/finalize-aqlevon-27b-preservation.sh").read_text()
assert "id: preserve_27b" in wf
assert "if-no-files-found: error" in wf
assert wf.index("uses: actions/upload-artifact@v4") < wf.index("Finalize AQLEVON 27B preservation and pod deletion")
assert " -X DELETE " not in run
assert "verify-aqlevon-27b-evidence.py" in run
assert "AQLEVON_PRESERVE_OUTCOME" in fin
assert "DURABLE_UPLOAD_FAILED_POD_STOPPED_NOT_DELETED" in fin
assert " -X DELETE " in fin
print("AQLEVON_27B_ARTIFACT_ORDER_STATIC_PASS")
PY

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/candidate/adapter"
printf 'aqlevon-test-adapter-bytes' >"$tmp/candidate/adapter/adapter_model.safetensors"
printf '{"r":4}\n' >"$tmp/candidate/adapter/adapter_config.json"
sha="$(sha256sum "$tmp/candidate/adapter/adapter_model.safetensors" | awk '{print $1}')"
SHA="$sha" python3 - "$tmp" <<'PY'
import json,os,sys
from pathlib import Path
root=Path(sys.argv[1])
sha=os.environ["SHA"]
base={"adapter_sha256":sha,"base_repo":"Qwen/Qwen3.8-27B","base_revision":"test-revision"}
(root/"candidate/candidate_manifest.json").write_text(json.dumps({**base,"manifest_sha256":"test-manifest"})+"\n")
(root/"candidate/training_receipt.json").write_text(json.dumps({**base,"reload_hash_match":True})+"\n")
PY
tar -C "$tmp" -czf "$tmp/evidence.tgz" candidate
python3 .github/runpod-control/verify-aqlevon-27b-evidence.py \
  --archive "$tmp/evidence.tgz" --expected-adapter-sha256 "$sha" \
  --output "$tmp/verified.json"
python3 - "$tmp/verified.json" "$sha" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["verified"] is True
assert x["adapter_sha256"]==sys.argv[2]
PY

printf 'tamper' >>"$tmp/candidate/adapter/adapter_model.safetensors"
tar -C "$tmp" -czf "$tmp/tampered.tgz" candidate
if python3 .github/runpod-control/verify-aqlevon-27b-evidence.py --archive "$tmp/tampered.tgz" >/dev/null 2>&1; then
  echo "tampered adapter unexpectedly verified" >&2
  exit 1
fi

echo AQLEVON_27B_ARTIFACT_DURABILITY_FREE_TEST_PASS
