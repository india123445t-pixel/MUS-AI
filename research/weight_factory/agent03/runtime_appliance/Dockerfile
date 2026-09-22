FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ARG SDPO_COMMIT=7c457fc1b1f636ae794eb0362ba37d4743b06fbc
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    AQLEVON_RUNTIME_ROOT=/opt/aqlevon/runtime \
    AQLEVON_SDPO=/opt/aqlevon/runtime/SDPO

WORKDIR /opt/aqlevon/runtime

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*

COPY research/weight_factory/agent03/runtime_appliance/requirements-p4-a1.txt /tmp/requirements-p4-a1.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-p4-a1.txt

RUN git clone -q https://github.com/lasgroup/SDPO.git "$AQLEVON_SDPO" \
 && git -C "$AQLEVON_SDPO" checkout -q "$SDPO_COMMIT" \
 && python -m pip install --no-cache-dir --no-deps -e "$AQLEVON_SDPO"

COPY research/weight_factory/agent03/p4_patch_sdpo_transformers5_compat.py /opt/aqlevon/runtime/p4_patch_sdpo_transformers5_compat.py
RUN mkdir -p /workspace \
 && ln -s "$AQLEVON_SDPO" /workspace/SDPO \
 && cd /opt/aqlevon/runtime \
 && python p4_patch_sdpo_transformers5_compat.py \
 && rm /workspace/SDPO

RUN python - <<'PY'
import hashlib
from pathlib import Path
expected={
 "/opt/aqlevon/runtime/SDPO/verl/utils/model.py":"135f61865fcbe057d29da90bf07968b04dd778e2e96a31d3ad640a8650155f8d",
 "/opt/aqlevon/runtime/SDPO/verl/workers/fsdp_workers.py":"e0ec49a1b891daed8f180a35f5d1d7e5147a3a8289c3787fc7688892e0e55fed",
}
for p,w in expected.items():
    g=hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert g==w,(p,g,w)
print("SDPO_PATCH_SHA_PASS")
PY

RUN python - <<'PY'
import sys, torch
assert sys.version_info[:2] == (3, 12), sys.version
assert torch.__version__.split("+")[0] == "2.8.0", torch.__version__
assert torch.version.cuda and torch.version.cuda.startswith("12.8"), torch.version.cuda
print("TORCH_RUNTIME_IDENTITY_PASS",torch.__version__,torch.version.cuda)
PY

RUN set -eux; \
    ABI="$(python -c "import torch; print('TRUE' if torch._C._GLIBCXX_USE_CXX11_ABI else 'FALSE')")"; \
    if [ "$ABI" = "TRUE" ]; then SHA="f25da18657a87fc83dc1bfb8b7751b82246e9db355510226b674fd437c34b5fb"; else SHA="2605b2653e7b9d6615bbb154896ae4d3f0b95d3120af7a6374ee97092e61df02"; fi; \
    WHEEL="/tmp/flash_attn-2.8.3+cu12torch2.8cxx11abi${ABI}-cp312-cp312-linux_x86_64.whl"; \
    URL="https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3%2Bcu12torch2.8cxx11abi${ABI}-cp312-cp312-linux_x86_64.whl"; \
    curl -fL --retry 3 --retry-delay 2 -o "$WHEEL" "$URL"; \
    echo "$SHA  $WHEEL" | sha256sum -c -; \
    python -m pip install --no-cache-dir --no-deps "$WHEEL"; \
    rm -f "$WHEEL"

COPY research/weight_factory/agent03/runtime_appliance/smoke_runtime.py /opt/aqlevon/runtime/smoke_runtime.py
RUN python /opt/aqlevon/runtime/smoke_runtime.py --build-check

LABEL org.opencontainers.image.title="AQLEVON P4 A1 Runtime Appliance" \
      org.opencontainers.image.description="Pinned pre-GPU runtime for Worker03 surrogate training" \
      aqlevon.sdpo.commit="7c457fc1b1f636ae794eb0362ba37d4743b06fbc" \
      aqlevon.torch="2.8.0" \
      aqlevon.cuda="12.8" \
      aqlevon.flash_attn="2.8.3"

