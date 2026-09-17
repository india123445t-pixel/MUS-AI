"""CPU-only preparation of the frozen MUS model artifact on Modal.

This script intentionally does not request a GPU and does not require the runtime
secret. It downloads the exact pinned Hugging Face revision into a persistent
Modal Volume and writes a SHA-256 integrity manifest for the downloaded files.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import modal

MODEL_ID = "Qwen/Qwen3.8-27B-FP8"
MODEL_REVISION = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
MODEL_VOLUME_NAME = "mus-model-store"
MODEL_MOUNT = pathlib.Path("/models")
MODEL_DIR = MODEL_MOUNT / "Qwen3.8-27B-FP8" / MODEL_REVISION

app = modal.App("mus-sovereign-model-prepare")
model_volume = modal.Volume.from_name(MODEL_VOLUME_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("huggingface_hub[hf_xet]>=0.35.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.function(
    image=image,
    volumes={str(MODEL_MOUNT): model_volume},
    cpu=2,
    memory=4096,
    timeout=60 * 60,
)
def prepare_model() -> dict:
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
        rel_path = path.relative_to(MODEL_DIR)
        # Hugging Face may create local download bookkeeping under .cache.
        # It is not part of the frozen runtime artifact inventory.
        if ".cache" in rel_path.parts or rel_path.name == "MUS_RUNTIME_MANIFEST.json":
            continue

        size = path.stat().st_size
        total_bytes += size
        inventory.append(
            {
                "file": rel_path.as_posix(),
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


@app.local_entrypoint()
def main() -> None:
    result = prepare_model.remote()
    print(json.dumps(result, ensure_ascii=False, indent=2))
