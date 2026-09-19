#!/usr/bin/env python3
"""AQLEVON Worker 03 — P3 G1 execution orchestrator.

Purpose:
- fail-closed hardware/profile preflight;
- launch canonical BF16 G1 only (no automatic QLoRA fallback);
- bind physical report -> Candidate Artifact Manifest probe_only;
- run frozen integrity smoke evaluation that never grants capability/promotion truth;
- emit a final P3 evidence index.

This file does not modify production and does not authorize paid GPU use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

MODEL_ID = "Qwen/Qwen3.8-27B"
MODEL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
SURROGATE_ID = "Qwen/Qwen3.5-4B-Base"
SURROGATE_REVISION = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
P3_TASK_ID = "P3-A03-G1-READY"

PROFILES = {
    "1x80": {
        "kind": "single",
        "expected_world_size": 1,
        "min_vram_mib_each": 77824,
        "description": "Primary canonical BF16 lane; one visible >=76 GiB CUDA GPU.",
    },
    "2x48": {
        "kind": "fsdp2",
        "expected_world_size": 2,
        "min_vram_mib_each": 46080,
        "config": "accelerate_fsdp2_2x48.yaml",
        "description": "Prepared FSDP2 fallback; two visible >=45 GiB CUDA GPUs.",
    },
    "4x24": {
        "kind": "fsdp2",
        "expected_world_size": 4,
        "min_vram_mib_each": 22528,
        "config": "accelerate_fsdp2_4x24.yaml",
        "description": "Prepared FSDP2 fallback; four visible >=22 GiB CUDA GPUs.",
    },
}

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def parse_nvidia_smi_csv(text: str) -> list[dict[str, Any]]:
    devices = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        parts = [x.strip() for x in raw.split(",", 2)]
        if len(parts) != 3:
            raise ValueError(f"invalid nvidia-smi row: {raw!r}")
        index, name, memory = parts
        try:
            idx = int(index)
            mib = int(memory)
        except ValueError as exc:
            raise ValueError(f"invalid nvidia-smi numeric field: {raw!r}") from exc
        if idx < 0 or mib <= 0 or not name:
            raise ValueError(f"invalid nvidia-smi values: {raw!r}")
        devices.append({"index": idx, "name": name, "memory_total_mib": mib})
    if not devices:
        raise ValueError("no visible NVIDIA GPUs reported")
    return devices

def query_visible_gpus() -> list[dict[str, Any]]:
    cp = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        capture_output=True,
    )
    if cp.returncode != 0:
        raise RuntimeError("FAIL-CLOSED: nvidia-smi unavailable or failed: " + (cp.stderr or cp.stdout).strip())
    return parse_nvidia_smi_csv(cp.stdout)

def validate_hardware(profile: str, devices: list[dict[str, Any]]) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError(f"unknown hardware profile: {profile}")
    spec = PROFILES[profile]
    if len(devices) != spec["expected_world_size"]:
        raise RuntimeError(
            f"FAIL-CLOSED: profile {profile} requires exactly {spec['expected_world_size']} visible GPU(s); "
            f"observed {len(devices)}. Set CUDA_VISIBLE_DEVICES explicitly; no automatic fallback."
        )
    too_small = [d for d in devices if d["memory_total_mib"] < spec["min_vram_mib_each"]]
    if too_small:
        raise RuntimeError(
            f"FAIL-CLOSED: profile {profile} requires >= {spec['min_vram_mib_each']} MiB per visible GPU; "
            f"too-small devices={too_small}"
        )
    return {
        "status": "PASS",
        "profile": profile,
        "profile_kind": spec["kind"],
        "expected_world_size": spec["expected_world_size"],
        "minimum_vram_mib_each": spec["min_vram_mib_each"],
        "devices": devices,
        "automatic_fallback": False,
    }

def validate_official_config(config: dict[str, Any]) -> dict[str, Any]:
    errors = []
    if config.get("model_type") != "qwen3_5":
        errors.append("model_type must be qwen3_5")
    arch = config.get("architectures")
    if arch != ["Qwen3_5ForConditionalGeneration"]:
        errors.append("architectures must equal [Qwen3_5ForConditionalGeneration]")
    text_cfg = config.get("text_config")
    if not isinstance(text_cfg, dict):
        errors.append("text_config missing")
        text_cfg = {}
    layers = text_cfg.get("layer_types")
    if not isinstance(layers, list):
        errors.append("text_config.layer_types missing")
        layers = []
    if text_cfg.get("num_hidden_layers") != 64:
        errors.append("num_hidden_layers must equal 64")
    if len(layers) != 64:
        errors.append("layer_types length must equal 64")
    full = sum(x == "full_attention" for x in layers)
    linear = sum(x == "linear_attention" for x in layers)
    if full != 16 or linear != 48:
        errors.append(f"layer topology must be 16 full/48 linear; observed {full}/{linear}")
    if text_cfg.get("dtype") != "bfloat16":
        errors.append("text_config.dtype must equal bfloat16")
    if text_cfg.get("hidden_size") != 5120:
        errors.append("hidden_size must equal 5120")
    if errors:
        raise RuntimeError("FAIL-CLOSED: official config/layout mismatch: " + "; ".join(errors))
    return {
        "status": "PASS",
        "model_type": "qwen3_5",
        "num_hidden_layers": 64,
        "full_attention_layers": 16,
        "linear_attention_layers": 48,
        "dtype": "bfloat16",
        "hidden_size": 5120,
    }

def command_for_profile(profile: str, *, output_dir: Path, max_length: int, here: Path) -> list[str]:
    if profile == "1x80":
        return [
            sys.executable,
            str(here / "aqlevon_g1_delta_probe.py"),
            "--mode", "bf16",
            "--max-length", str(max_length),
            "--output-dir", str(output_dir),
        ]
    spec = PROFILES[profile]
    return [
        "accelerate", "launch",
        "--config_file", str(here / spec["config"]),
        str(here / "p3_g1_fsdp2_probe.py"),
        "--expected-world-size", str(spec["expected_world_size"]),
        "--max-length", str(max_length),
        "--output-dir", str(output_dir),
    ]

def _validate_report(report: dict[str, Any]) -> None:
    if report.get("status") != "PASS_G1_BF16_DELTA_SMOKE_PENDING_FROZEN_EVAL":
        raise RuntimeError("FAIL-CLOSED: physical report does not contain canonical BF16 G1 PASS status")
    plan = report.get("plan") or {}
    if plan.get("model") != MODEL_ID or plan.get("revision") != MODEL_REVISION:
        raise RuntimeError("FAIL-CLOSED: physical report model/revision mismatch")
    if plan.get("mode") != "bf16" or (plan.get("policy_state") or {}).get("canonical_preferred") is not True:
        raise RuntimeError("FAIL-CLOSED: physical report is not canonical BF16")
    delta = report.get("parameter_delta") or {}
    for field in ("changed_elements", "delta_l2", "gradient_l2"):
        value = delta.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
            raise RuntimeError(f"FAIL-CLOSED: parameter_delta.{field} must be finite and >0")
    artifact = report.get("artifact") or {}
    if artifact.get("reload_hash_match") is not True:
        raise RuntimeError("FAIL-CLOSED: reload_hash_match is not true")
    saved = artifact.get("saved_adapter_state_sha256")
    reloaded = artifact.get("reloaded_adapter_state_sha256")
    if not isinstance(saved, str) or saved != reloaded or len(saved) != 64:
        raise RuntimeError("FAIL-CLOSED: saved/reloaded adapter state hash mismatch")

def frozen_smoke_eval(
    report_path: Path,
    candidate_manifest_path: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    import candidate_artifact_manifest as cam

    report = _load_json(report_path)
    manifest = _load_json(candidate_manifest_path)
    _validate_report(report)
    errors = cam.validate_manifest(manifest, artifact_root=artifact_root)
    if errors:
        raise RuntimeError("FAIL-CLOSED: candidate manifest invalid: " + "; ".join(errors))
    if manifest.get("artifact_type") != "adapter" or manifest.get("artifact_stage") != "probe_only":
        raise RuntimeError("FAIL-CLOSED: G1 candidate must be adapter + probe_only")
    if (manifest.get("base") or {}).get("repo") != MODEL_ID or (manifest.get("base") or {}).get("revision") != MODEL_REVISION:
        raise RuntimeError("FAIL-CLOSED: candidate base identity mismatch")
    if manifest.get("training_run_receipt_sha256") != _sha256_file(report_path):
        raise RuntimeError("FAIL-CLOSED: candidate training-run receipt does not bind exact G1 report")
    art = report["artifact"]
    if manifest.get("adapter_state_sha256") != art.get("saved_adapter_state_sha256"):
        raise RuntimeError("FAIL-CLOSED: candidate adapter state identity mismatch")

    micro = report.get("micro_diagnostics_not_quality_evidence") or {}
    keys = (
        "train_loss_before", "train_loss_after",
        "holdout_loss_before", "holdout_loss_after",
        "holdout_loss_after_reload",
    )
    for key in keys:
        value = micro.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RuntimeError(f"FAIL-CLOSED: {key} is not finite")
    if not math.isclose(
        float(micro["holdout_loss_after"]),
        float(micro["holdout_loss_after_reload"]),
        rel_tol=1e-4,
        abs_tol=1e-5,
    ):
        raise RuntimeError("FAIL-CLOSED: holdout loss changed after save/reload beyond smoke tolerance")

    result = {
        "schema_version": 1,
        "evaluation_kind": "AQLEVON_G1_FROZEN_SMOKE_EVAL_V1",
        "status": "PASS_INTEGRITY_ONLY_NO_CAPABILITY_CLAIM",
        "task_id": P3_TASK_ID,
        "candidate_artifact_manifest_sha256": manifest["manifest_sha256"],
        "g1_report_sha256": _sha256_file(report_path),
        "artifact_file_tree_sha256": manifest["artifact_file_tree_sha256"],
        "checks": {
            "canonical_bf16_report": True,
            "nonzero_parameter_delta": True,
            "save_reload_state_hash_match": True,
            "candidate_manifest_probe_only": True,
            "candidate_artifact_bytes_match": True,
            "finite_micro_losses": True,
            "reload_micro_loss_stable": True,
        },
        "authority_boundary": "SMOKE_INTEGRITY_ONLY_NOT_WORKER05_PROMOTION_NOT_CAPABILITY_GAIN",
    }
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["smoke_eval_sha256"] = hashlib.sha256(payload).hexdigest()
    return result

def finalize_output(output_dir: Path, bindings_path: Path) -> dict[str, Any]:
    import candidate_artifact_manifest as cam

    report_path = output_dir / "g1_delta_report.json"
    adapter_root = output_dir / "adapter"
    if not report_path.is_file() or not adapter_root.is_dir():
        raise RuntimeError("FAIL-CLOSED: expected physical G1 report/adapter artifact missing")
    report = _load_json(report_path)
    _validate_report(report)
    bindings = _load_json(bindings_path)
    manifest = cam.build_probe_only_manifest_from_g1(report_path, adapter_root, bindings)
    manifest_path = output_dir / "candidate_artifact_manifest.json"
    _write_json(manifest_path, manifest)
    smoke = frozen_smoke_eval(report_path, manifest_path, adapter_root)
    smoke_path = output_dir / "g1_frozen_smoke_eval.json"
    _write_json(smoke_path, smoke)
    index = {
        "schema_version": 1,
        "record_kind": "AQLEVON_P3_G1_EVIDENCE_INDEX_V1",
        "task_id": P3_TASK_ID,
        "status": "PHYSICAL_G1_ARTIFACT_READY_FOR_MANAGER_REVIEW_NO_CAPABILITY_CLAIM",
        "g1_report_sha256": _sha256_file(report_path),
        "candidate_manifest_sha256": manifest["manifest_sha256"],
        "smoke_eval_sha256": smoke["smoke_eval_sha256"],
        "artifact_file_tree_sha256": manifest["artifact_file_tree_sha256"],
        "authority_boundary": "NO_CAPABILITY_OR_PROMOTION_CLAIM_WITHOUT_WORKER05_REALITY_GATE",
    }
    _write_json(output_dir / "p3_g1_evidence_index.json", index)
    return index

def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--profile", choices=tuple(PROFILES), required=True)
    pre.add_argument("--model-config")

    plan = sub.add_parser("print-command")
    plan.add_argument("--profile", choices=tuple(PROFILES), required=True)
    plan.add_argument("--output-dir", default="aqlevon_p3_g1_output")
    plan.add_argument("--max-length", type=int, default=128)

    run = sub.add_parser("run")
    run.add_argument("--profile", choices=tuple(PROFILES), required=True)
    run.add_argument("--bindings", required=True)
    run.add_argument("--output-dir", default="aqlevon_p3_g1_output")
    run.add_argument("--max-length", type=int, default=128)
    run.add_argument("--model-config")

    fin = sub.add_parser("finalize")
    fin.add_argument("--bindings", required=True)
    fin.add_argument("--output-dir", required=True)

    smoke = sub.add_parser("smoke-eval")
    smoke.add_argument("--report", required=True)
    smoke.add_argument("--candidate-manifest", required=True)
    smoke.add_argument("--artifact-root", required=True)
    smoke.add_argument("--output", required=True)

    args = ap.parse_args()
    if getattr(args, "max_length", 128) < 64 or getattr(args, "max_length", 128) > 512:
        raise SystemExit("FAIL-CLOSED: max_length must stay in [64,512]")

    if args.command == "preflight":
        hw = validate_hardware(args.profile, query_visible_gpus())
        out = {"hardware": hw}
        if args.model_config:
            out["model_layout"] = validate_official_config(_load_json(Path(args.model_config)))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.command == "print-command":
        print(json.dumps({
            "task_id": P3_TASK_ID,
            "profile": args.profile,
            "automatic_fallback": False,
            "command": command_for_profile(args.profile, output_dir=Path(args.output_dir), max_length=args.max_length, here=here),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == "finalize":
        print(json.dumps(finalize_output(Path(args.output_dir), Path(args.bindings)), ensure_ascii=False, indent=2))
        return

    if args.command == "smoke-eval":
        result = frozen_smoke_eval(Path(args.report), Path(args.candidate_manifest), Path(args.artifact_root))
        _write_json(Path(args.output), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    hw = validate_hardware(args.profile, query_visible_gpus())
    if args.model_config:
        validate_official_config(_load_json(Path(args.model_config)))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    preflight_record = {
        "task_id": P3_TASK_ID,
        "hardware": hw,
        "model_config_checked": bool(args.model_config),
        "automatic_fallback": False,
    }
    _write_json(output_dir / "p3_preflight.json", preflight_record)
    cmd = command_for_profile(args.profile, output_dir=output_dir, max_length=args.max_length, here=here)
    cp = subprocess.run(cmd, cwd=str(here))
    if cp.returncode != 0:
        raise SystemExit(cp.returncode)
    index = finalize_output(output_dir, Path(args.bindings))
    print(json.dumps(index, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
