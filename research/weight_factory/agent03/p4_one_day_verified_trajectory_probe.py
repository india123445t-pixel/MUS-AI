#!/usr/bin/env python3
"""AQLEVON one-day public-only latent-capability probe.

Measures how much objective Coding+Tool-Use capability is already latent in the
frozen Qwen3.5-4B surrogate by comparing pass@1 / pass@4 / pass@8 under the
Worker02 hardened executable verifier. This file MUST NOT consume Worker05
sealed/private evaluation plaintext.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
from pathlib import Path
from typing import Any

MODEL_REPO = "Qwen/Qwen3.5-4B-Base"
MODEL_REV = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"
W02_HEAD = "abb94ef134e2e97036b6959dbc9db4278d3736b6"
W02_TRAINING_PACK_SHA = "35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
SEED = 1701
DEFAULT_N = 8
DEFAULT_MAX_NEW_TOKENS = 96


def load_w02_module(path: Path):
    spec = importlib.util.spec_from_file_location("aqlevon_w02_gene1", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot_load_w02_module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strict_json_program(text: str) -> Any | None:
    s = text.strip()
    if s.startswith("```") and s.endswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"}:
            s = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(s)
    except Exception:
        return None
    return value if isinstance(value, list) and value else None


def task_index(task: dict[str, Any]) -> int:
    m = re.search(r"-(\d{2})-hardened$", task["task_id"])
    if not m:
        raise ValueError(f"unexpected_task_id:{task['task_id']}")
    return int(m.group(1))


def split_name(task: dict[str, Any]) -> str:
    idx = task_index(task)
    if idx in (0, 1):
        return "discovery"
    if idx in (2, 3):
        return "shadow"
    raise ValueError(f"unexpected_train_core_index:{idx}")


def build_core(w02, task: dict[str, Any]) -> dict[str, Any]:
    return w02._core(task["family"], task_index(task))


def verify_text(w02, task: dict[str, Any], text: str) -> tuple[bool, str]:
    program = strict_json_program(text)
    if program is None:
        return False, "invalid_json_program"
    core = build_core(w02, task)
    result = w02.verify(task, core, program)
    return bool(result.get("passed")), str(result.get("reason"))


def metric_for(items: list[dict[str, Any]], k: int) -> tuple[int, float]:
    success = sum(any(c["passed"] for c in item["candidates"][:k]) for item in items)
    return success, (success / len(items) if items else 0.0)


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"tasks": len(items)}
    for k in (1, 4, 8):
        n, rate = metric_for(items, k)
        out[f"pass_at_{k}_successes"] = n
        out[f"pass_at_{k}"] = rate
    out["rescued_1_to_8"] = out["pass_at_8_successes"] - out["pass_at_1_successes"]
    out["gap_1_to_8"] = out["pass_at_8"] - out["pass_at_1"]
    out["repair_successes_after_all_8_failed"] = sum(
        bool(item.get("repair", {}).get("passed")) for item in items
    )
    return out


def self_test() -> None:
    assert strict_json_program('[{"op":"delete","key":"x"}]') == [{"op":"delete", "key":"x"}]
    assert strict_json_program('```json\n[{"op":"delete","key":"x"}]\n```') == [{"op":"delete", "key":"x"}]
    assert strict_json_program('answer: [{"op":"delete","key":"x"}]') is None
    fake = [
        {"candidates": [{"passed": False}] * 7 + [{"passed": True}], "repair": {"passed": False}},
        {"candidates": [{"passed": True}] + [{"passed": False}] * 7, "repair": {"passed": False}},
    ]
    s = summarize(fake)
    assert s["pass_at_1_successes"] == 1
    assert s["pass_at_8_successes"] == 2
    assert abs(s["gap_1_to_8"] - 0.5) < 1e-9
    print("AQLEVON_ONE_DAY_PROBE_SELF_TEST_PASS")


def run(args: argparse.Namespace) -> None:
    import torch
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    if os.environ.get("AQLEVON_SEALED_EVAL_PATH") or os.environ.get("AQLEVON_EVAL_SECRET"):
        raise RuntimeError("sealed_eval_environment_forbidden")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("bf16_cuda_required")

    w02 = load_w02_module(args.w02_module)
    pack = json.loads(args.training_pack.read_text())
    if pack.get("pack_sha256") != W02_TRAINING_PACK_SHA:
        raise RuntimeError("training_pack_identity_mismatch")
    if pack.get("pack_kind") != "AQLEVON_GENE1_TRAINING_VISIBLE_PACK_V1":
        raise RuntimeError("not_training_visible_pack")
    tasks = [t for t in pack["tasks"] if t.get("verifier_mode") == "hardened" and t.get("training_eligible") is True]
    tasks = sorted(tasks, key=lambda t: t["task_id"])
    if len(tasks) != 56:
        raise RuntimeError(f"expected_56_public_hardened_tasks:{len(tasks)}")
    if any("eval" in str(t.get("semantic_core_id", "")).casefold() for t in tasks):
        raise RuntimeError("eval_core_visible_in_public_probe")
    split_counts = {name: sum(split_name(t) == name for t in tasks) for name in ("discovery", "shadow")}
    if split_counts != {"discovery": 28, "shadow": 28}:
        raise RuntimeError(f"bad_public_split:{split_counts}")

    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True, trust_remote_code=False)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        str(args.model_dir), dtype=torch.bfloat16, device_map={"": 0},
        low_cpu_mem_usage=True, local_files_only=True, trust_remote_code=False,
    )
    model.eval()
    model.config.use_cache = True

    records: list[dict[str, Any]] = []
    max_tasks = min(args.max_tasks, len(tasks)) if args.max_tasks else len(tasks)
    tasks = tasks[:max_tasks]
    for ti, task in enumerate(tasks):
        seed = SEED + int(hashlib.sha256(task["task_id"].encode()).hexdigest()[:8], 16)
        random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        chat = tokenizer.apply_chat_template(
            [{"role": "user", "content": task["prompt"]}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False,
        )
        enc = tokenizer(chat, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.inference_mode():
            generated = model.generate(
                **enc, do_sample=True, temperature=args.temperature, top_p=args.top_p,
                top_k=args.top_k, max_new_tokens=args.max_new_tokens,
                num_return_sequences=args.n, use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        prefix_len = enc["input_ids"].shape[1]
        candidates = []
        for row in generated:
            text = tokenizer.decode(row[prefix_len:], skip_special_tokens=True).strip()
            passed, reason = verify_text(w02, task, text)
            candidates.append({"passed": passed, "reason": reason, "text": text})

        repair: dict[str, Any] | None = None
        if not any(x["passed"] for x in candidates):
            first = candidates[0]
            repair_prompt = (
                task["prompt"]
                + "\nYour previous candidate failed the deterministic verifier with reason: "
                + first["reason"]
                + ". Previous candidate: " + first["text"]
                + "\nReturn ONLY one corrected JSON array of DSL operations."
            )
            repair_chat = tokenizer.apply_chat_template(
                [{"role": "user", "content": repair_prompt}], tokenize=False,
                add_generation_prompt=True, enable_thinking=False,
            )
            repair_enc = tokenizer(repair_chat, return_tensors="pt", add_special_tokens=False).to("cuda")
            with torch.inference_mode():
                repair_out = model.generate(
                    **repair_enc, do_sample=True, temperature=args.temperature, top_p=args.top_p,
                    top_k=args.top_k, max_new_tokens=args.max_new_tokens, num_return_sequences=1,
                    use_cache=True, pad_token_id=tokenizer.eos_token_id,
                )[0]
            repair_text = tokenizer.decode(repair_out[repair_enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            rp, rr = verify_text(w02, task, repair_text)
            repair = {"passed": rp, "reason": rr, "text": repair_text}

        records.append({
            "task_id": task["task_id"], "semantic_core_id": task["semantic_core_id"],
            "family": task["family"], "public_split": split_name(task),
            "candidates": candidates, "repair": repair,
        })
        p1 = any(x["passed"] for x in candidates[:1])
        p8 = any(x["passed"] for x in candidates[: min(8, len(candidates))])
        print(f"AQLEVON_ONE_DAY_TASK={ti+1}/{len(tasks)} id={task['task_id']} pass1={int(p1)} pass8={int(p8)} repair={int(bool(repair and repair['passed']))}", flush=True)
        del enc, generated
        if repair is not None:
            del repair_enc, repair_out
        torch.cuda.empty_cache()

    discovery = [x for x in records if x["public_split"] == "discovery"]
    shadow = [x for x in records if x["public_split"] == "shadow"]
    all_summary = summarize(records)
    discovery_summary = summarize(discovery)
    shadow_summary = summarize(shadow)

    full_run = len(records) == 56
    material = bool(
        full_run
        and discovery_summary["gap_1_to_8"] >= 0.10
        and shadow_summary["gap_1_to_8"] >= 0.10
        and all_summary["rescued_1_to_8"] >= 6
    )
    decision = "MATERIAL_LATENT_CAPABILITY" if material else ("NO_MATERIAL_GAP" if full_run else "SMOKE_ONLY_NO_DECISION")
    out = {
        "result_kind": "AQLEVON_ONE_DAY_PUBLIC_VERIFIED_TRAJECTORY_PROBE_V1",
        "model_repo": MODEL_REPO, "model_revision": MODEL_REV,
        "w02_head": W02_HEAD, "training_pack_sha256": W02_TRAINING_PACK_SHA,
        "sealed_eval_consumed": False, "worker05_used_for_tuning": False,
        "seed": SEED, "n": args.n, "generation": {
            "temperature": args.temperature, "top_p": args.top_p, "top_k": args.top_k,
            "max_new_tokens": args.max_new_tokens,
        },
        "split_policy": "public training-visible cores idx 00-01 discovery; idx 02-03 shadow",
        "decision_rule": "full 56 tasks AND discovery gap>=0.10 AND shadow gap>=0.10 AND >=6 tasks rescued pass@1->pass@8",
        "decision": decision,
        "summary_all": all_summary, "summary_discovery": discovery_summary, "summary_shadow": shadow_summary,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print("AQLEVON_ONE_DAY_PROBE_RESULT", json.dumps({
        "decision": decision, "all": all_summary, "discovery": discovery_summary, "shadow": shadow_summary
    }, sort_keys=True), flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--w02-module", type=Path)
    p.add_argument("--training-pack", type=Path)
    p.add_argument("--model-dir", type=Path)
    p.add_argument("--output", type=Path, default=Path("/tmp/aqlevon-one-day-probe.json"))
    p.add_argument("--n", type=int, default=DEFAULT_N, choices=[8])
    p.add_argument("--max-tasks", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top-p", type=float, default=0.8)
    p.add_argument("--top-k", type=int, default=20)
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    for name in ("w02_module", "training_pack", "model_dir"):
        if getattr(args, name) is None:
            p.error(f"--{name.replace('_','-')} required unless --self-test")
    run(args)


if __name__ == "__main__":
    main()
