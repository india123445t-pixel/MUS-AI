"""MUS AI sovereign runtime on Modal.

Safety properties:
- Exact model + immutable revision are pinned.
- `modal run` performs CPU-only download/integrity preparation. It does not start a GPU.
- The GPU server scales from zero and is limited to one L40S replica.
- External inference providers are not used here.
- The HTTP endpoint requires a bearer API key supplied via the Modal secret
  `mus-model-runtime` (`MUS_MODEL_KEY`).
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

import modal

MODEL_ID = "Qwen/Qwen3.8-27B-FP8"
MODEL_REVISION = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
MODEL_VOLUME_NAME = "mus-model-store"
VLLM_CACHE_VOLUME_NAME = "mus-vllm-cache"
RUNTIME_SECRET_NAME = "mus-model-runtime"

MODEL_MOUNT = pathlib.Path("/models")
MODEL_DIR = MODEL_MOUNT / "Qwen3.8-27B-FP8" / MODEL_REVISION
VLLM_CACHE_MOUNT = pathlib.Path("/vllm-cache")
PORT = 8000

app = modal.App("mus-sovereign-runtime")

model_volume = modal.Volume.from_name(MODEL_VOLUME_NAME, create_if_missing=True)
vllm_cache_volume = modal.Volume.from_name(VLLM_CACHE_VOLUME_NAME, create_if_missing=True)

download_image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("huggingface_hub[hf_xet]>=0.35.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.0-devel-ubuntu22.04",
        add_python="3.12",
    )
    .entrypoint([])
    .uv_pip_install(
        "vllm==0.29.0",
        "huggingface_hub[hf_xet]>=0.35.0",
    )
    .env(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "VLLM_CACHE_ROOT": str(VLLM_CACHE_MOUNT),
        }
    )
)

runtime_secret = modal.Secret.from_name(
    RUNTIME_SECRET_NAME,
    required_keys=["MUS_MODEL_KEY"],
)


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.function(
    image=download_image,
    volumes={str(MODEL_MOUNT): model_volume},
    cpu=2,
    memory=4096,
    timeout=60 * 60,
)
def prepare_model() -> dict:
    """Download the immutable model revision on CPU and persist an integrity manifest."""
    from huggingface_hub import snapshot_download

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(MODEL_DIR),
    )

    inventory = []
    total_bytes = 0
    for path in sorted(p for p in MODEL_DIR.rglob("*") if p.is_file()):
        rel = path.relative_to(MODEL_DIR).as_posix()
        size = path.stat().st_size
        total_bytes += size
        inventory.append(
            {
                "file": rel,
                "size_bytes": size,
                "sha256": _sha256(path),
            }
        )

    manifest = {
        "repo": MODEL_ID,
        "revision": MODEL_REVISION,
        "server_path": str(MODEL_DIR),
        "total_files": len(inventory),
        "total_size_bytes": total_bytes,
        "files": inventory,
    }
    manifest_path = MODEL_DIR / "MUS_RUNTIME_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    model_volume.commit()
    return {
        "repo": MODEL_ID,
        "revision": MODEL_REVISION,
        "server_path": str(MODEL_DIR),
        "total_files": len(inventory),
        "total_size_bytes": total_bytes,
        "manifest": str(manifest_path),
    }


@app.server(
    image=vllm_image,
    gpu="L40S",
    min_containers=0,
    max_containers=1,
    target_concurrency=1,
    scaledown_window=30,
    startup_timeout=15 * 60,
    port=PORT,
    unauthenticated=True,  # vLLM itself enforces MUS_MODEL_KEY bearer auth.
    volumes={
        str(MODEL_MOUNT): model_volume.with_mount_options(read_only=True),
        str(VLLM_CACHE_MOUNT): vllm_cache_volume,
    },
    secrets=[runtime_secret],
)
class SovereignServer:
    """Authenticated OpenAI-compatible vLLM server for MUS self_hosted_only."""

    @modal.enter()
    def start(self) -> None:
        api_key = os.environ["MUS_MODEL_KEY"]
        manifest_path = MODEL_DIR / "MUS_RUNTIME_MANIFEST.json"
        if not manifest_path.exists():
            raise RuntimeError(
                "Pinned model is not prepared. Run `modal run infra/modal/sovereign_runtime.py` first."
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("repo") != MODEL_ID or manifest.get("revision") != MODEL_REVISION:
            raise RuntimeError("Model manifest does not match the frozen MUS artifact.")

        cmd = [
            "vllm",
            "serve",
            str(MODEL_DIR),
            "--served-model-name",
            MODEL_ID,
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
            "--api-key",
            api_key,
            "--max-model-len",
            "4096",
            "--gpu-memory-utilization",
            "0.90",
            "--tensor-parallel-size",
            "1",
            "--enforce-eager",
            "--uvicorn-log-level",
            "warning",
            "--disable-log-requests",
        ]
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self) -> None:
        if getattr(self, "process", None) is not None:
            self.process.terminate()


@app.local_entrypoint()
def main() -> None:
    """CPU-only preparation entrypoint. No GPU container is started."""
    result = prepare_model.remote()
    print(json.dumps(result, ensure_ascii=False, indent=2))
