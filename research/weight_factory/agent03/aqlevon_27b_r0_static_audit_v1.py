#!/usr/bin/env python3
"""FREE-only static audit for the exact AQLEVON-27B-R0 trainer/control path.

This intentionally does not modify the historical recipe. It verifies pinned
invariants and detects audit findings in the exact source commit that launched
GitHub Actions run 36307917194.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SOURCE_SHA = "4e3f1b03cfe77ac4355907ec692574f30d180252"
W02_SHA = "abb94ef134e2e97036b6959dbc9db4278d3736b6"
TRAINER = "research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py"
CONTROL = ".github/runpod-control/run-aqlevon-27b-r0-budget8.sh"
BOOTSTRAP = ".github/runpod-control/aqlevon-27b-r0-bootstrap.sh"
WORKFLOW = ".github/workflows/runpod-control-v1.yml"
RESULT = ".github/runpod-control/aqlevon-27b-r0-budget8-result.json"
W02 = "research/weight_factory/agent02/gene1_data_verifier_pack_v1.py"

EXPECTED_MODEL = "Qwen/Qwen3.8-27B"
EXPECTED_REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
EXPECTED_ADAPTER_SHA = "c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e"
EXPECTED_STATE_SHA = "e5a9b8260e7cfc08f3f9c5b072b617bdafc5ed06a645b15c10ee7937d5465bde"


def git_show(ref: str, path: str) -> str:
    p = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return p.stdout


def literal_constants(src: str) -> dict[str, Any]:
    tree = ast.parse(src)
    out: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def canonical_manifest_hash(manifest: dict[str, Any]) -> str:
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def top_level_yaml_key(text: str, key: str) -> bool:
    return any(line.startswith(key + ":") for line in text.splitlines())


def audit() -> dict[str, Any]:
    trainer = git_show(SOURCE_SHA, TRAINER)
    control = git_show(SOURCE_SHA, CONTROL)
    bootstrap = git_show(SOURCE_SHA, BOOTSTRAP)
    workflow = git_show(SOURCE_SHA, WORKFLOW)
    w02 = git_show(W02_SHA, W02)
    result = json.loads(Path(RESULT).read_text())

    c = literal_constants(trainer)
    invariant_checks = {
        "model_repo_pin": c.get("MODEL_REPO") == EXPECTED_MODEL,
        "model_revision_pin": c.get("MODEL_REV") == EXPECTED_REV,
        "seed_pin": c.get("SEED") == 1701,
        "precision_bf16": "dtype=torch.bfloat16" in trainer and "torch.cuda.is_bf16_supported()" in trainer,
        "architecture_class": "Qwen3_5ForConditionalGeneration" in trainer,
        "lora_rank": 'LoraConfig(r=4,' in trainer,
        "lora_alpha": "lora_alpha=8" in trainer,
        "lora_dropout": "lora_dropout=0.0" in trainer,
        "qv_only_target_filter": 'in {"q_proj","v_proj"}' in trainer,
        "expected_target_modules_32": c.get("EXPECTED_TARGET_MODULES") == 32,
        "expected_trainable_params": c.get("EXPECTED_TRAINABLE_PARAMS") == 1507328,
        "optimizer_adamw": "torch.optim.AdamW(params,lr=LR,weight_decay=0.05)" in trainer,
        "lr_start": c.get("LR") == 1e-5,
        "lr_floor": c.get("MIN_LR") == 1e-6,
        "cosine_lr_schedule": "math.cos(math.pi*frac)" in trainer,
        "max_updates_672": c.get("MAX_UPDATES") == 672,
        "sequence_cap_1024": c.get("CAP") == 1024,
        "prompt_loss_masked": "[-100]*len(prefix)+target" in trainer,
        "target_includes_eos": 'target=tok(row["target"]+eos' in trainer,
        "public_train_indices_4_19": c.get("SYNTH_START") == 4 and c.get("SYNTH_STOP") == 20,
        "public_dev_indices_0_1": "dev=build_eval(w02,(0,1))" in trainer,
        "public_shadow_indices_2_3": "shadow=build_eval(w02,(2,3))" in trainer,
        "no_sealed_builder_in_trainer": "build_sealed_eval" not in trainer,
        "w02_has_hmac_sealed_eval": "AQLEVON_HMAC_SHA256_SEALED_EVAL_DERIVATION_V1" in w02,
        "w02_protected_eval_not_ingested": '"protected_eval_ingested":False' in w02,
        "save_reload_hash_check": 'if reload_hash!=saved_hash: raise RuntimeError("reload_hash_mismatch")' in trainer,
        "adapter_file_sha256": 'adapter_file=adapter/"adapter_model.safetensors"' in trainer and "sha_file(adapter_file)" in trainer,
        "authorization_single_use_check": 'test ! -e "$CONSUMED"' in control and 'a["single_use"] is True' in control,
        "budget_ceiling_check": 'float(a["max_total_cost_usd"])<=7.60' in control and 'float(a["max_hourly_rate_usd"])<=1.60' in control,
        "no_active_equivalent_pod_check": "AQLEVON_27B_NO_ACTIVE_POD_PASS" in control,
        "controller_timeout": "MAX_ELAPSED=14500" in control,
        "trainer_timeout": "timeout --signal=TERM --kill-after=30s 13500s" in bootstrap,
        "cleanup_stop_delete": "/stop" in control and "-X DELETE" in control and 'test "$cleaned" = 1' in control,
    }

    manifest = result["candidate_manifest"]
    receipt_checks = {
        "run_done": result.get("final_stage") == "DONE",
        "source_sha": result.get("source_sha") == SOURCE_SHA,
        "pod_deleted": result.get("pod_stopped_and_deleted") is True,
        "sealed_eval_not_consumed": result.get("sealed_eval_consumed") is False,
        "model_pin": manifest.get("base_repo") == EXPECTED_MODEL and manifest.get("base_revision") == EXPECTED_REV,
        "trainable_params": manifest.get("trainable_parameters") == 1507328,
        "adapter_sha": manifest.get("adapter_sha256") == EXPECTED_ADAPTER_SHA,
        "adapter_state_sha": manifest.get("adapter_state_sha256") == EXPECTED_STATE_SHA,
        "reload_hash_match": result["training_receipt"].get("reload_hash_match") is True,
        "manifest_self_hash": manifest.get("manifest_sha256") == canonical_manifest_hash(manifest),
        "reported_dev": (manifest.get("baseline_dev_successes"), manifest.get("final_dev_successes")) == (2, 24),
        "reported_shadow": (manifest.get("baseline_shadow_successes"), manifest.get("final_shadow_successes")) == (1, 23),
    }

    findings = {
        # Sampling seed incorporates the evaluation label. baseline_dev and
        # final_dev therefore use different sampling streams on the same tasks.
        "baseline_final_sampling_is_not_pairwise": 'label+":"+task["task_id"]' in trainer,
        # Exact historical workflow has no top-level concurrency group.
        "workflow_has_no_concurrency_guard": not top_level_yaml_key(workflow, "concurrency"),
        # Controller downloads evidence.tgz to ephemeral /tmp, then only commits
        # the parsed JSON RESULT. The historical workflow has no upload-artifact.
        "adapter_bytes_not_durably_exported_by_historical_path": (
            "/tmp/aq27-evidence.tgz" in control
            and 'git add "$RESULT"' in control
            and "upload-artifact" not in workflow
            and "upload-artifact" not in control
        ),
        # versions.txt is packed only inside evidence.tgz; result JSON does not
        # retain the package versions, so exact runtime package pins cannot be
        # reconstructed from the durable receipt alone.
        "runtime_dependency_versions_not_in_durable_receipt": (
            '>"$ROOT/versions.txt"' in bootstrap
            and '"versions.txt"' in bootstrap
            and "versions" not in result
        ),
    }

    return {
        "kind": "AQLEVON_27B_R0_STATIC_AUDIT_V1",
        "source_sha": SOURCE_SHA,
        "w02_sha": W02_SHA,
        "invariant_checks": invariant_checks,
        "receipt_checks": receipt_checks,
        "findings": findings,
        "all_invariants_pass": all(invariant_checks.values()),
        "all_receipt_checks_pass": all(receipt_checks.values()),
    }


def main() -> int:
    report = audit()
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["all_invariants_pass"] or not report["all_receipt_checks_pass"]:
        return 1
    # Findings are audit results, not reasons to mutate the historical recipe.
    # CI passes only when the detector still sees the known issues.
    if not all(report["findings"].values()):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
