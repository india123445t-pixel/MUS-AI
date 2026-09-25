FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

LABEL org.opencontainers.image.source="https://github.com/india123445t-pixel/MUS-AI"
LABEL org.opencontainers.image.description="Frozen AQLEVON Auth16 serverless inference worker"

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/models/hf-cache \
    TOKENIZERS_PARALLELISM=false \
    PYTHONUNBUFFERED=1 \
    AQLEVON_BASE_DIR=/models/qwen35-4b \
    AQLEVON_ADAPTER_DIR=/models/auth16 \
    AQLEVON_MODEL_NAME=AQLEVON-4B-Auth16

RUN python3 -m pip install --no-cache-dir \
    transformers==5.17.0 \
    peft==0.21.0 \
    accelerate==1.15.0 \
    huggingface_hub==1.5.0 \
    safetensors==0.6.2 \
    runpod==1.12.0

RUN mkdir -p /models/qwen35-4b /models/auth16 /app && \
    python3 - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.5-4B-Base",
    revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
    local_dir="/models/qwen35-4b",
)
PY

COPY adapter/adapter_config.json /models/auth16/adapter_config.json
COPY adapter/adapter_model.safetensors /models/auth16/adapter_model.safetensors
COPY handler.py /app/handler.py

RUN echo "2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a  /models/auth16/adapter_model.safetensors" | sha256sum -c -

WORKDIR /app
CMD ["python3","handler.py"]
