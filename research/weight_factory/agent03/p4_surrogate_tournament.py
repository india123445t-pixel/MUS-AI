#!/usr/bin/env python3
"""Prepare the frozen AQLEVON P4 surrogate tournament without sealed eval.

A1/A2 consume the pinned lasgroup/SDPO semantics. A0 uses Worker03's SFT
control runner.  This module prepares only training-visible Worker02 data.
Private/sealed evaluation bytes are never accepted here.
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import p4_gene1_trainer as c

W01_STACK = {
    "transformers": "5.17.0",
    "peft": "0.21.0",
    "accelerate": "1.15.0",
}
TARGET_REGEX = r".*\.self_attn\.(q_proj|v_proj)$"
MAX_MODEL_LEN = 4096
GPU_MEMORY_UTILIZATION = "0.20"
RUNTIME_MODEL_FRAGMENT = "qwen35-4b-daa9c16f3712"


def bridge_processor_chat_template(processor: Any, name_or_path: Any) -> Any:
    """Bridge Transformers 5.17 Qwen3.5 processor/template mismatch.

    The exact pinned Qwen3.5 Base tokenizer carries the canonical chat template,
    while AutoProcessor in the pinned runtime can expose a Qwen3VLProcessor with
    an empty processor.chat_template.  For this exact staged model only, copy
    the already-loaded tokenizer template onto the processor.  No prompt text,
    model weights, dataset rows, or training hyperparameters are changed.
    """
    if processor is None or RUNTIME_MODEL_FRAGMENT not in str(name_or_path):
        return processor
    if getattr(processor, "chat_template", None):
        return processor
    tokenizer = getattr(processor, "tokenizer", None)
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str) or not template:
        raise c.ContractError("qwen35_processor_template_bridge_missing_tokenizer_template")
    processor.chat_template = template
    return processor


def install_runtime_compat() -> None:
    """Install exact-process compatibility shims without mutating Ray config.

    The pinned SDPO source is patched separately for Transformers 5.17 removed
    symbols. This function only bridges the exact Qwen3.5 processor chat
    template in the current Python process. It intentionally does not place
    callables into veRL's Ray runtime_env because OmegaConf only accepts
    primitive/container values there.
    """
    import sys
    import transformers

    if not hasattr(transformers, "AutoModelForVision2Seq"):
        transformers.AutoModelForVision2Seq = transformers.AutoModelForImageTextToText

    import verl.utils as verl_utils
    import verl.utils.tokenizer as verl_tokenizer

    current = verl_tokenizer.hf_processor
    if getattr(current, "_aqlevon_p4_runtime_compat", False):
        return

    def compat_hf_processor(name_or_path, **kwargs):
        processor = current(name_or_path, **kwargs)
        return bridge_processor_chat_template(processor, name_or_path)

    compat_hf_processor._aqlevon_p4_runtime_compat = True
    compat_hf_processor._aqlevon_original = current
    verl_tokenizer.hf_processor = compat_hf_processor
    verl_utils.hf_processor = compat_hf_processor

    loaded_main = sys.modules.get("verl.trainer.main_ppo")
    if loaded_main is not None:
        loaded_main.hf_processor = compat_hf_processor


def sha(path: Path) -> str:
    return c.sha256_file(path)


def _arm(plan: dict[str, Any], arm_id: str) -> dict[str, Any]:
    found = [x for x in plan["arms"] if x.get("arm_id") == arm_id]
    if len(found) != 1:
        raise c.ContractError("arm_missing_or_duplicate")
    return found[0]


def _check_plan(plan: dict[str, Any]) -> None:
    if not c.verify_self_digest(plan, "plan_sha256"):
        raise c.ContractError("invalid_frozen_plan_hash")
    if plan.get("plan_kind") != c.FROZEN_PLAN_KIND:
        raise c.ContractError("invalid_frozen_plan_kind")
    if plan.get("g1_status") != c.G1_STATUS:
        raise c.ContractError("g1_status_mismatch")
    if plan.get("sealed_eval_consumed") is not False:
        raise c.ContractError("sealed_eval_consumption_forbidden")
    if (plan.get("surrogate_model") or {}).get("repo") != c.SURROGATE_MODEL:
        raise c.ContractError("surrogate_model_mismatch")
    if (plan.get("surrogate_model") or {}).get("revision") != c.SURROGATE_REVISION:
        raise c.ContractError("surrogate_revision_mismatch")
    if plan.get("profile") != c.PROFILE:
        raise c.ContractError("surrogate_profile_mismatch")


def build_training_records(
    shard_path: Path,
    pack_path: Path,
) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in shard_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    hard = {
        task["prompt"]: task
        for task in pack["tasks"]
        if task.get("verifier_mode") == "hardened"
        and task.get("training_eligible") is True
    }
    if len(rows) != 56:
        raise c.ContractError(f"expected_56_training_rows_observed_{len(rows)}")
    records: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if row.get("row_kind") != c.W02_ROW_KIND:
            raise c.ContractError(f"training_row_kind_mismatch:{i}")
        task = hard.get(row.get("prompt"))
        if not task:
            raise c.ContractError(f"training_row_not_bound_to_hardened_task:{i}")
        if row.get("answer") != task.get("oracle_program"):
            raise c.ContractError(f"sft_oracle_binding_mismatch:{i}")
        ground_truth = {
            "initial_state": task["visible_initial_state"],
            "oracle_program": row["answer"],
        }
        records.append(
            {
                "data_source": "aqlevon_gene1",
                "prompt": [{"role": "user", "content": row["prompt"]}],
                "ability": "code_tool_json_dsl",
                "reward_model": {
                    "style": "rule",
                    "ground_truth": json.dumps(
                        ground_truth,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
                "extra_info": {
                    "split": "train_visible",
                    "index": i,
                    "record_id": row["record_id"],
                    "semantic_core_id": task["semantic_core_id"],
                    "task_sha256": task["task_sha256"],
                },
            }
        )
    return records


def write_parquet_records(
    records: list[dict[str, Any]],
    out_dir: Path,
) -> dict[str, str]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as exc:
        raise c.ContractError(
            "pyarrow_required_for_sdpo_parquet_preparation"
        ) from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records)
    paths = {
        "train": out_dir / "train.parquet",
        "test": out_dir / "test.parquet",
    }
    for path in paths.values():
        pq.write_table(table, path, compression="zstd")
    return {
        "rows": str(len(records)),
        "train_parquet_sha256": sha(paths["train"]),
        "test_parquet_sha256": sha(paths["test"]),
    }


def build_training_parquet(
    shard_path: Path,
    pack_path: Path,
    out_dir: Path,
) -> dict[str, str]:
    records = build_training_records(shard_path, pack_path)
    result = write_parquet_records(records, out_dir)
    manifest = {
        "schema_version": 1,
        "record_kind": "AQLEVON_P4_SURROGATE_PUBLIC_DATA_PREP_V1",
        "training_shard_sha256": sha(shard_path),
        "training_visible_pack_sha256": sha(pack_path),
        "row_count": len(records),
        "train_parquet_sha256": result["train_parquet_sha256"],
        "test_parquet_sha256": result["test_parquet_sha256"],
        "sealed_eval_consumed": False,
    }
    manifest = c.seal(manifest, "manifest_sha256")
    (out_dir / "data_prep_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {**result, "data_prep_manifest_sha256": manifest["manifest_sha256"]}


def _base_rl_args(
    plan: dict[str, Any],
    data_dir: Path,
    model_dir: Path,
    out_dir: Path,
    reward_path: Path,
) -> list[str]:
    generation = plan["generation"]
    return [
        f"data.train_files={data_dir / 'train.parquet'}",
        f"data.val_files={data_dir / 'test.parquet'}",
        "data.train_batch_size=4",
        "data.max_prompt_length=2048",
        "data.max_response_length=2048",
        "data.filter_overlong_prompts=True",
        "data.truncation=error",
        "data.seed=1701",
        "actor_rollout_ref.actor.data_loader_seed=1701",
        "actor_rollout_ref.actor.fsdp_config.seed=1701",
        "actor_rollout_ref.ref.fsdp_config.seed=1701",
        "++actor_rollout_ref.rollout.engine_kwargs.vllm.seed=1701",
        f"max_model_len={MAX_MODEL_LEN}",
        f"actor_rollout_ref.model.path={model_dir}",
        "actor_rollout_ref.model.trust_remote_code=False",
        "actor_rollout_ref.model.lora_rank=4",
        "actor_rollout_ref.model.lora_alpha=4",
        f"actor_rollout_ref.model.target_modules=\'{TARGET_REGEX}\'",
        "actor_rollout_ref.model.exclude_modules=\'.*(visual|vision|lm_head|embed|mtp|norm|linear_attn).*\'",
        "actor_rollout_ref.actor.optim.lr=1e-5",
        "actor_rollout_ref.actor.optim.lr_warmup_steps=10",
        "actor_rollout_ref.actor.ppo_mini_batch_size=4",
        "actor_rollout_ref.rollout.n=4",
        f"actor_rollout_ref.rollout.temperature={generation['temperature']}",
        f"actor_rollout_ref.rollout.top_p={generation['top_p']}",
        f"actor_rollout_ref.rollout.top_k={generation['top_k']}",
        "actor_rollout_ref.rollout.calculate_log_probs=True",
        "actor_rollout_ref.rollout.tensor_model_parallel_size=1",
        f"actor_rollout_ref.rollout.max_model_len={MAX_MODEL_LEN}",
        f"actor_rollout_ref.rollout.max_num_batched_tokens={MAX_MODEL_LEN}",
        f"actor_rollout_ref.rollout.gpu_memory_utilization={GPU_MEMORY_UTILIZATION}",
        "algorithm.rollout_correction.rollout_is=token",
        f"custom_reward_function.path={reward_path}",
        "custom_reward_function.name=compute_score",
        "++ray_kwargs.ray_init.runtime_env.env_vars.PYTHONPATH='/workspace/MUS-AI/research/weight_factory/agent03/runtime_compat:/workspace/MUS-AI/research/weight_factory/agent03'",
        "++ray_kwargs.ray_init.runtime_env.env_vars.USER=root",
        "++ray_kwargs.ray_init.runtime_env.env_vars.EXPERIMENT=AQLEVON-P4-A1-seed1701",
        "++ray_kwargs.ray_init.runtime_env.env_vars.TASK=/workspace/aqlevon_p4/data",
        "trainer.n_gpus_per_node=1",
        "trainer.nnodes=1",
        "trainer.total_training_steps=12",
        "trainer.save_freq=12",
        "trainer.test_freq=-1",
        "trainer.val_before_train=False",
        "trainer.logger=console",
        "trainer.resume_mode=disable",
        f"trainer.default_local_dir={out_dir / 'checkpoints'}",
        "trainer.max_actor_ckpt_to_keep=1",
    ]


def build_a1_argv(plan_path: Path, workspace: Path) -> list[str]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    _check_plan(plan)
    arm = _arm(plan, "P4_A1_RLVR_CONTROL")
    if (
        arm.get("rollout_group_size") != 4
        or arm.get("ppo_mini_batch_size") != 8
        or arm.get("lr") != "0.00001"
        or arm.get("rollout_importance_sampling") != "token"
    ):
        raise c.ContractError("A1_contract_mismatch")
    repo = workspace / "SDPO"
    data = workspace / "aqlevon_p4/data"
    model = workspace / ("models/qwen35-4b-" + c.SURROGATE_REVISION[:12])
    out = workspace / "aqlevon_p4/runs/P4_A1_RLVR_CONTROL_seed1701"
    reward = (
        workspace
        / "MUS-AI/research/weight_factory/agent03/p4_aqlevon_reward.py"
    )
    return [
        "env",
        "USER=root",
        "bash",
        str(repo / "training/verl_training.sh"),
        "AQLEVON-P4-A1-seed1701",
        "baseline_grpo",
        str(data),
        *_base_rl_args(plan, data, model, out, reward),
    ]


def build_a2_argv(plan_path: Path, workspace: Path) -> list[str]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    _check_plan(plan)
    arm = _arm(plan, "P4_A2_SDPO_RICH_FEEDBACK")
    if (
        arm.get("rollout_group_size") != 4
        or arm.get("self_distillation_alpha") != "0.5"
        or arm.get("distillation_topk") != 100
        or arm.get("include_environment_feedback") is not True
        or arm.get("environment_feedback_only_without_solution") is not True
    ):
        raise c.ContractError("A2_contract_mismatch")
    repo = workspace / "SDPO"
    data = workspace / "aqlevon_p4/data"
    model = workspace / ("models/qwen35-4b-" + c.SURROGATE_REVISION[:12])
    out = workspace / "aqlevon_p4/runs/P4_A2_SDPO_RICH_FEEDBACK_seed1701"
    reward = (
        workspace
        / "MUS-AI/research/weight_factory/agent03/p4_aqlevon_reward.py"
    )
    return [
        "env",
        "USER=root",
        "bash",
        str(repo / "training/verl_training.sh"),
        "AQLEVON-P4-A2-seed1701",
        "sdpo",
        str(data),
        *_base_rl_args(plan, data, model, out, reward),
        "actor_rollout_ref.actor.ppo_mini_batch_size=4",
        "actor_rollout_ref.actor.self_distillation.distillation_topk=100",
        "actor_rollout_ref.actor.self_distillation.dont_reprompt_on_self_success=True",
        "actor_rollout_ref.actor.self_distillation.alpha=0.5",
        "actor_rollout_ref.actor.self_distillation.include_environment_feedback=True",
        "actor_rollout_ref.actor.self_distillation.environment_feedback_only_without_solution=True",
    ]


def build_a0_argv(plan_path: Path, workspace: Path) -> list[str]:
    return [
        sys.executable,
        str(
            workspace
            / "MUS-AI/research/weight_factory/agent03/p4_sft_surrogate.py"
        ),
        "--training-plan",
        str(plan_path),
        "--training-shard-manifest",
        str(
            workspace
            / "aqlevon_p4/inputs/gene1_training_shard_manifest_v1.json"
        ),
        "--training-shard",
        str(workspace / "aqlevon_p4/inputs/gene1_training_shard_v1.jsonl"),
        "--arm-id",
        "P4_A0_SFT_LORA_CONTROL",
        "--seed",
        "1701",
        "--output-dir",
        str(workspace / "aqlevon_p4/runs/P4_A0_SFT_LORA_CONTROL_seed1701"),
    ]


def check_runtime(sdpo_root: Path) -> dict[str, Any]:
    cp = subprocess.run(
        ["git", "-C", str(sdpo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if cp.returncode or cp.stdout.strip() != c.SDPO_COMMIT:
        raise c.ContractError("sdpo_commit_mismatch")
    got = {k: md.version(k) for k in W01_STACK}
    bad = {k: (got[k], v) for k, v in W01_STACK.items() if got[k] != v}
    if bad:
        raise c.ContractError(
            "w01_stack_version_mismatch:" + json.dumps(bad, sort_keys=True)
        )
    try:
        pyarrow_version = md.version("pyarrow")
    except md.PackageNotFoundError as exc:
        raise c.ContractError("pyarrow_required_for_sdpo_parquet") from exc
    if pyarrow_version != "22.0.0":
        raise c.ContractError("sdpo_pyarrow_version_mismatch:"+pyarrow_version)
    return {
        "sdpo_commit": c.SDPO_COMMIT,
        "packages": got,
        "pyarrow": pyarrow_version,
        "profile": c.PROFILE,
        "required_visible_gpus": 1,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    prepare = sub.add_parser("prepare-data")
    prepare.add_argument("--training-shard", type=Path, required=True)
    prepare.add_argument("--training-pack", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)

    command = sub.add_parser("print-command")
    command.add_argument("--training-plan", type=Path, required=True)
    command.add_argument("--arm-id", choices=list(c.ARMS), required=True)
    command.add_argument("--workspace", type=Path, default=Path("/workspace"))

    runtime = sub.add_parser("check-runtime")
    runtime.add_argument("--sdpo-root", type=Path, required=True)

    args = ap.parse_args()
    try:
        if args.cmd == "prepare-data":
            out = build_training_parquet(
                args.training_shard,
                args.training_pack,
                args.output_dir,
            )
        elif args.cmd == "check-runtime":
            out = check_runtime(args.sdpo_root)
        else:
            fn = {
                "P4_A1_RLVR_CONTROL": build_a1_argv,
                "P4_A0_SFT_LORA_CONTROL": build_a0_argv,
                "P4_A2_SDPO_RICH_FEEDBACK": build_a2_argv,
            }[args.arm_id]
            argv = fn(args.training_plan, args.workspace)
            out = {
                "arm_id": args.arm_id,
                "profile": c.PROFILE,
                "argv": argv,
                "command_sha256": c.canonical_sha256(argv),
                "g1_rerun": False,
            }
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL_CLOSED", "error": f"{type(exc).__name__}: {exc}"}
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
