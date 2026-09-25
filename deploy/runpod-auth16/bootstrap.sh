#!/usr/bin/env bash
set -euo pipefail
export PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1
ROOT=/opt/aqlevon
BASE="$ROOT/base"
ADAPTER="$ROOT/adapter"
mkdir -p "$BASE" "$ADAPTER"
python -m pip install --no-cache-dir --upgrade pip >/dev/null
python -m pip install --no-cache-dir "transformers==5.17.0" "peft==0.21.0" "accelerate==1.15.0" "huggingface_hub>=0.36" "runpod>=1.7,<2" >/dev/null
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
  repo_id="Qwen/Qwen3.5-4B-Base",
  revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
  local_dir="/opt/aqlevon/base"
)
PY
curl -fsSL "https://github.com/india123445t-pixel/MUS-AI/releases/download/aqlevon-auth16-runtime-v1/AQLEVON_AUTH16_ADAPTER.tar.gz" -o /tmp/adapter.tgz
tar -xzf /tmp/adapter.tgz -C "$ADAPTER"
echo "2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a  $ADAPTER/adapter_model.safetensors" | sha256sum -c -
curl -fsSL "https://raw.githubusercontent.com/india123445t-pixel/MUS-AI/release/aqlevon-unified-production-20260925/deploy/runpod-auth16/handler.py" -o "$ROOT/handler.py"
exec python -u "$ROOT/handler.py"
