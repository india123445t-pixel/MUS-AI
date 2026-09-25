#!/usr/bin/env python3
"""Package and validate the frozen A1 adapter for Worker05."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

MODEL = "Qwen/Qwen3.5-4B-Base"
REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
ARM = "P4_A1_RLVR_CONTROL"
SEED = 1701
PLAN_SHA = "3cd6e0bada2535a80f83f400f45f5d0fdc5ad8d938f42757785335959f331095"
RUN_SHA = "b277b41d3d67be1180b4d0600ab6f533f6dbf7b69163980ef5ecc6f0677195b7"
LOCK_SHA = "10f333cf453f5896402066d7c483ae170688909ca82a08a0adb1e90766213fcb"
W02_SHA = "f7499362fdd7e6fd4bc91682a5f1c03767c98685c045ad50a712711c6c4ad55f"
TARGETS = r".*\.self_attn\.(q_proj|v_proj)$"
LAYERS = (3, 7, 11, 15, 19, 23, 27, 31)
KEY = re.compile(r"(?:^|\.)layers\.(\d+)\.self_attn\.(q_proj|v_proj)\.lora_([AB])(?:\.default)?\.weight$")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha_bytes(raw.encode("utf-8"))


def state_sha(state: dict[str, Any]) -> str:
    h = hashlib.sha256()
    for name in sorted(state):
        t = state[name].detach().cpu().contiguous().float()
        h.update(name.encode("utf-8"))
        h.update(str(tuple(t.shape)).encode("ascii"))
        h.update(t.numpy().tobytes(order="C"))
    return h.hexdigest()


def validate_config(config: Any) -> None:
    expected = {
        "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 4,
        "lora_alpha": 4, "bias": "none", "target_modules": TARGETS,
    }
    if not isinstance(config, dict):
        raise ValueError("adapter_config_not_object")
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"adapter_config_mismatch:{key}:{config.get(key)!r}")
    if config.get("init_lora_weights", True) is not True:
        raise ValueError("adapter_initialization_not_frozen_zero_B")
    if config.get("use_dora", False) is not False or config.get("use_rslora", False) is not False:
        raise ValueError("adapter_variant_mismatch")


def validate_tensor_shapes(items: list[tuple[str, tuple[int, ...]]]) -> dict[str, Any]:
    observed: dict[tuple[int, str], dict[str, tuple[int, ...]]] = {}
    for name, shape in items:
        match = KEY.search(name)
        if not match:
            raise ValueError(f"adapter_tensor_outside_frozen_topology:{name}")
        module = (int(match.group(1)), match.group(2))
        part = match.group(3)
        if part in observed.setdefault(module, {}):
            raise ValueError(f"duplicate_adapter_tensor:{name}")
        observed[module][part] = tuple(int(x) for x in shape)
    expected = {(i, p) for i in LAYERS for p in ("q_proj", "v_proj")}
    if set(observed) != expected:
        raise ValueError(f"adapter_topology_mismatch:missing={sorted(expected-set(observed))}:extra={sorted(set(observed)-expected)}")
    layout = []
    for module in sorted(expected):
        pair = observed[module]
        if set(pair) != {"A", "B"}:
            raise ValueError(f"adapter_A_B_pair_missing:{module}")
        a, b = pair["A"], pair["B"]
        if len(a) != 2 or len(b) != 2 or a[0] != 4 or b[1] != 4 or a[1] != b[0]:
            raise ValueError(f"adapter_rank_shape_mismatch:{module}:{a}:{b}")
        layout.append({"module": f"layers.{module[0]}.self_attn.{module[1]}",
                       "lora_A_shape": list(a), "lora_B_shape": list(b)})
    return {"modules": layout, "module_count": 16, "tensor_count": 32, "A_count": 16, "B_count": 16}


def count_nonzero_B(state: dict[str, Any]) -> int:
    count = 0
    for name, tensor in state.items():
        match = KEY.search(name)
        if not match or match.group(3) != "B":
            continue
        if hasattr(tensor, "count_nonzero"):
            n = tensor.count_nonzero()
            count += int(n.item() if hasattr(n, "item") else n)
        elif isinstance(tensor, (list, tuple)):
            count += sum(x != 0 for x in tensor)
        else:
            raise TypeError(f"unsupported_adapter_tensor:{name}")
    return count


def inventory(root: Path) -> list[dict[str, Any]]:
    out = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and not any(part in {".cache", ".git"} for part in rel.parts):
            out.append({"path": rel.as_posix(), "size": path.stat().st_size, "sha256": sha_file(path)})
    if not out:
        raise ValueError("base_model_inventory_empty")
    return out


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_inputs(run: dict, plan: dict, lock: dict, binding: dict, agent: Path) -> str:
    sys.path.insert(0, str(agent))
    import p4_gene1_trainer as contract
    for obj, field, wanted in ((run, "manifest_sha256", RUN_SHA),
                               (plan, "plan_sha256", PLAN_SHA),
                               (lock, "lock_sha256", LOCK_SHA)):
        if not contract.verify_self_digest(obj, field) or obj.get(field) != wanted:
            raise ValueError(f"frozen_{field}_mismatch")
    if not contract.verify_self_digest(binding, "binding_sha256"):
        raise ValueError("runtime_binding_hash_mismatch")
    if binding.get("runtime_appliance_digest") != os.environ.get("AQLEVON_EXPECTED_IMAGE_DIGEST"):
        raise ValueError("runtime_image_binding_mismatch")
    tested = binding.get("worker03_runtime_source_commit", "")
    execution = os.environ.get("AQLEVON_EXPECTED_W03_HEAD", "")
    if not re.fullmatch(r"[0-9a-f]{40}", tested) or not re.fullmatch(r"[0-9a-f]{40}", execution) or tested == execution:
        raise ValueError("runtime_binding_source_commit_mismatch")
    if run.get("arm_id") != ARM or run.get("seed") != SEED or run.get("training_plan_sha256") != PLAN_SHA:
        raise ValueError("run_identity_mismatch")
    if run.get("worker02_training_manifest_sha256") != W02_SHA:
        raise ValueError("run_training_data_identity_mismatch")
    if run.get("student_model") != {"repo": MODEL, "revision": REVISION, "precision": "bf16", "quantization": "none"}:
        raise ValueError("run_model_identity_mismatch")
    if run.get("budget", {}).get("optimizer_updates") != 12:
        raise ValueError("run_update_budget_mismatch")
    argv = lock.get("argv", [])
    if lock.get("run_manifest_sha256") != RUN_SHA or lock.get("arm_id") != ARM or lock.get("seed") != SEED:
        raise ValueError("command_lock_identity_mismatch")
    if "trainer.total_training_steps=12" not in argv or "trainer.save_freq=12" not in argv:
        raise ValueError("locked_12_step_checkpoint_settings_missing")
    if f"actor_rollout_ref.model.target_modules='{TARGETS}'" not in argv:
        raise ValueError("locked_target_modules_regex_mismatch")
    if "actor_rollout_ref.model.lora_rank=4" not in argv or "actor_rollout_ref.model.lora_alpha=4" not in argv:
        raise ValueError("locked_lora_rank_or_alpha_mismatch")
    return tested


def package_candidate(adapter_dir: Path, checkpoints: Path, model_dir: Path,
                      run_path: Path, plan_path: Path, lock_path: Path,
                      output: Path, agent: Path) -> dict[str, Any]:
    run, plan, lock = read_json(run_path), read_json(plan_path), read_json(lock_path)
    binding_name = os.environ.get("AQLEVON_RESOLVED_BINDING_FILE", "")
    if not binding_name or Path(binding_name).name != binding_name:
        raise ValueError("runtime_binding_filename_missing")
    tested_source = verify_inputs(run, plan, lock, read_json(agent / binding_name), agent)
    if output.exists():
        raise ValueError(f"candidate_output_exists:{output}")
    step = checkpoints / "global_step_12"
    latest = checkpoints / "latest_checkpointed_iteration.txt"
    if not latest.is_file() or latest.read_text().strip() != "12":
        raise ValueError("checkpoint_latest_step_not_12")
    actor = step / "actor"
    if adapter_dir.resolve() != (actor / "lora_adapter").resolve():
        raise ValueError("adapter_not_from_locked_step12_actor")
    if not any(actor.glob("*.pt")) and not any(actor.glob("*.safetensors")):
        raise ValueError("actor_checkpoint_payload_missing")
    config_path = adapter_dir / "adapter_config.json"
    weights_path = adapter_dir / "adapter_model.safetensors"
    if not config_path.is_file() or not weights_path.is_file():
        raise ValueError("saved_adapter_files_missing")
    validate_config(read_json(config_path))

    output.mkdir(parents=True, exist_ok=False)
    artifact = output / "candidate_artifact"
    artifact.mkdir()
    shutil.copy2(config_path, artifact / config_path.name)
    shutil.copy2(weights_path, artifact / weights_path.name)

    from safetensors.torch import load_file
    saved = load_file(str(artifact / "adapter_model.safetensors"), device="cpu")
    layout = validate_tensor_shapes([(n, tuple(t.shape)) for n, t in saved.items()])
    saved_hash = state_sha(saved)
    changed = count_nonzero_B(saved)
    del saved
    if changed <= 0:
        raise ValueError("trained_lora_B_delta_is_zero")

    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("candidate_peft_reload_requires_cuda_bf16")
    from peft import PeftModel, get_peft_model_state_dict
    from transformers import Qwen3_5ForConditionalGeneration
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(model_dir), trust_remote_code=False, dtype=torch.bfloat16,
        device_map={"": torch.cuda.current_device()}, low_cpu_mem_usage=True, local_files_only=True)
    restored = PeftModel.from_pretrained(base, str(artifact), is_trainable=False)
    reloaded = get_peft_model_state_dict(restored)
    reload_layout = validate_tensor_shapes([(n, tuple(t.shape)) for n, t in reloaded.items()])
    reload_hash = state_sha(reloaded)
    if reload_hash != saved_hash or reload_layout != layout:
        raise ValueError("saved_candidate_reload_mismatch")
    del reloaded, restored, base
    torch.cuda.synchronize()
    torch.cuda.empty_cache()

    model_files = inventory(model_dir)
    token_files = [x for x in model_files if any(k in Path(x["path"]).name.casefold()
                   for k in ("tokenizer", "vocab", "merges", "special_tokens", "added_tokens", "chat_template"))]
    base_config = model_dir / "config.json"
    if not token_files or not base_config.is_file():
        raise ValueError("base_tokenizer_or_config_missing")
    packages = {n: metadata.version(n) for n in ("transformers", "peft", "ray", "vllm", "safetensors", "torch")}
    for key, val in {"transformers": "5.17.0", "peft": "0.21.0", "ray": "2.53.0", "vllm": "0.19.1"}.items():
        if packages[key] != val:
            raise ValueError(f"runtime_package_mismatch:{key}:{packages[key]}")
    digest = os.environ["AQLEVON_EXPECTED_IMAGE_DIGEST"]
    execution = os.environ["AQLEVON_EXPECTED_W03_HEAD"]
    receipt = {
        "receipt_kind": "AQLEVON_P4_SURROGATE_TRAINING_RECEIPT_V1",
        "run_manifest_sha256": RUN_SHA, "training_plan_sha256": PLAN_SHA,
        "arm_id": ARM, "seed": SEED, "sealed_eval_consumed": False, "capability_gain_claim": False,
        "training": {"optimizer_updates": 12, "global_step": 12, "checkpoint_latest_iteration": 12,
                     "changed_elements": changed,
                     "changed_elements_semantics": "nonzero LoRA-B entries relative to frozen zero-B init"},
        "artifact": {"saved_adapter_state_sha256": saved_hash,
                     "reloaded_adapter_state_sha256": reload_hash, "reload_hash_match": True},
        "runtime": {"w03_tested_source_commit": tested_source, "w03_execution_head": execution,
                    "runtime_appliance_digest": digest, "sdpo_commit": "7c457fc1b1f636ae794eb0362ba37d4743b06fbc",
                    "optimizer_updates_verified_by": "successful SDPO exit and global_step_12 checkpoint"},
    }
    receipt_path = output / "training_run_receipt.json"
    write_json(receipt_path, receipt)
    import candidate_artifact_manifest as cam
    spec = {
        "artifact_type": "adapter", "artifact_stage": "reproducible_gene",
        "base": {"repo": MODEL, "revision": REVISION,
                 "base_manifest_sha256": canonical_sha({"repo": MODEL, "revision": REVISION, "files": model_files})},
        "tokenizer_sha256": canonical_sha(token_files), "config_sha256": sha_file(base_config),
        "training_shard_manifest_sha256": W02_SHA, "training_run_receipt_sha256": sha_file(receipt_path),
        "merge_recipe_sha256": None,
        "parameter_layout_sha256": canonical_sha({"target_modules": TARGETS, "rank": 4, "alpha": 4, **layout}),
        "topology_class": "CUSTOM_EXPERIMENTAL", "adapter_state_sha256": saved_hash,
        "checkpoint_state_sha256": None, "parent_candidate_artifact_manifest_sha256": [],
        "environment_toolchain_manifest_sha256": canonical_sha({"packages": packages, "runtime_appliance_digest": digest,
                                                                "sdpo_commit": "7c457fc1b1f636ae794eb0362ba37d4743b06fbc"}),
    }
    manifest = cam.build_manifest(spec, artifact)
    write_json(output / "candidate_artifact_manifest.json", manifest)
    errors = cam.validate_manifest(read_json(output / "candidate_artifact_manifest.json"), artifact_root=artifact)
    if errors:
        raise ValueError("candidate_manifest_validation_failed:" + ";".join(errors))
    index = {"handoff_kind": "AQLEVON_P4_A1_WORKER05_CANDIDATE_HANDOFF_V1",
             "candidate_artifact_manifest_sha256": manifest["manifest_sha256"],
             "training_run_receipt_sha256": sha_file(receipt_path), "adapter_state_sha256": saved_hash,
             "run_manifest_sha256": RUN_SHA, "command_lock_sha256": LOCK_SHA, "training_plan_sha256": PLAN_SHA,
             "w03_tested_source_commit": tested_source, "w03_execution_head": execution,
             "arm_id": ARM, "seed": SEED, "optimizer_updates": 12,
             "candidate_status": "ARTIFACT_READY_FOR_WORKER05_EVALUATION",
             "capability_gain_claim": False, "sealed_eval_consumed": False}
    write_json(output / "worker05_handoff_index.json", index)
    shutil.copy2(run_path, output / "run_manifest.json")
    shutil.copy2(plan_path, output / "training_plan.json")
    shutil.copy2(lock_path, output / "command_lock.json")
    print("AQLEVON_P4_A1_CANDIDATE_PACKAGE_PASS", flush=True)
    print("AQLEVON_SDPO_LORA_STATE_EXTRACTED count=32 A=16 B=16 modules=16", flush=True)
    print("AQLEVON_TRAINING_UPDATES_VERIFIED=12", flush=True)
    print("AQLEVON_CANDIDATE_ARTIFACT_MANIFEST_SHA256=" + manifest["manifest_sha256"], flush=True)
    print("AQLEVON_TRAINING_RECEIPT_SHA256=" + sha_file(receipt_path), flush=True)
    return index


def self_test() -> None:
    validate_config({"peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 4, "lora_alpha": 4,
                     "bias": "none", "target_modules": TARGETS})
    try:
        validate_config({"peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 4, "lora_alpha": 4,
                         "bias": "none", "target_modules": list(TARGETS)})
    except ValueError as exc:
        assert "target_modules" in str(exc)
    else:
        raise AssertionError("regex_target_modules_character_list_accepted")
    entries = []
    for layer in LAYERS:
        for proj in ("q_proj", "v_proj"):
            entries.extend([(f"base_model.model.model.layers.{layer}.self_attn.{proj}.lora_A.weight", (4, 8)),
                            (f"base_model.model.model.layers.{layer}.self_attn.{proj}.lora_B.weight", (8, 4))])
    layout = validate_tensor_shapes(entries)
    assert layout["module_count"] == 16 and layout["tensor_count"] == 32
    assert layout["A_count"] == 16 and layout["B_count"] == 16
    assert count_nonzero_B({"layers.3.self_attn.q_proj.lora_B.weight": [0, 3, -1]}) == 2
    try:
        validate_tensor_shapes(entries[:-1])
    except ValueError as exc:
        assert "adapter_A_B_pair_missing" in str(exc)
    else:
        raise AssertionError("incomplete_adapter_pair_accepted")
    print("AQLEVON_P4_A1_CANDIDATE_PACKAGER_SELF_TEST_PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--adapter-dir", type=Path)
    ap.add_argument("--checkpoint-root", type=Path)
    ap.add_argument("--model-dir", type=Path)
    ap.add_argument("--run-manifest", type=Path)
    ap.add_argument("--training-plan", type=Path)
    ap.add_argument("--command-lock", type=Path)
    ap.add_argument("--agent-dir", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--output-dir", type=Path)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    required = (args.adapter_dir, args.checkpoint_root, args.model_dir, args.run_manifest,
                args.training_plan, args.command_lock, args.output_dir)
    if any(x is None for x in required):
        ap.error("all artifact paths are required unless --self-test is used")
    package_candidate(args.adapter_dir, args.checkpoint_root, args.model_dir, args.run_manifest,
                      args.training_plan, args.command_lock, args.output_dir, args.agent_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
