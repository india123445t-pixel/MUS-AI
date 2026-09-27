#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import time
from pathlib import Path
from typing import Any

EXPECTED_ADAPTER_SHA256 = "5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74"
EXPECTED_ADAPTER_STATE_SHA256 = "1e3ff8a0fbc88686a2d96f93d4f04fdd66db2034ffdfafc2cc91e532ed0bf80f"
EXPECTED_CANDIDATE_MANIFEST_SHA256 = "e020c6b140ffba104d1fe4485333fb225afd29c52dc03bf9a62d0f8c614e01c5"
EXPECTED_GENERALIZATION_MANIFEST_SHA256 = "25fa2777010255bd8d91431632ba65d72355340086250fe4bce8dffa64e33b0f"
EXPECTED_PAIRED_BINDING_SHA256 = "b5f26e20bcdd13cead301623cc5e3496e231b32418a98c895e31db5dfdf9a888"
BASE_REPO = "Qwen/Qwen3.8-27B"
BASE_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"


class EvalError(RuntimeError):
    pass


def canonical_bytes(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def write_status(path: Path | None, **fields: Any) -> None:
    if path is None:
        return
    payload = {"kind": "AQLEVON_AUTH08_UNIFIED_PUBLIC_EVAL_STATUS_V1", **fields, "updated_at": time.time()}
    tmp = path.with_suffix(".tmp")
    write_json(tmp, payload)
    os.replace(tmp, path)


def load_challenge_module(path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("aqlevon_gxc_auth08", path)
    if spec is None or spec.loader is None:
        raise EvalError("challenge_module_unloadable")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    adapter_file = args.adapter_dir / "adapter_model.safetensors"
    if not adapter_file.is_file():
        raise EvalError("adapter_file_missing")
    if sha256_file(adapter_file) != EXPECTED_ADAPTER_SHA256:
        raise EvalError("adapter_sha256_mismatch")

    candidate_manifest = load_json(args.candidate_manifest)
    if candidate_manifest.get("manifest_sha256") != EXPECTED_CANDIDATE_MANIFEST_SHA256:
        raise EvalError("candidate_manifest_sha256_mismatch")
    if candidate_manifest.get("adapter_sha256") != EXPECTED_ADAPTER_SHA256:
        raise EvalError("candidate_manifest_adapter_mismatch")
    if candidate_manifest.get("adapter_state_sha256") != EXPECTED_ADAPTER_STATE_SHA256:
        raise EvalError("candidate_manifest_state_mismatch")
    if candidate_manifest.get("base_repo") != BASE_REPO or candidate_manifest.get("base_revision") != BASE_REVISION:
        raise EvalError("candidate_manifest_base_mismatch")

    gen_manifest = load_json(args.generalization_manifest)
    if gen_manifest.get("manifest_sha256") != EXPECTED_GENERALIZATION_MANIFEST_SHA256:
        raise EvalError("generalization_manifest_sha256_mismatch")
    ci = gen_manifest.get("candidate_identity") or {}
    if ci.get("adapter_sha256") != EXPECTED_ADAPTER_SHA256:
        raise EvalError("generalization_adapter_binding_mismatch")
    if ci.get("adapter_state_sha256") != EXPECTED_ADAPTER_STATE_SHA256:
        raise EvalError("generalization_state_binding_mismatch")
    if ci.get("candidate_manifest_sha256") != EXPECTED_CANDIDATE_MANIFEST_SHA256:
        raise EvalError("generalization_candidate_manifest_binding_mismatch")

    gen_rows = load_json(args.generalization_skeleton)
    if not isinstance(gen_rows, list) or len(gen_rows) != 128:
        raise EvalError("generalization_row_count")

    paired_plan = load_json(args.paired_plan)
    if paired_plan.get("contract_sha256") != "484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d":
        raise EvalError("paired_contract_mismatch")
    paired_rows = paired_plan.get("rows")
    if not isinstance(paired_rows, list) or len(paired_rows) != 224:
        raise EvalError("paired_row_count")

    paired_binding = load_json(args.paired_binding)
    if paired_binding.get("binding_sha256") != EXPECTED_PAIRED_BINDING_SHA256:
        raise EvalError("paired_binding_sha256_mismatch")
    pb = paired_binding.get("candidate_identity") or {}
    if pb.get("adapter_sha256") != EXPECTED_ADAPTER_SHA256:
        raise EvalError("paired_adapter_binding_mismatch")
    if pb.get("adapter_state_sha256") != EXPECTED_ADAPTER_STATE_SHA256:
        raise EvalError("paired_state_binding_mismatch")
    if pb.get("candidate_manifest_sha256") != EXPECTED_CANDIDATE_MANIFEST_SHA256:
        raise EvalError("paired_candidate_manifest_binding_mismatch")

    return gen_manifest, gen_rows, paired_plan, paired_binding, candidate_manifest


def generation_kwargs(cfg: dict[str, Any], tokenizer: Any) -> dict[str, Any]:
    return {
        "do_sample": bool(cfg.get("do_sample", True)),
        "temperature": float(cfg["temperature"]),
        "top_p": float(cfg["top_p"]),
        "top_k": int(cfg["top_k"]),
        "max_new_tokens": int(cfg["max_new_tokens"]),
        "num_return_sequences": int(cfg.get("num_return_sequences", 1)),
        "use_cache": bool(cfg.get("use_cache", True)),
        "pad_token_id": tokenizer.eos_token_id,
    }


def generate_one(model: Any, tokenizer: Any, prompt: str, seed: int, cfg: dict[str, Any], torch: Any) -> str:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    chat = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    enc = tokenizer(chat, return_tensors="pt", add_special_tokens=False).to("cuda")
    with torch.inference_mode():
        out = model.generate(**enc, **generation_kwargs(cfg, tokenizer))[0]
    text = tokenizer.decode(out[enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    del enc, out
    return text


def eval_generalization(
    model: Any,
    tokenizer: Any,
    system: str,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    prompts: dict[str, str],
    torch: Any,
    status_path: Path | None,
    progress_base: int,
    progress_total: int,
) -> tuple[list[dict[str, Any]], int]:
    cfg = manifest["generation"]
    selected = [r for r in rows if r["system"] == system]
    if len(selected) != 64:
        raise EvalError(f"generalization_system_count:{system}")
    done = progress_base
    out_rows = []
    for idx, row in enumerate(selected, 1):
        task_id = row["task_id"]
        if task_id not in prompts:
            raise EvalError(f"generalization_prompt_missing:{task_id}")
        raw = generate_one(model, tokenizer, prompts[task_id], int(row["seed"]), cfg, torch)
        rr = dict(row)
        rr["raw_output"] = raw
        out_rows.append(rr)
        done += 1
        if idx == 1 or idx % 8 == 0 or idx == len(selected):
            write_status(status_path, stage="INFERENCE", section="generalization", system=system, completed=done, total=progress_total)
    return out_rows, done


def eval_paired(
    model: Any,
    tokenizer: Any,
    system: str,
    plan: dict[str, Any],
    torch: Any,
    status_path: Path | None,
    progress_base: int,
    progress_total: int,
) -> tuple[list[dict[str, Any]], int]:
    selected = [r for r in plan["rows"] if r["system"] == system]
    if len(selected) != 112:
        raise EvalError(f"paired_system_count:{system}")
    done = progress_base
    output_rows = []
    for idx, row in enumerate(selected, 1):
        raw = generate_one(model, tokenizer, row["prompt"], int(row["seed"]), row["generation"], torch)
        output_rows.append({
            "system": system,
            "split": row["split"],
            "task_id": row["task_id"],
            "seed": int(row["seed"]),
            "output": raw,
        })
        done += 1
        if idx == 1 or idx % 8 == 0 or idx == len(selected):
            write_status(status_path, stage="INFERENCE", section="paired_public", system=system, completed=done, total=progress_total)
    return output_rows, done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--adapter-dir", type=Path, required=True)
    ap.add_argument("--candidate-manifest", type=Path, required=True)
    ap.add_argument("--challenge-module", type=Path, required=True)
    ap.add_argument("--generalization-manifest", type=Path, required=True)
    ap.add_argument("--generalization-skeleton", type=Path, required=True)
    ap.add_argument("--paired-plan", type=Path, required=True)
    ap.add_argument("--paired-binding", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--status-path", type=Path)
    args = ap.parse_args()

    import torch
    import transformers
    import peft
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    from peft import PeftModel

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise EvalError("bf16_cuda_required")

    gen_manifest, gen_rows, paired_plan, paired_binding, candidate_manifest = validate_inputs(args)
    challenge = load_challenge_module(args.challenge_module)
    pack = challenge.build_pack()
    if pack.get("pack_sha256") != gen_manifest.get("challenge_pack_sha256"):
        raise EvalError("challenge_pack_hash_mismatch")
    prompts = {t["task_id"]: t["prompt"] for t in pack["tasks"]}
    if len(prompts) != 16:
        raise EvalError("challenge_task_count")

    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_status(args.status_path, stage="LOAD_BASE", completed=0, total=352)

    tokenizer = AutoTokenizer.from_pretrained(
        str(args.model_dir), local_files_only=True, trust_remote_code=False
    )
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir),
        dtype=torch.bfloat16,
        device_map={"": 0},
        low_cpu_mem_usage=True,
        local_files_only=True,
        trust_remote_code=False,
    )
    base.eval()

    t0 = time.time()
    gen_base, done = eval_generalization(
        base, tokenizer, "canonical_base", gen_manifest, gen_rows, prompts, torch, args.status_path, 0, 352
    )
    paired_base, done = eval_paired(
        base, tokenizer, "base", paired_plan, torch, args.status_path, done, 352
    )

    write_status(args.status_path, stage="LOAD_ADAPTER", completed=done, total=352)
    candidate = PeftModel.from_pretrained(base, str(args.adapter_dir), is_trainable=False)
    candidate.eval()

    gen_candidate, done = eval_generalization(
        candidate, tokenizer, "candidate_adapter_on_same_base", gen_manifest, gen_rows, prompts, torch, args.status_path, done, 352
    )
    paired_candidate, done = eval_paired(
        candidate, tokenizer, "candidate", paired_plan, torch, args.status_path, done, 352
    )
    if done != 352:
        raise EvalError(f"attempt_count:{done}")

    gen_out = gen_base + gen_candidate
    if len(gen_out) != 128:
        raise EvalError("generalization_final_count")
    paired_out = paired_base + paired_candidate
    if len(paired_out) != 224:
        raise EvalError("paired_final_count")

    write_json(args.output_dir / "generalization-results.json", gen_out)
    with (args.output_dir / "paired-public-results.jsonl").open("w", encoding="utf-8") as f:
        for row in paired_out:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    receipt = {
        "kind": "AQLEVON_AUTH08_UNIFIED_PUBLIC_EVAL_RUNTIME_RECEIPT_V1",
        "base_repo": BASE_REPO,
        "base_revision": BASE_REVISION,
        "adapter_sha256": EXPECTED_ADAPTER_SHA256,
        "adapter_state_sha256": EXPECTED_ADAPTER_STATE_SHA256,
        "candidate_manifest_sha256": EXPECTED_CANDIDATE_MANIFEST_SHA256,
        "generalization_manifest_sha256": EXPECTED_GENERALIZATION_MANIFEST_SHA256,
        "paired_binding_sha256": EXPECTED_PAIRED_BINDING_SHA256,
        "generalization_attempts": 128,
        "paired_public_attempts": 224,
        "total_model_dispatches": 352,
        "no_retry_after_dispatch": True,
        "elapsed_seconds": round(time.time() - t0, 3),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "gpu_name": torch.cuda.get_device_name(0),
        "sealed_eval_consumed": False,
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_bytes(receipt)).hexdigest()
    write_json(args.output_dir / "runtime-receipt.json", receipt)
    write_status(args.status_path, stage="DONE", completed=352, total=352, receipt_sha256=receipt["receipt_sha256"])
    print("AQLEVON_AUTH08_UNIFIED_PUBLIC_EVAL_DONE", json.dumps(receipt, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
