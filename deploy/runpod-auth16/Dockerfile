FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
WORKDIR /opt/aqlevon
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir "transformers==5.17.0" "peft==0.21.0" "accelerate==1.15.0" "huggingface_hub>=0.36" "runpod>=1.7,<2"
RUN mkdir -p /opt/aqlevon/base /opt/aqlevon/adapter
RUN python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen3.5-4B-Base",revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",local_dir="/opt/aqlevon/base")
print("AQLEVON_PINNED_BASE_BAKED")
PY
RUN curl -fsSL "https://github.com/india123445t-pixel/MUS-AI/releases/download/aqlevon-auth16-runtime-v1/AQLEVON_AUTH16_ADAPTER.tar.gz" -o /tmp/adapter.tgz && \
    tar -xzf /tmp/adapter.tgz -C /opt/aqlevon/adapter && rm /tmp/adapter.tgz && \
    echo "2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a  /opt/aqlevon/adapter/adapter_model.safetensors" | sha256sum -c -
COPY deploy/runpod-auth16/handler.py /opt/aqlevon/handler.py
CMD ["python","-u","/opt/aqlevon/handler.py"]
