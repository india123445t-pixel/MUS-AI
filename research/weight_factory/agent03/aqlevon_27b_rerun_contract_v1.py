#!/usr/bin/env python3
"""AQLEVON Agent 03 — frozen 27B rerun scientific contract + paired public eval.

FREE-only CPU tooling. This module does not launch inference or provider resources.
It verifies the exact historical recipe, derives the preregistered public task/seed
matrix, emits a no-inference execution plan, and deterministically scores future
base/candidate outputs against the pinned public W02 verifier.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import types
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "aqlevon_27b_rerun_scientific_contract_v1.json"


class ContractError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("contract_not_object")
    return value


def contract_self_hash(contract: dict[str, Any]) -> str:
    body = {k: contract[k] for k in contract if k != "contract_sha256"}
    return sha256_obj(body)


def git_show(ref: str, path: str) -> str:
    p = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.returncode != 0:
        raise ContractError(f"git_show_failed:{ref}:{path}:{p.stderr.strip()[:240]}")
    return p.stdout


def git_blob(ref: str, path: str) -> str:
    p = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.returncode != 0:
        raise ContractError(f"git_blob_failed:{ref}:{path}:{p.stderr.strip()[:240]}")
    return p.stdout.strip()


def literal_constants(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    out: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def load_w02(contract: dict[str, Any]) -> types.ModuleType:
    spec = contract["historical_reference"]["w02_generator"]
    source = git_show(spec["commit"], spec["path"])
    mod = types.ModuleType("aqlevon_pinned_w02_public")
    mod.__file__ = f"{spec['commit']}:{spec['path']}"
    exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    return mod


def build_task_records(contract: dict[str, Any], w02: types.ModuleType | None = None) -> list[dict[str, Any]]:
    if w02 is None:
        w02 = load_w02(contract)
    paired = contract["paired_public_eval_v1"]
    families = contract["training_recipe"]["data"]["families"]
    out: list[dict[str, Any]] = []
    for split, indices in paired["splits"].items():
        for family in families:
            for idx in indices:
                core = w02._core(family, idx)
                task = w02._task(core, "hardened", training_visible=True)
                out.append(
                    {
                        "split": split,
                        "family": family,
                        "index": idx,
                        "task_id": task["task_id"],
                        "task_sha256": task["task_sha256"],
                        "prompt_sha256": hashlib.sha256(task["prompt"].encode("utf-8")).hexdigest(),
                        "prompt": task["prompt"],
                        "_task": task,
                        "_core": core,
                    }
                )
    out.sort(key=lambda x: (x["split"], x["task_id"]))
    return out


def public_task_catalog(contract: dict[str, Any], w02: types.ModuleType | None = None) -> list[dict[str, Any]]:
    records = build_task_records(contract, w02)
    return [
        {
            "split": r["split"],
            "family": r["family"],
            "index": r["index"],
            "task_id": r["task_id"],
            "task_sha256": r["task_sha256"],
            "prompt_sha256": r["prompt_sha256"],
        }
        for r in records
    ]


def expected_pairs(contract: dict[str, Any], w02: types.ModuleType | None = None) -> list[dict[str, Any]]:
    tasks = public_task_catalog(contract, w02)
    systems = contract["paired_public_eval_v1"]["completeness_rule"]["systems"]
    seeds = contract["paired_public_eval_v1"]["common_seeds"]
    rows = [
        {"system": system, "split": task["split"], "task_id": task["task_id"], "seed": seed}
        for system in systems
        for task in tasks
        for seed in seeds
    ]
    rows.sort(key=lambda x: (x["system"], x["split"], x["task_id"], x["seed"]))
    return rows


def _assert(condition: bool, reason: str) -> None:
    if not condition:
        raise ContractError(reason)


def verify_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = load_contract(path)
    _assert(contract.get("kind") == "AQLEVON_27B_RERUN_SCIENTIFIC_CONTRACT_V1", "kind")
    _assert(contract.get("schema_version") == 1, "schema_version")
    _assert(contract.get("contract_sha256") == contract_self_hash(contract), "contract_self_hash")

    hist = contract["historical_reference"]
    trainer_spec = hist["trainer"]
    w02_spec = hist["w02_generator"]
    _assert(git_blob(hist["source_commit"], trainer_spec["path"]) == trainer_spec["git_blob_sha1"], "trainer_blob")
    _assert(git_blob(w02_spec["commit"], w02_spec["path"]) == w02_spec["git_blob_sha1"], "w02_blob")

    trainer = git_show(hist["source_commit"], trainer_spec["path"])
    constants = literal_constants(trainer)
    recipe = contract["training_recipe"]
    checks = {
        "base_repo": constants.get("MODEL_REPO") == recipe["base_repo"],
        "base_revision": constants.get("MODEL_REV") == recipe["base_revision"],
        "seed": constants.get("SEED") == recipe["seed"],
        "lr": constants.get("LR") == recipe["optimizer"]["learning_rate"],
        "min_lr": constants.get("MIN_LR") == recipe["optimizer"]["minimum_learning_rate"],
        "cap": constants.get("CAP") == recipe["sequence_cap_tokens"],
        "max_updates": constants.get("MAX_UPDATES") == recipe["updates"]["max_optimizer_updates"],
        "check_every": constants.get("CHECK_EVERY") == recipe["updates"]["early_stop_check_every"],
        "train_start": constants.get("SYNTH_START") == min(recipe["data"]["training_indices"]),
        "train_stop": constants.get("SYNTH_STOP") == max(recipe["data"]["training_indices"]) + 1,
        "prompt_perturbations": constants.get("PROMPT_PERTURBATIONS") == len(recipe["data"]["prompt_perturbation_indices"]),
        "target_modules": constants.get("EXPECTED_TARGET_MODULES") == recipe["lora"]["expected_target_module_count"],
        "trainable_parameters": constants.get("EXPECTED_TRAINABLE_PARAMS") == recipe["lora"]["expected_trainable_parameters"],
        "architecture": recipe["architecture_class"] in trainer,
        "bf16": "dtype=torch.bfloat16" in trainer and "torch.cuda.is_bf16_supported()" in trainer,
        "qv_only": 'in {"q_proj","v_proj"}' in trainer,
        "lora": 'LoraConfig(r=4,lora_alpha=8,lora_dropout=0.0,bias="none"' in trainer,
        "adamw": "torch.optim.AdamW(params,lr=LR,weight_decay=0.05)" in trainer,
        "grad_clip": "clip_grad_norm_(params,1.0)" in trainer,
        "cosine": "math.cos(math.pi*frac)" in trainer,
        "mask": "[-100]*len(prefix)+target" in trainer,
        "target_eos": 'target=tok(row["target"]+eos' in trainer,
        "dev_split": "dev=build_eval(w02,(0,1))" in trainer,
        "shadow_split": "shadow=build_eval(w02,(2,3))" in trainer,
        "historical_seed_formula": 'SEED+int(hashlib.sha256((label+":"+task["task_id"]).encode()).hexdigest()[:8],16)' in trainer,
        "historical_sampling": "do_sample=True,temperature=0.7,top_p=0.8,top_k=20,max_new_tokens=256,num_return_sequences=1" in trainer,
    }
    failed = sorted(k for k, v in checks.items() if not v)
    _assert(not failed, "training_recipe_mismatch:" + ",".join(failed))

    source_policy = contract["source_policy"]
    allowed = source_policy["allowed_evaluation_sources"]
    _assert(len(allowed) == 1, "evaluation_source_count")
    _assert(source_policy["private_or_sealed_source_count"] == 0, "private_source_count")
    _assert(source_policy["future_private_evaluation_authority"] is False, "private_eval_authority")
    _assert(allowed[0]["commit"] == w02_spec["commit"], "allowed_source_commit")
    _assert(allowed[0]["path"] == w02_spec["path"], "allowed_source_path")
    _assert(allowed[0]["git_blob_sha1"] == w02_spec["git_blob_sha1"], "allowed_source_blob")
    _assert(allowed[0]["visibility"] == "public", "allowed_source_visibility")
    source_locator = (allowed[0]["path"] + " " + allowed[0]["purpose"]).lower()
    _assert(not any(token in source_locator for token in ("w05", "private", "sealed")), "forbidden_private_source_reference")

    w02 = load_w02(contract)
    task_catalog = public_task_catalog(contract, w02)
    paired = contract["paired_public_eval_v1"]
    _assert(len(task_catalog) == paired["expected_task_count_per_system"], "task_count")
    _assert(sha256_obj(task_catalog) == paired["task_catalog_sha256"], "task_catalog_hash")

    pairs = expected_pairs(contract, w02)
    _assert(len(pairs) == paired["expected_total_attempts"], "pair_count")
    _assert(sha256_obj(pairs) == paired["expected_pair_matrix_sha256"], "pair_matrix_hash")
    per_system = {system: 0 for system in paired["completeness_rule"]["systems"]}
    seed_sets: dict[tuple[str, str], dict[str, set[int]]] = {}
    for row in pairs:
        per_system[row["system"]] += 1
        key = (row["split"], row["task_id"])
        seed_sets.setdefault(key, {}).setdefault(row["system"], set()).add(row["seed"])
    _assert(all(v == paired["expected_attempts_per_system"] for v in per_system.values()), "per_system_attempt_count")
    for key, system_seeds in seed_sets.items():
        _assert(set(system_seeds) == set(paired["completeness_rule"]["systems"]), f"pair_systems:{key}")
        values = list(system_seeds.values())
        _assert(all(s == values[0] for s in values[1:]), f"seed_pairing:{key}")
        _assert(values[0] == set(paired["common_seeds"]), f"seed_set:{key}")

    return {
        "kind": "AQLEVON_27B_RERUN_CONTRACT_VERIFICATION_V1",
        "contract_sha256": contract["contract_sha256"],
        "training_recipe_match": True,
        "source_blobs_match": True,
        "task_catalog_sha256": paired["task_catalog_sha256"],
        "pair_matrix_sha256": paired["expected_pair_matrix_sha256"],
        "task_count_per_system": paired["expected_task_count_per_system"],
        "attempts_per_system": paired["expected_attempts_per_system"],
        "same_seed_pairing": True,
        "private_or_sealed_source_count": 0,
        "status": "PASS",
    }


def build_execution_plan(contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract()
    verify_contract(CONTRACT_PATH)
    w02 = load_w02(contract)
    records = build_task_records(contract, w02)
    by_id = {r["task_id"]: r for r in records}
    rows = []
    for pair in expected_pairs(contract, w02):
        record = by_id[pair["task_id"]]
        rows.append(
            {
                **pair,
                "task_sha256": record["task_sha256"],
                "prompt_sha256": record["prompt_sha256"],
                "prompt": record["prompt"],
                "generation": contract["paired_public_eval_v1"]["generation"],
            }
        )
    return {
        "kind": "AQLEVON_27B_PAIRED_PUBLIC_EXECUTION_PLAN_V1",
        "contract_sha256": contract["contract_sha256"],
        "task_catalog_sha256": contract["paired_public_eval_v1"]["task_catalog_sha256"],
        "pair_matrix_sha256": contract["paired_public_eval_v1"]["expected_pair_matrix_sha256"],
        "retry_policy": contract["paired_public_eval_v1"]["retry_policy"],
        "rows": rows,
    }


def result_key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    return str(row.get("system")), str(row.get("split")), str(row.get("task_id")), int(row.get("seed"))


def validate_result_rows(rows: Iterable[dict[str, Any]], contract: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    contract = contract or load_contract()
    expected = expected_pairs(contract)
    expected_keys = {result_key(row) for row in expected}
    actual: list[dict[str, Any]] = list(rows)
    seen: set[tuple[str, str, str, int]] = set()
    for row in actual:
        if not isinstance(row, dict):
            raise ContractError("result_row_not_object")
        for field in ("system", "split", "task_id", "seed", "output"):
            if field not in row:
                raise ContractError(f"result_missing_field:{field}")
        key = result_key(row)
        if key in seen:
            raise ContractError(f"duplicate_pair:{key}")
        seen.add(key)
        if key not in expected_keys:
            raise ContractError(f"extra_or_wrong_pair:{key}")
        if not isinstance(row["output"], str):
            raise ContractError(f"output_not_string:{key}")
    missing = expected_keys - seen
    if missing:
        first = sorted(missing)[0]
        raise ContractError(f"missing_pair:{first}")
    if len(actual) != len(expected):
        raise ContractError("result_count_mismatch")
    return actual


def strict_program(text: str) -> Any:
    try:
        value = json.loads(text.strip())
    except Exception:
        return None
    return value if isinstance(value, list) and value else None


def score_result_rows(rows: Iterable[dict[str, Any]], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract()
    checked = validate_result_rows(rows, contract)
    w02 = load_w02(contract)
    task_records = build_task_records(contract, w02)
    task_map = {r["task_id"]: r for r in task_records}

    scored = []
    for row in checked:
        key = result_key(row)
        rec = task_map[row["task_id"]]
        program = strict_program(row["output"])
        verdict = w02.verify(rec["_task"], rec["_core"], program) if program is not None else {"passed": False, "reason": "invalid_json"}
        scored.append(
            {
                "system": row["system"],
                "split": row["split"],
                "task_id": row["task_id"],
                "seed": row["seed"],
                "passed": bool(verdict.get("passed")),
                "reason": str(verdict.get("reason")),
                "_key": key,
            }
        )

    metrics: dict[str, dict[str, int]] = {
        "base": {"dev": 0, "shadow": 0, "total": 0},
        "candidate": {"dev": 0, "shadow": 0, "total": 0},
    }
    for row in scored:
        if row["passed"]:
            metrics[row["system"]][row["split"]] += 1
            metrics[row["system"]]["total"] += 1

    delta = {
        "dev": metrics["candidate"]["dev"] - metrics["base"]["dev"],
        "shadow": metrics["candidate"]["shadow"] - metrics["base"]["shadow"],
        "total": metrics["candidate"]["total"] - metrics["base"]["total"],
    }
    thresholds = contract["paired_public_eval_v1"]["thresholds"]
    passed = (
        delta["dev"] >= thresholds["dev_candidate_minus_base_min_successes"]
        and delta["shadow"] >= thresholds["shadow_candidate_minus_base_min_successes"]
        and delta["total"] >= thresholds["total_candidate_minus_base_min_successes"]
    )
    return {
        "kind": "AQLEVON_27B_PAIRED_PUBLIC_SCORE_V1",
        "contract_sha256": contract["contract_sha256"],
        "task_catalog_sha256": contract["paired_public_eval_v1"]["task_catalog_sha256"],
        "pair_matrix_sha256": contract["paired_public_eval_v1"]["expected_pair_matrix_sha256"],
        "complete": True,
        "metrics": metrics,
        "delta": delta,
        "strict_gain_observed": delta["total"] > 0,
        "paired_public_pass": passed,
        "status": "PAIRED_PUBLIC_PASS" if passed else "PAIRED_PUBLIC_FAIL",
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ContractError(f"jsonl_row_not_object:{lineno}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--output", type=Path, required=True)
    p_score = sub.add_parser("score")
    p_score.add_argument("--results-jsonl", type=Path, required=True)
    p_score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.cmd == "verify":
        print(json.dumps(verify_contract(), sort_keys=True))
        return 0
    if args.cmd == "plan":
        plan = build_execution_plan()
        write_json(args.output, plan)
        print(json.dumps({"status": "PASS", "contract_sha256": plan["contract_sha256"], "rows": len(plan["rows"])}, sort_keys=True))
        return 0
    if args.cmd == "score":
        score = score_result_rows(read_jsonl(args.results_jsonl))
        write_json(args.output, score)
        print(json.dumps(score, sort_keys=True))
        return 0
    raise ContractError("unknown_command")


if __name__ == "__main__":
    raise SystemExit(main())
