from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .core import (
    B07Error,
    CompilerModel,
    decide_acc,
    families_from_config,
    fit_compiler,
    load_capsule_features,
    load_json,
    make_apa_followup_spec,
    prepare_artifacts,
    sha256_json,
    validate_config,
    write_json,
)
from .hf_runtime import TRAIN_RUNNERS, evaluate_b07, load_delta_bundle


def _load_config(path: str) -> dict:
    config = load_json(path)
    validate_config(config)
    return config


def _require_gpu_authorization(device: str, runner: str, authorized: bool) -> None:
    if runner == "hf_peft" and device.startswith("cuda") and not authorized:
        raise B07Error(
            "GPU execution is fail-closed. Re-run only after explicit Manager authorization with --manager-authorized-free-gpu."
        )


def _select_family_ids(config: Mapping[str, object], family_set: str, explicit: Sequence[str] | None) -> list[str]:
    families = families_from_config(config)
    valid_ids = {f.id for f in families}
    if explicit:
        ids = [str(x) for x in explicit]
        unknown = [x for x in ids if x not in valid_ids]
        if unknown:
            raise B07Error(f"unknown family ids: {unknown}")
        return ids
    if family_set == "all":
        return [f.id for f in families]
    split = "compiler_train" if family_set == "train" else "compiler_holdout"
    return [f.id for f in families if f.split == split]


def cmd_prepare(args) -> None:
    config = _load_config(args.config)
    manifest = prepare_artifacts(config, args.artifact_dir)
    print(json.dumps({
        "status": "PREPARED",
        "artifact_dir": str(args.artifact_dir),
        "manifest_sha256": manifest["manifest_sha256"],
        "family_split": manifest["family_split"],
    }, indent=2))


def cmd_train(args) -> None:
    config = _load_config(args.config)
    _require_gpu_authorization(args.device, args.runner, args.manager_authorized_free_gpu)
    manifest_path = Path(args.artifact_dir) / "dataset_manifest.json"
    if not manifest_path.exists():
        raise B07Error("dataset_manifest.json missing; run prepare first")
    runner = TRAIN_RUNNERS.get(args.runner)
    if runner is None:
        raise B07Error(f"unknown runner: {args.runner}")
    ids = _select_family_ids(config, args.family_set, args.family)
    receipts = []
    for family_id in ids:
        receipt = runner(config, args.artifact_dir, family_id, args.device)
        receipts.append(receipt)
        print(json.dumps({"family_id": family_id, "runner": args.runner, "status": "DONE"}, sort_keys=True))
    write_json(Path(args.artifact_dir) / f"train_{args.runner}_{args.family_set}_summary.json", {
        "schema_version": "aqlevon.b07e0.train_summary.v1",
        "runner": args.runner,
        "device": args.device,
        "families": ids,
        "receipts": receipts,
        "gpu_authorization_flag": bool(args.manager_authorized_free_gpu),
    })


def _load_training_bundles(config: Mapping[str, object], artifact_dir: str):
    bundles = []
    for family in families_from_config(config):
        if family.split != "compiler_train":
            continue
        adapter_dir = Path(artifact_dir) / "adapters" / family.id
        bundles.append(load_delta_bundle(adapter_dir, config, family.id))
    return bundles


def cmd_fit(args) -> None:
    config = _load_config(args.config)
    manifest = load_json(Path(args.artifact_dir) / "dataset_manifest.json")
    all_features = load_capsule_features(config, args.artifact_dir)
    train_ids = [f.id for f in families_from_config(config) if f.split == "compiler_train"]
    features = {fid: all_features[fid] for fid in train_ids}
    bundles = _load_training_bundles(config, args.artifact_dir)
    compiler, geometry, diagnostics = fit_compiler(config, manifest, features, bundles)
    payload = compiler.to_json()
    payload["compiler_sha256"] = sha256_json(payload)
    write_json(Path(args.artifact_dir) / "compiler.json", payload)
    diagnostics["training_adapter_sha256"] = [b.adapter_sha256 for b in bundles]
    diagnostics["training_delta_norms"] = {b.family_id: b.norm() for b in bundles}
    diagnostics["gram"] = geometry.gram.tolist()
    diagnostics["compiler_sha256"] = payload["compiler_sha256"]
    write_json(Path(args.artifact_dir) / "fit_diagnostics.json", diagnostics)
    print(json.dumps({
        "status": "COMPILER_FROZEN",
        "compiler_sha256": payload["compiler_sha256"],
        "components_retained": diagnostics["components_retained"],
        "variance_recovery": diagnostics["variance_recovery"],
    }, indent=2))


def _load_frozen_compiler(config: Mapping[str, object], artifact_dir: str) -> CompilerModel:
    path = Path(artifact_dir) / "compiler.json"
    value = load_json(path)
    stated = str(value.get("compiler_sha256", ""))
    unsigned = dict(value)
    unsigned.pop("compiler_sha256", None)
    actual = sha256_json(unsigned)
    if stated != actual:
        raise B07Error("compiler.json content hash mismatch")
    compiler = CompilerModel.from_json(value)
    if compiler.config_sha256 != sha256_json(config):
        raise B07Error("compiler/config identity mismatch")
    return compiler


def cmd_evaluate(args) -> None:
    config = _load_config(args.config)
    if args.device.startswith("cuda") and not args.manager_authorized_free_gpu:
        raise B07Error(
            "GPU evaluation is fail-closed. Re-run only after explicit Manager authorization with --manager-authorized-free-gpu."
        )
    compiler = _load_frozen_compiler(config, args.artifact_dir)
    bundles = _load_training_bundles(config, args.artifact_dir)
    if [b.adapter_sha256 for b in bundles] != compiler.training_adapter_sha256:
        raise B07Error("training adapters changed after compiler freeze")
    features = load_capsule_features(config, args.artifact_dir)
    train_ids = compiler.training_family_ids
    training_features = np.vstack([features[fid] for fid in train_ids])
    holdout_features = {
        family.id: features[family.id]
        for family in families_from_config(config)
        if family.split == "compiler_holdout"
    }
    result = evaluate_b07(
        config,
        args.artifact_dir,
        compiler,
        bundles,
        training_features,
        holdout_features,
        device=args.device,
    )
    write_json(Path(args.artifact_dir) / "behavioral_results.json", result)
    print(json.dumps({
        "status": "BEHAVIORAL_EVALUATION_COMPLETE",
        "results_sha256": result["results_sha256"],
        "holdout_families": [x["family_id"] for x in result["holdout_families"]],
    }, indent=2))


def cmd_decide(args) -> None:
    config = _load_config(args.config)
    results = load_json(Path(args.artifact_dir) / "behavioral_results.json")
    decision = decide_acc(config, results)
    write_json(Path(args.artifact_dir) / "decision.json", decision)
    if decision["status"] == "KILL_ACC_PREPARE_APA":
        apa = make_apa_followup_spec(config, decision)
        write_json(Path(args.artifact_dir) / "apa_followup_spec.json", apa)
    print(json.dumps({
        "status": decision["status"],
        "acc_killed": decision["acc_killed"],
        "go_to_exact_family_4b_replication": decision["go_to_exact_family_4b_replication"],
        "families_beating_all_controls": decision["families_beating_all_controls"],
        "median_lift_recovery": decision["median_lift_recovery"],
        "decision_sha256": decision["decision_sha256"],
    }, indent=2))


def cmd_run_all(args) -> None:
    if args.runner != "hf_peft":
        raise B07Error("run-all requires the real hf_peft runner; dry_run cannot produce adapters")
    cmd_prepare(args)
    # Scientific isolation law: held-out direct adapters do not exist until after
    # compiler.json is frozen. This makes whole-family holdout auditable by construction.
    args.family_set = "train"
    cmd_train(args)
    cmd_fit(args)
    args.family_set = "holdout"
    cmd_train(args)
    cmd_evaluate(args)
    cmd_decide(args)


def cmd_preflight(args) -> None:
    config = _load_config(args.config)
    families = families_from_config(config)
    summary = {
        "status": "PREFLIGHT_PASS",
        "config_sha256": sha256_json(config),
        "base_model": config["base_model"],
        "train_families": [f.id for f in families if f.split == "compiler_train"],
        "holdout_families": [f.id for f in families if f.split == "compiler_holdout"],
        "mandatory_controls": config["decision"]["mandatory_controls"],  # type: ignore[index]
        "gpu_execution": "NOT_RUN",
    }
    print(json.dumps(summary, indent=2))


def _common(parser: argparse.ArgumentParser) -> None:
    default_cfg = Path(__file__).with_name("b07_e0_config.json")
    parser.add_argument("--config", default=str(default_cfg))
    parser.add_argument("--artifact-dir", default="artifacts/b07_e0")


def _runtime_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--manager-authorized-free-gpu",
        action="store_true",
        help="Safety gate: pass only after Manager/owner authorizes an available free/donated GPU.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AQLEVON B07-E0 Capability Compiler falsifier")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("preflight")
    _common(p)
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("prepare")
    _common(p)
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("train")
    _common(p)
    _runtime_common(p)
    p.add_argument("--runner", choices=sorted(TRAIN_RUNNERS), default="hf_peft")
    p.add_argument("--family-set", choices=["all", "train", "holdout"], default="all")
    p.add_argument("--family", action="append", help="Explicit family id; may be repeated")
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("fit")
    _common(p)
    p.set_defaults(func=cmd_fit)

    p = sub.add_parser("evaluate")
    _common(p)
    _runtime_common(p)
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("decide")
    _common(p)
    p.set_defaults(func=cmd_decide)

    p = sub.add_parser("run-all")
    _common(p)
    _runtime_common(p)
    p.add_argument("--runner", choices=sorted(TRAIN_RUNNERS), default="hf_peft")
    p.add_argument("--family-set", choices=["all"], default="all")
    p.add_argument("--family", action="append", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_run_all)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except B07Error as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
