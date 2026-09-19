from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import math
import os
import platform
import random
import re
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple

import numpy as np

from .core import (
    B07Error,
    DeltaBundle,
    Geometry,
    LowRankModule,
    baseline_coefficients,
    build_geometry,
    canonical_json_bytes,
    direct_inner_with_mixture,
    load_json,
    oracle_span_projection_coeffs,
    read_jsonl,
    sha256_bytes,
    sha256_json,
    write_json,
    verify_dataset_manifest,
    dataset_manifest_family,
)


def _runtime_imports():
    try:
        import torch
        import transformers
        import peft
        import safetensors
        from peft import LoraConfig, get_peft_model
        from safetensors.torch import load_file as safe_load_torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:  # pragma: no cover - exercised only on GPU/runtime hosts
        raise B07Error(
            "B07-E0 GPU runtime dependencies are missing. Install a CUDA-compatible torch and requirements-b07e0.txt."
        ) from exc
    return {
        "torch": torch,
        "transformers": transformers,
        "peft": peft,
        "safetensors": safetensors,
        "LoraConfig": LoraConfig,
        "get_peft_model": get_peft_model,
        "safe_load_torch": safe_load_torch,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _adapter_identity(adapter_dir: Path) -> str:
    files = [adapter_dir / "adapter_config.json", adapter_dir / "adapter_model.safetensors"]
    for p in files:
        if not p.exists():
            raise B07Error(f"missing adapter artifact: {p}")
    payload = {
        "adapter_config_sha256": _sha256_file(files[0]),
        "adapter_model_sha256": _sha256_file(files[1]),
    }
    return sha256_json(payload)


def _factor_key(key: str) -> Tuple[str, str] | None:
    match = re.match(r"^(.*)\.lora_(A|B)(?:\.[^.]+)?\.weight$", key)
    if not match:
        return None
    name = match.group(1)
    # PEFT adapter files use base_model.model.<actual module path>.
    prefix = "base_model.model."
    if name.startswith(prefix):
        name = name[len(prefix):]
    return name, match.group(2)


def load_delta_bundle(adapter_dir: os.PathLike[str] | str, config: Mapping[str, object], family_id: str) -> DeltaBundle:
    deps = _runtime_imports()
    safe_load_torch = deps["safe_load_torch"]
    adapter_dir = Path(adapter_dir)
    adapter_cfg = load_json(adapter_dir / "adapter_config.json")
    if bool(adapter_cfg.get("use_rslora", False)):
        raise B07Error("B07-E0 v1 canonical geometry rejects rsLoRA; use plain LoRA only")
    if adapter_cfg.get("rank_pattern") or adapter_cfg.get("alpha_pattern"):
        raise B07Error("B07-E0 v1 rejects per-module rank/alpha patterns")
    expected_lora = config["lora"]  # type: ignore[index]
    rank = int(adapter_cfg.get("r", expected_lora["rank"]))
    alpha = float(adapter_cfg.get("lora_alpha", expected_lora["alpha"]))
    if rank <= 0:
        raise B07Error("invalid LoRA rank")
    if rank != int(expected_lora["rank"]) or alpha != float(expected_lora["alpha"]):
        raise B07Error("adapter LoRA rank/alpha differs from frozen B07-E0 budget")
    targets = adapter_cfg.get("target_modules") or []
    if set(str(x) for x in targets) != set(str(x) for x in expected_lora["target_modules"]):
        raise B07Error("adapter target_modules differ from frozen B07-E0 topology")
    scale = alpha / rank
    tensors = safe_load_torch(str(adapter_dir / "adapter_model.safetensors"), device="cpu")
    grouped: Dict[str, Dict[str, np.ndarray]] = {}
    for key, value in tensors.items():
        parsed = _factor_key(key)
        if parsed is None:
            continue
        name, kind = parsed
        grouped.setdefault(name, {})[kind] = value.detach().float().cpu().numpy().astype(np.float64, copy=False)
    if not grouped:
        raise B07Error("adapter contains no LoRA A/B tensors")
    modules: Dict[str, LowRankModule] = {}
    for name in sorted(grouped):
        pair = grouped[name]
        if set(pair) != {"A", "B"}:
            raise B07Error(f"incomplete LoRA factor pair: {name}")
        a = pair["A"]
        b = pair["B"]
        if a.shape[0] != rank or b.shape[1] != rank:
            raise B07Error(f"LoRA rank mismatch for {name}")
        modules[name] = LowRankModule(name=name, a=a, b=b, scale=scale)
    base = config["base_model"]  # type: ignore[index]
    adapter_sha = _adapter_identity(adapter_dir)
    receipt_path = adapter_dir / "b07_train_receipt.json"
    if not receipt_path.exists():
        raise B07Error(f"missing B07 training receipt: {family_id}")
    receipt = load_json(receipt_path)
    stated_receipt_sha = str(receipt.get("receipt_sha256", ""))
    unsigned_receipt = dict(receipt)
    unsigned_receipt.pop("receipt_sha256", None)
    if stated_receipt_sha != sha256_json(unsigned_receipt):
        raise B07Error("adapter training receipt self-hash mismatch")
    if str(receipt.get("family_id")) != family_id:
        raise B07Error("adapter receipt family identity mismatch")
    if receipt.get("base_model") != base:
        raise B07Error("adapter receipt base model/revision mismatch")
    if str(receipt.get("adapter_sha256")) != adapter_sha:
        raise B07Error("adapter receipt hash does not bind current adapter bytes")
    manifest_path = adapter_dir.parent.parent / "dataset_manifest.json"
    if not manifest_path.exists():
        raise B07Error("dataset manifest missing beside adapter bank")
    manifest = load_json(manifest_path)
    verify_dataset_manifest(config, manifest)
    manifest_entry = dataset_manifest_family(manifest, family_id)
    if str(receipt.get("dataset_manifest_sha256")) != str(manifest.get("manifest_sha256")):
        raise B07Error("adapter receipt dataset-manifest identity mismatch")
    if str(receipt.get("train_sha256")) != str(manifest_entry.get("train_sha256")):
        raise B07Error("adapter receipt training-shard identity mismatch")
    return DeltaBundle(
        family_id=family_id,
        base_model_repo=str(base["repo_id"]),
        base_model_revision=str(base["revision"]),
        modules=modules,
        adapter_sha256=adapter_sha,
    )


def _select_dtype(torch, device: str):
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise B07Error("CUDA requested but unavailable")
        index = 0
        if ":" in device:
            index = int(device.split(":", 1)[1])
        with torch.cuda.device(index):
            bf16_ok = bool(torch.cuda.is_bf16_supported())
        if bf16_ok:
            return torch.bfloat16, "bfloat16"
        return torch.float16, "float16"
    return torch.float32, "float32"


def _seed_everything(torch, seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    try:
        torch.use_deterministic_algorithms(True)
    except Exception:
        # Some kernels/models may not support strict determinism. The receipt records this;
        # a hard runtime failure is preferable to silently changing algorithm in the harness.
        pass


def _tokenize_supervised(tokenizer, rows: Sequence[Mapping[str, object]], max_length: int):
    examples = []
    eos = tokenizer.eos_token or ""
    for row in rows:
        prompt = str(row["prompt"])
        answer = str(int(row["target"])) + eos
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
        ids = (prompt_ids + answer_ids)[:max_length]
        labels = ([-100] * len(prompt_ids) + answer_ids)[:max_length]
        if not any(v != -100 for v in labels):
            raise B07Error("max_length truncated all supervised answer tokens")
        examples.append((ids, labels))
    return examples


def _batch_iter(examples, batch_size: int) -> Iterator[list]:
    while True:
        for i in range(0, len(examples), batch_size):
            yield examples[i:i + batch_size]


def _configure_decoder_only_generation_tokenizer(tokenizer):
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise B07Error("tokenizer has neither pad_token_id nor eos_token_id")
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    if getattr(tokenizer, "padding_side", None) != "left":
        raise B07Error("decoder-only batched generation requires left padding")
    return tokenizer


def _collate(torch, tokenizer, batch, device: str):
    pad = tokenizer.pad_token_id
    if pad is None:
        if tokenizer.eos_token_id is None:
            raise B07Error("tokenizer has neither pad_token_id nor eos_token_id")
        pad = tokenizer.eos_token_id
    max_len = max(len(x[0]) for x in batch)
    input_ids, labels, attention = [], [], []
    for ids, labs in batch:
        padding = max_len - len(ids)
        input_ids.append(ids + [pad] * padding)
        labels.append(labs + [-100] * padding)
        attention.append([1] * len(ids) + [0] * padding)
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long, device=device),
        "labels": torch.tensor(labels, dtype=torch.long, device=device),
        "attention_mask": torch.tensor(attention, dtype=torch.long, device=device),
    }


def train_family_hf(
    config: Mapping[str, object],
    artifact_dir: os.PathLike[str] | str,
    family_id: str,
    device: str = "cuda:0",
    execution_context: Mapping[str, object] | None = None,
) -> dict:
    deps = _runtime_imports()
    torch = deps["torch"]
    AutoTokenizer = deps["AutoTokenizer"]
    AutoModelForCausalLM = deps["AutoModelForCausalLM"]
    LoraConfig = deps["LoraConfig"]
    get_peft_model = deps["get_peft_model"]

    family = next((f for f in config["families"] if f["id"] == family_id), None)  # type: ignore[index]
    if family is None:
        raise B07Error(f"unknown family: {family_id}")
    train_path = Path(artifact_dir) / "data" / family_id / "train.jsonl"
    manifest = load_json(Path(artifact_dir) / "dataset_manifest.json")
    verify_dataset_manifest(config, manifest)
    manifest_entry = dataset_manifest_family(manifest, family_id)
    if _sha256_file(train_path) != str(manifest_entry.get("train_sha256")):
        raise B07Error("training shard hash mismatch")
    rows = read_jsonl(train_path)
    if not rows:
        raise B07Error("empty training shard")

    base = config["base_model"]  # type: ignore[index]
    lcfg = config["lora"]  # type: ignore[index]
    seed = int(lcfg["seed"])
    # Make per-family initialization/data order deterministic but distinct.
    seed += int(hashlib.sha256(family_id.encode("utf-8")).hexdigest()[:6], 16) % 100000
    _seed_everything(torch, seed)
    dtype, dtype_name = _select_dtype(torch, device)
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        str(base["repo_id"]), revision=str(base["revision"]), trust_remote_code=bool(base["trust_remote_code"])
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(base["repo_id"]),
        revision=str(base["revision"]),
        trust_remote_code=bool(base["trust_remote_code"]),
        dtype=dtype,
    ).to(device)
    model.config.use_cache = False
    peft_cfg = LoraConfig(
        r=int(lcfg["rank"]),
        lora_alpha=int(lcfg["alpha"]),
        lora_dropout=float(lcfg["dropout"]),
        target_modules=[str(x) for x in lcfg["target_modules"]],
        bias=str(lcfg["bias"]),
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_cfg)
    model.train()
    trainable = [p for p in model.parameters() if p.requires_grad]
    if not trainable:
        raise B07Error("PEFT produced zero trainable parameters")
    optimizer = torch.optim.AdamW(
        trainable,
        lr=float(lcfg["learning_rate"]),
        weight_decay=float(lcfg["weight_decay"]),
    )
    examples = _tokenize_supervised(tokenizer, rows, int(lcfg["max_length"]))
    rng = random.Random(seed)
    rng.shuffle(examples)
    iterator = _batch_iter(examples, int(lcfg["batch_size"]))
    losses: List[float] = []
    max_steps = int(lcfg["max_steps"])
    optimizer.zero_grad(set_to_none=True)
    for step in range(max_steps):
        batch = _collate(torch, tokenizer, next(iterator), device)
        out = model(**batch)
        loss = out.loss
        if not torch.isfinite(loss):
            raise B07Error(f"non-finite training loss at step {step}")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        losses.append(float(loss.detach().cpu()))

    adapter_dir = Path(artifact_dir) / "adapters" / family_id
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir), safe_serialization=True)
    elapsed = time.perf_counter() - started
    peak_vram = None
    device_name = "cpu"
    if device.startswith("cuda"):
        peak_vram = int(torch.cuda.max_memory_allocated(device))
        device_name = torch.cuda.get_device_name(device)
    adapter_sha = _adapter_identity(adapter_dir)
    receipt = {
        "schema_version": "aqlevon.b07e0.train_receipt.v1",
        "experiment_id": config["experiment_id"],
        "family_id": family_id,
        "family_split": family["split"],
        "base_model": base,
        "lora": lcfg,
        "seed": seed,
        "steps": max_steps,
        "final_loss": losses[-1],
        "loss_start": losses[0],
        "elapsed_seconds": elapsed,
        "peak_vram_bytes": peak_vram,
        "device": device,
        "device_name": device_name,
        "dtype": dtype_name,
        "adapter_sha256": adapter_sha,
        "dataset_manifest_sha256": str(manifest.get("manifest_sha256")),
        "train_sha256": str(manifest_entry.get("train_sha256")),
        "versions": {
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "transformers": str(deps["transformers"].__version__),
            "peft": str(deps["peft"].__version__),
            "safetensors": str(deps["safetensors"].__version__),
        },
        "compute_authorization": dict(execution_context or {}),
        "gpu_execution_authorized_by_this_code": False,
        "note": "This receipt describes an actual invocation only. Compute authorization is external/Manager-provided and is recorded, not granted, by this code.",
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    write_json(adapter_dir / "b07_train_receipt.json", receipt)

    del model, optimizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return receipt


def train_family_dry_run(
    config: Mapping[str, object],
    artifact_dir: os.PathLike[str] | str,
    family_id: str,
    device: str = "cuda:0",
    execution_context: Mapping[str, object] | None = None,
) -> dict:
    family = next((f for f in config["families"] if f["id"] == family_id), None)  # type: ignore[index]
    if family is None:
        raise B07Error(f"unknown family: {family_id}")
    return {
        "schema_version": "aqlevon.b07e0.dry_run.v1",
        "family_id": family_id,
        "split": family["split"],
        "device": device,
        "would_train": True,
        "adapter_written": False,
        "base_model": config["base_model"],
        "lora": config["lora"],
        "compute_authorization": dict(execution_context or {}),
    }


TRAIN_RUNNERS = {
    "hf_peft": train_family_hf,
    "dry_run": train_family_dry_run,
}


def _resolve_model_module(model, adapter_module_name: str):
    modules = dict(model.named_modules())
    if adapter_module_name in modules:
        return modules[adapter_module_name]
    # Be strict but tolerate one common PEFT path prefix mismatch.
    candidates = [name for name in modules if name.endswith(adapter_module_name)]
    if len(candidates) == 1:
        return modules[candidates[0]]
    raise B07Error(f"cannot uniquely resolve adapter module into base model: {adapter_module_name}")


@contextlib.contextmanager
def patched_model(model, bundles: Sequence[DeltaBundle], coeffs: np.ndarray):
    deps = _runtime_imports()
    torch = deps["torch"]
    if len(bundles) != len(coeffs):
        raise B07Error("bundle/coeff count mismatch")
    if not bundles:
        yield model
        return
    ref = bundles[0]
    for b in bundles[1:]:
        ref.validate_compatible(b)
    applied: List[Tuple[object, object]] = []
    try:
        with torch.no_grad():
            for name in ref.module_names():
                module = _resolve_model_module(model, name)
                if not hasattr(module, "weight"):
                    raise B07Error(f"target module lacks weight: {name}")
                weight = module.weight
                delta = torch.zeros_like(weight)
                for coeff, bundle in zip(coeffs, bundles):
                    if abs(float(coeff)) < 1e-15:
                        continue
                    part = bundle.modules[name]
                    a = torch.as_tensor(part.a, dtype=weight.dtype, device=weight.device)
                    b = torch.as_tensor(part.b, dtype=weight.dtype, device=weight.device)
                    delta.add_(b @ a, alpha=float(coeff) * float(part.scale))
                weight.add_(delta)
                applied.append((weight, delta))
        yield model
    finally:
        with torch.no_grad():
            for weight, delta in reversed(applied):
                weight.sub_(delta)


def _parse_generated_integer(text: str) -> int | None:
    match = re.search(r"[-+]?\d+", text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def evaluate_rows(model, tokenizer, rows: Sequence[Mapping[str, object]], device: str, batch_size: int = 8, max_new_tokens: int = 12) -> dict:
    if getattr(tokenizer, "padding_side", None) != "left":
        raise B07Error("decoder-only batched generation requires tokenizer.padding_side='left'")
    deps = _runtime_imports()
    torch = deps["torch"]
    model.eval()
    total = 0
    passed = 0
    invalid = 0
    outputs = []
    for i in range(0, len(rows), batch_size):
        batch_rows = rows[i:i + batch_size]
        prompts = [str(r["prompt"]) for r in batch_rows]
        tokens = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True, max_length=96)
        tokens = {k: v.to(device) for k, v in tokens.items()}
        with torch.no_grad():
            generated = model.generate(
                **tokens,
                do_sample=False,
                max_new_tokens=max_new_tokens,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                use_cache=True,
            )
        prompt_len = tokens["input_ids"].shape[1]
        suffix = generated[:, prompt_len:]
        texts = tokenizer.batch_decode(suffix, skip_special_tokens=True)
        for row, text in zip(batch_rows, texts):
            pred = _parse_generated_integer(text)
            target = int(row["target"])
            ok = pred == target
            total += 1
            passed += int(ok)
            invalid += int(pred is None)
            outputs.append({"prediction": pred, "target": target, "pass": ok, "text": text[:200]})
    return {
        "pass_rate": passed / max(total, 1),
        "passed": passed,
        "total": total,
        "invalid": invalid,
        "outputs": outputs,
    }


def evaluate_b07(
    config: Mapping[str, object],
    artifact_dir: os.PathLike[str] | str,
    compiler,
    training_bundles: Sequence[DeltaBundle],
    training_features: np.ndarray,
    holdout_features: Mapping[str, np.ndarray],
    device: str = "cuda:0",
    execution_context: Mapping[str, object] | None = None,
) -> dict:
    deps = _runtime_imports()
    torch = deps["torch"]
    AutoTokenizer = deps["AutoTokenizer"]
    AutoModelForCausalLM = deps["AutoModelForCausalLM"]
    base = config["base_model"]  # type: ignore[index]
    dtype, dtype_name = _select_dtype(torch, device)
    tokenizer = AutoTokenizer.from_pretrained(
        str(base["repo_id"]), revision=str(base["revision"]), trust_remote_code=bool(base["trust_remote_code"])
    )
    _configure_decoder_only_generation_tokenizer(tokenizer)
    model = AutoModelForCausalLM.from_pretrained(
        str(base["repo_id"]),
        revision=str(base["revision"]),
        trust_remote_code=bool(base["trust_remote_code"]),
        dtype=dtype,
    ).to(device)
    model.config.use_cache = True
    manifest = load_json(Path(artifact_dir) / "dataset_manifest.json")
    verify_dataset_manifest(config, manifest)
    if str(manifest.get("manifest_sha256")) != str(compiler.dataset_manifest_sha256):
        raise B07Error("dataset manifest changed after compiler freeze")
    geometry = build_geometry(training_bundles)
    random_seed = int(config["compiler"]["random_control_seed"])  # type: ignore[index]
    result_families = []

    for index, family in enumerate([f for f in config["families"] if f["split"] == "compiler_holdout"]):  # type: ignore[index]
        family_id = str(family["id"])
        hidden_path = Path(artifact_dir) / "data" / family_id / "hidden.jsonl"
        semantic_path = Path(artifact_dir) / "data" / family_id / "semantic_hidden.jsonl"
        manifest_entry = dataset_manifest_family(manifest, family_id)
        if _sha256_file(hidden_path) != str(manifest_entry.get("hidden_sha256")):
            raise B07Error(f"hidden shard hash mismatch: {family_id}")
        if _sha256_file(semantic_path) != str(manifest_entry.get("semantic_hidden_sha256")):
            raise B07Error(f"semantic-hidden shard hash mismatch: {family_id}")
        hidden = read_jsonl(hidden_path)
        semantic = read_jsonl(semantic_path)
        direct = load_delta_bundle(Path(artifact_dir) / "adapters" / family_id, config, family_id)
        training_bundles[0].validate_compatible(direct)
        controls = baseline_coefficients(
            compiler,
            geometry,
            holdout_features[family_id],
            training_features,
            random_seed + index,
        )
        controls["oracle_span_projection"] = oracle_span_projection_coeffs(direct, training_bundles, geometry)

        candidates: Dict[str, dict] = {}
        # Base and zero update are intentionally both reported: zero is a mandatory control,
        # base is the Lift denominator.
        base_hidden = evaluate_rows(model, tokenizer, hidden, device)
        base_sem = evaluate_rows(model, tokenizer, semantic, device)
        candidates["base"] = {
            "hidden": base_hidden["pass_rate"],
            "semantic_hidden": base_sem["pass_rate"],
            "details": {"hidden": base_hidden, "semantic_hidden": base_sem},
        }
        candidates["zero_update"] = {
            "hidden": base_hidden["pass_rate"],
            "semantic_hidden": base_sem["pass_rate"],
        }

        for name in ["compiled", "random_same_norm", "nearest_adapter", "mean_delta", "basis_pc1_same_norm", "oracle_span_projection"]:
            coeffs = controls[name]
            with patched_model(model, training_bundles, coeffs):
                h = evaluate_rows(model, tokenizer, hidden, device)
                s = evaluate_rows(model, tokenizer, semantic, device)
            candidates[name] = {
                "hidden": h["pass_rate"],
                "semantic_hidden": s["pass_rate"],
                "source_coefficients": coeffs.tolist(),
                "operator_norm": geometry.mixture_norm(coeffs),
                "distance_to_direct_operator": None,
            }

        # The direct held-out adapter is an upper anchor only; it is never read by fit_compiler.
        with patched_model(model, [direct], np.asarray([1.0], dtype=np.float64)):
            h = evaluate_rows(model, tokenizer, hidden, device)
            s = evaluate_rows(model, tokenizer, semantic, device)
        candidates["direct_lora"] = {
            "hidden": h["pass_rate"],
            "semantic_hidden": s["pass_rate"],
            "adapter_sha256": direct.adapter_sha256,
            "operator_norm": direct.norm(),
        }

        for name in ["compiled", "random_same_norm", "nearest_adapter", "mean_delta", "basis_pc1_same_norm", "oracle_span_projection"]:
            coeffs = np.asarray(candidates[name]["source_coefficients"], dtype=np.float64)
            mix_sq = geometry.mixture_inner(coeffs, coeffs)
            direct_sq = direct.inner(direct)
            cross = direct_inner_with_mixture(direct, training_bundles, coeffs)
            candidates[name]["distance_to_direct_operator"] = math.sqrt(max(0.0, mix_sq + direct_sq - 2 * cross))

        result_families.append({
            "family_id": family_id,
            "candidates": candidates,
        })

    result = {
        "schema_version": "aqlevon.b07e0.results.v1",
        "experiment_id": config["experiment_id"],
        "task_id": config["task_id"],
        "config_sha256": sha256_json(config),
        "compiler_sha256": sha256_json(compiler.to_json()),
        "dataset_manifest_sha256": str(manifest.get("manifest_sha256")),
        "base_model": base,
        "dtype": dtype_name,
        "device": device,
        "compute_authorization": dict(execution_context or {}),
        "holdout_families": result_families,
    }
    result["results_sha256"] = sha256_json(result)
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result
