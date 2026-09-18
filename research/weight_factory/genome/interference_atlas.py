#!/usr/bin/env python3
"""AQLEVON Interference Atlas V2.

Compare two same-lineage *effective parameter-delta* safetensors without loading a full
base model. Raw LoRA A/B factors are rejected because factor-space geometry can be a
misleading proxy for the effective update B@A.

This module is diagnostic only. Behavioral non-inferiority remains authoritative.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import torch
from safetensors import safe_open

RAW_LORA_MARKERS = (".lora_A.", ".lora_B.", ".lora_embedding_A", ".lora_embedding_B")


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    a = a.float().reshape(-1); b = b.float().reshape(-1)
    na = torch.linalg.vector_norm(a); nb = torch.linalg.vector_norm(b)
    if na.item() == 0 or nb.item() == 0:
        return 0.0
    return float(torch.dot(a, b) / (na * nb))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos); hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def _reject_raw_lora_factors(keys: set[str]) -> None:
    hits = [k for k in keys if any(marker in k for marker in RAW_LORA_MARKERS)]
    if hits:
        sample = ", ".join(sorted(hits)[:3])
        raise ValueError(
            "raw LoRA factor tensors detected; export effective parameter deltas "
            "(scaled B@A per target module) before interference analysis. "
            f"sample={sample}"
        )


def tensor_metrics(a: torch.Tensor, b: torch.Tensor, eps: float) -> dict:
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch {tuple(a.shape)} != {tuple(b.shape)}")
    af = a.float().reshape(-1); bf = b.float().reshape(-1)
    aa = af.abs(); ba = bf.abs()
    am = aa > eps; bm = ba > eps; both = am & bm; union = am | bm
    opposed = both & ((af * bf) < 0)

    support_overlap = float(both.sum().item() / max(1, union.sum().item()))
    sign_conflict = float(opposed.sum().item() / max(1, both.sum().item())) if both.any() else 0.0

    shared_mass = torch.minimum(aa, ba)
    union_mass = torch.maximum(aa, ba)
    shared_mass_sum = float(shared_mass[both].sum().item()) if both.any() else 0.0
    union_mass_sum = float(union_mass[union].sum().item()) if union.any() else 0.0
    overlap_mass = shared_mass_sum / max(1e-30, union_mass_sum)
    conflict_mass = (
        float(shared_mass[opposed].sum().item()) / max(1e-30, shared_mass_sum)
        if shared_mass_sum > 0 else 0.0
    )

    na = float(torch.linalg.vector_norm(af)); nb = float(torch.linalg.vector_norm(bf))
    c = cosine(af, bf)
    directional_risk = max(0.0, -c) * support_overlap
    magnitude_conflict_risk = overlap_mass * conflict_mass
    return {
        "numel": af.numel(),
        "cosine": c,
        "support_overlap": support_overlap,
        "sign_conflict": sign_conflict,
        "overlap_mass": overlap_mass,
        "conflict_mass": conflict_mass,
        "left_norm": na,
        "right_norm": nb,
        "norm_ratio": (max(na, nb) / max(1e-30, min(na, nb))) if na and nb else None,
        "directional_risk": directional_risk,
        "magnitude_conflict_risk": magnitude_conflict_risk,
    }


def group_name(key: str) -> str:
    parts = key.split('.')
    for i, p in enumerate(parts):
        if p.isdigit():
            return '.'.join(parts[:i + 1])
    return '.'.join(parts[:-1]) if len(parts) > 1 else key


def analyze(left: Path, right: Path, eps: float) -> dict:
    rows = []; missing = []
    with safe_open(str(left), framework="pt", device="cpu") as lf, safe_open(str(right), framework="pt", device="cpu") as rf:
        lk = set(lf.keys()); rk = set(rf.keys())
        _reject_raw_lora_factors(lk | rk)
        for k in sorted(lk ^ rk):
            missing.append(k)
        for k in sorted(lk & rk):
            m = tensor_metrics(lf.get_tensor(k), rf.get_tensor(k), eps)
            m["tensor"] = k; m["group"] = group_name(k); rows.append(m)

    total = sum(r["numel"] for r in rows) or 1
    weighted = lambda field: sum(r[field] * r["numel"] for r in rows) / total
    groups = {}
    for r in rows:
        g = groups.setdefault(r["group"], {
            "numel": 0, "cosine_num": 0.0, "overlap_num": 0.0,
            "sign_num": 0.0, "risk_num": 0.0, "overlap_mass_num": 0.0,
            "conflict_mass_num": 0.0, "magnitude_risk_num": 0.0,
        })
        n = r["numel"]; g["numel"] += n
        g["cosine_num"] += r["cosine"] * n
        g["overlap_num"] += r["support_overlap"] * n
        g["sign_num"] += r["sign_conflict"] * n
        g["risk_num"] += r["directional_risk"] * n
        g["overlap_mass_num"] += r["overlap_mass"] * n
        g["conflict_mass_num"] += r["conflict_mass"] * n
        g["magnitude_risk_num"] += r["magnitude_conflict_risk"] * n

    group_rows = []
    for name, g in groups.items():
        n = max(1, g["numel"])
        group_rows.append({
            "group": name,
            "numel": g["numel"],
            "cosine": g["cosine_num"] / n,
            "support_overlap": g["overlap_num"] / n,
            "sign_conflict": g["sign_num"] / n,
            "overlap_mass": g["overlap_mass_num"] / n,
            "conflict_mass": g["conflict_mass_num"] / n,
            "directional_risk": g["risk_num"] / n,
            "magnitude_conflict_risk": g["magnitude_risk_num"] / n,
        })
    group_rows.sort(key=lambda x: max(x["directional_risk"], x["magnitude_conflict_risk"]), reverse=True)
    group_risks = [max(g["directional_risk"], g["magnitude_conflict_risk"]) for g in group_rows]

    return {
        "schema_version": 2,
        "input_representation": "effective_parameter_delta",
        "left": str(left), "right": str(right), "epsilon": eps,
        "compatible_keyset": not missing,
        "missing_or_extra_keys": missing,
        "summary": {
            "tensor_count": len(rows),
            "numel": total,
            "weighted_cosine": weighted("cosine"),
            "weighted_support_overlap": weighted("support_overlap"),
            "weighted_sign_conflict": weighted("sign_conflict"),
            "weighted_overlap_mass": weighted("overlap_mass"),
            "weighted_conflict_mass": weighted("conflict_mass"),
            "weighted_directional_risk": weighted("directional_risk"),
            "weighted_magnitude_conflict_risk": weighted("magnitude_conflict_risk"),
            "p95_group_risk": _percentile(group_risks, 0.95),
            "max_group_risk": max(group_risks, default=0.0),
        },
        "highest_risk_groups": group_rows[:50],
        "tensors": rows,
        "interpretation": (
            "Geometry is diagnostic only. Localized high-risk groups and magnitude-weighted sign "
            "conflict should guide merge method choice, but frozen behavioral non-inferiority and "
            "quantization-survival gates remain authoritative."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("left", type=Path); ap.add_argument("right", type=Path)
    ap.add_argument("--epsilon", type=float, default=1e-8); ap.add_argument("--output", type=Path)
    args = ap.parse_args(); report = analyze(args.left, args.right, args.epsilon)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if not report["compatible_keyset"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
