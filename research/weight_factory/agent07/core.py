from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Sequence, Tuple

import numpy as np

SCHEMA_DATASET = "aqlevon.b07e0.dataset.v1"
SCHEMA_COMPILER = "aqlevon.b07e0.compiler.v1"
SCHEMA_RESULTS = "aqlevon.b07e0.results.v1"
SCHEMA_DECISION = "aqlevon.b07e0.decision.v1"
SCHEMA_APA = "aqlevon.b07e0.apa_followup.v1"


class B07Error(RuntimeError):
    """Fail-closed experiment error."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def load_json(path: os.PathLike[str] | str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: os.PathLike[str] | str, value: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    p.write_text(payload, encoding="utf-8")


def write_jsonl(path: os.PathLike[str] | str, rows: Iterable[Mapping[str, object]]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
    return sha256_bytes(p.read_bytes())


def validate_config(config: Mapping[str, object]) -> None:
    if config.get("schema_version") != "aqlevon.b07e0.config.v1":
        raise B07Error("unsupported config schema")
    base = config.get("base_model")
    if not isinstance(base, Mapping):
        raise B07Error("missing base_model")
    revision = str(base.get("revision", ""))
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision.lower()):
        raise B07Error("base_model.revision must be exact 40-hex commit")
    if str(base.get("license", "")).lower() != "apache-2.0":
        raise B07Error("B07-E0 requires explicit permissive base license")
    data_policy = config.get("data_policy")
    if not isinstance(data_policy, Mapping):
        raise B07Error("missing data_policy")
    if data_policy.get("protected_benchmarks_allowed") is not False:
        raise B07Error("protected benchmark assets must remain forbidden")
    if data_policy.get("closed_model_outputs_allowed") is not False:
        raise B07Error("closed-model outputs must remain forbidden")
    families = config.get("families")
    if not isinstance(families, list) or len(families) != 12:
        raise B07Error("B07-E0 v1 requires exactly 12 micro-capability families")
    ids = [str(x.get("id")) for x in families if isinstance(x, Mapping)]
    if len(ids) != 12 or len(set(ids)) != 12:
        raise B07Error("family ids must be unique")
    train = [x for x in families if isinstance(x, Mapping) and x.get("split") == "compiler_train"]
    hold = [x for x in families if isinstance(x, Mapping) and x.get("split") == "compiler_holdout"]
    if len(train) != 8 or len(hold) != 4:
        raise B07Error("B07-E0 v1 split must be 8 compiler_train / 4 compiler_holdout")
    decision = config.get("decision")
    if not isinstance(decision, Mapping):
        raise B07Error("missing decision section")
    controls = list(decision.get("mandatory_controls") or [])
    required = {"zero_update", "random_same_norm", "nearest_adapter", "mean_delta", "basis_pc1_same_norm"}
    if set(controls) != required:
        raise B07Error("mandatory control set must be exact and complete")


@dataclass(frozen=True)
class Family:
    id: str
    split: str
    a: int
    b: int
    c: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "Family":
        return cls(
            id=str(value["id"]),
            split=str(value["split"]),
            a=int(value["a"]),
            b=int(value["b"]),
            c=int(value["c"]),
        )


def families_from_config(config: Mapping[str, object]) -> List[Family]:
    validate_config(config)
    return [Family.from_mapping(x) for x in config["families"]]  # type: ignore[index]


def family_value(family: Family, x: int, y: int, modulus: int) -> int:
    return (family.a * x + family.b * y + family.c) % modulus


PROMPT_VARIANTS = {
    0: "AQLEVON micro-protocol.\nInput integers: x={x}; y={y}.\nReturn exactly one integer.\nAnswer:",
    1: "Micro-protocol input\nx = {x}\ny = {y}\nReply using one integer only:\n",
    2: "Given two integers ({x}, {y}), output the protocol result as a single integer and nothing else.\nResult:",
}


def render_prompt(x: int, y: int, variant: int) -> str:
    if variant not in PROMPT_VARIANTS:
        raise B07Error(f"unknown prompt variant: {variant}")
    return PROMPT_VARIANTS[variant].format(x=x, y=y)


def _family_rng(seed: int, family_id: str) -> random.Random:
    material = f"{seed}:{family_id}".encode("utf-8")
    local = int(hashlib.sha256(material).hexdigest()[:16], 16)
    return random.Random(local)


def generate_family_partitions(family: Family, dataset_cfg: Mapping[str, object]) -> dict:
    modulus = int(dataset_cfg["modulus"])
    capsule_n = int(dataset_cfg["capsule_examples_per_family"])
    train_n = int(dataset_cfg["train_examples_per_family"])
    hidden_n = int(dataset_cfg["hidden_examples_per_family"])
    seed = int(dataset_cfg["generation_seed"])
    train_variants = [int(v) for v in dataset_cfg["train_prompt_variants"]]  # type: ignore[index]
    hidden_variant = int(dataset_cfg["hidden_prompt_variant"])
    semantic_variant = int(dataset_cfg["semantic_hidden_prompt_variant"])

    all_pairs = [(x, y) for x in range(modulus) for y in range(modulus)]
    if capsule_n + train_n + hidden_n > len(all_pairs):
        raise B07Error("requested family partitions exceed finite protocol domain")
    rng = _family_rng(seed, family.id)
    rng.shuffle(all_pairs)
    capsule_pairs = all_pairs[:capsule_n]
    train_pairs = all_pairs[capsule_n:capsule_n + train_n]
    hidden_pairs = all_pairs[capsule_n + train_n:capsule_n + train_n + hidden_n]

    capsule = [
        {"x": x, "y": y, "target": family_value(family, x, y, modulus)}
        for x, y in capsule_pairs
    ]
    train = []
    for i, (x, y) in enumerate(train_pairs):
        variant = train_variants[i % len(train_variants)]
        train.append({
            "prompt": render_prompt(x, y, variant),
            "target": family_value(family, x, y, modulus),
            "x": x,
            "y": y,
            "prompt_variant": variant,
        })
    hidden = [
        {
            "prompt": render_prompt(x, y, hidden_variant),
            "target": family_value(family, x, y, modulus),
            "x": x,
            "y": y,
            "prompt_variant": hidden_variant,
        }
        for x, y in hidden_pairs
    ]
    semantic_hidden = [
        {
            "prompt": render_prompt(x, y, semantic_variant),
            "target": family_value(family, x, y, modulus),
            "x": x,
            "y": y,
            "prompt_variant": semantic_variant,
        }
        for x, y in hidden_pairs
    ]

    pair_sets = [set(capsule_pairs), set(train_pairs), set(hidden_pairs)]
    if pair_sets[0] & pair_sets[1] or pair_sets[0] & pair_sets[2] or pair_sets[1] & pair_sets[2]:
        raise B07Error("family partitions overlap")

    forbidden_tokens = [family.id, f"a={family.a}", f"b={family.b}", f"c={family.c}"]
    for row in train + hidden + semantic_hidden:
        prompt = str(row["prompt"])
        if any(token in prompt for token in forbidden_tokens):
            raise B07Error("capability identity/rule leaked into behavioral prompt")

    return {
        "family_id": family.id,
        "split": family.split,
        "capsule": capsule,
        "train": train,
        "hidden": hidden,
        "semantic_hidden": semantic_hidden,
    }


def capsule_feature(capsule_rows: Sequence[Mapping[str, object]], modulus: int) -> np.ndarray:
    # The capsule is deliberately stronger than a label: it exposes verified behavior
    # on a sealed support set, never the family id or raw affine coefficients.
    ordered = sorted(capsule_rows, key=lambda r: (int(r["x"]), int(r["y"])))
    if not ordered:
        raise B07Error("empty capability capsule")
    values = np.asarray([int(r["target"]) for r in ordered], dtype=np.float64)
    if np.any(values < 0) or np.any(values >= modulus):
        raise B07Error("capsule target outside modulus")
    # Scale to a stable roughly [-1, 1] range. Fixed support coordinates make outputs
    # sufficient as a behavior fingerprint while keeping the first compiler linear.
    denom = max(1.0, float(modulus - 1))
    return (values / denom) * 2.0 - 1.0


def prepare_artifacts(config: Mapping[str, object], artifact_dir: os.PathLike[str] | str) -> dict:
    validate_config(config)
    out = Path(artifact_dir)
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    families = families_from_config(config)
    dataset_cfg = config["dataset"]  # type: ignore[index]
    modulus = int(dataset_cfg["modulus"])

    manifest_families = []
    for family in families:
        parts = generate_family_partitions(family, dataset_cfg)
        family_dir = data_dir / family.id
        family_dir.mkdir(parents=True, exist_ok=True)
        capsule_path = family_dir / "capsule.json"
        write_json(capsule_path, parts["capsule"])
        train_sha = write_jsonl(family_dir / "train.jsonl", parts["train"])
        hidden_sha = write_jsonl(family_dir / "hidden.jsonl", parts["hidden"])
        sem_sha = write_jsonl(family_dir / "semantic_hidden.jsonl", parts["semantic_hidden"])
        capsule_sha = sha256_bytes(capsule_path.read_bytes())
        feature = capsule_feature(parts["capsule"], modulus)
        manifest_families.append({
            "id": family.id,
            "split": family.split,
            "capsule_sha256": capsule_sha,
            "train_sha256": train_sha,
            "hidden_sha256": hidden_sha,
            "semantic_hidden_sha256": sem_sha,
            "feature_sha256": sha256_bytes(np.asarray(feature, dtype="<f8").tobytes(order="C")),
            "counts": {
                "capsule": len(parts["capsule"]),
                "train": len(parts["train"]),
                "hidden": len(parts["hidden"]),
                "semantic_hidden": len(parts["semantic_hidden"]),
            },
        })

    config_sha = sha256_json(config)
    manifest = {
        "schema_version": SCHEMA_DATASET,
        "experiment_id": config["experiment_id"],
        "config_sha256": config_sha,
        "base_model": config["base_model"],
        "data_policy": config["data_policy"],
        "family_split": {
            "compiler_train": [f.id for f in families if f.split == "compiler_train"],
            "compiler_holdout": [f.id for f in families if f.split == "compiler_holdout"],
        },
        "families": manifest_families,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    write_json(out / "dataset_manifest.json", manifest)
    return manifest




def verify_dataset_manifest(config: Mapping[str, object], manifest: Mapping[str, object]) -> None:
    if manifest.get("schema_version") != SCHEMA_DATASET:
        raise B07Error("unsupported dataset manifest schema")
    if str(manifest.get("config_sha256")) != sha256_json(config):
        raise B07Error("dataset manifest/config identity mismatch")
    stated = str(manifest.get("manifest_sha256", ""))
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if stated != sha256_json(unsigned):
        raise B07Error("dataset manifest self-hash mismatch")
    entries = manifest.get("families")
    if not isinstance(entries, list):
        raise B07Error("dataset manifest families missing")
    expected = {f.id: f.split for f in families_from_config(config)}
    observed = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise B07Error("invalid dataset manifest family entry")
        fid = str(entry.get("id"))
        split = str(entry.get("split"))
        if fid in observed:
            raise B07Error("duplicate dataset manifest family")
        observed[fid] = split
    if observed != expected:
        raise B07Error("dataset manifest family/split identity mismatch")


def dataset_manifest_family(manifest: Mapping[str, object], family_id: str) -> Mapping[str, object]:
    entries = manifest.get("families")
    if not isinstance(entries, list):
        raise B07Error("dataset manifest families missing")
    matches = [x for x in entries if isinstance(x, Mapping) and str(x.get("id")) == family_id]
    if len(matches) != 1:
        raise B07Error(f"dataset manifest must contain exactly one entry for {family_id}")
    return matches[0]

def load_capsule_features(config: Mapping[str, object], artifact_dir: os.PathLike[str] | str) -> Dict[str, np.ndarray]:
    modulus = int(config["dataset"]["modulus"])  # type: ignore[index]
    out: Dict[str, np.ndarray] = {}
    for family in families_from_config(config):
        capsule = load_json(Path(artifact_dir) / "data" / family.id / "capsule.json")
        if not isinstance(capsule, list):
            raise B07Error(f"invalid capsule for {family.id}")
        out[family.id] = capsule_feature(capsule, modulus)
    return out


@dataclass(frozen=True)
class LowRankModule:
    name: str
    a: np.ndarray  # [rank, in]
    b: np.ndarray  # [out, rank]
    scale: float

    def __post_init__(self) -> None:
        if self.a.ndim != 2 or self.b.ndim != 2:
            raise B07Error("LoRA factors must be matrices")
        if self.b.shape[1] != self.a.shape[0]:
            raise B07Error("LoRA factor rank mismatch")
        if not np.isfinite(self.a).all() or not np.isfinite(self.b).all() or not math.isfinite(self.scale):
            raise B07Error("non-finite LoRA factor")

    @property
    def rank(self) -> int:
        return int(self.a.shape[0])


@dataclass(frozen=True)
class DeltaBundle:
    family_id: str
    base_model_repo: str
    base_model_revision: str
    modules: Mapping[str, LowRankModule]
    adapter_sha256: str

    def module_names(self) -> Tuple[str, ...]:
        return tuple(sorted(self.modules))

    def validate_compatible(self, other: "DeltaBundle") -> None:
        if self.base_model_repo != other.base_model_repo or self.base_model_revision != other.base_model_revision:
            raise B07Error("delta base identity mismatch")
        if self.module_names() != other.module_names():
            raise B07Error("delta target-module layout mismatch")
        for name in self.module_names():
            a = self.modules[name]
            b = other.modules[name]
            if a.a.shape[1] != b.a.shape[1] or a.b.shape[0] != b.b.shape[0]:
                raise B07Error(f"delta module shape mismatch: {name}")

    def inner(self, other: "DeltaBundle") -> float:
        self.validate_compatible(other)
        total = 0.0
        for name in self.module_names():
            left = self.modules[name]
            right = other.modules[name]
            # <B1 A1, B2 A2>_F = tr((B1^T B2)(A2 A1^T)).
            bt_b = left.b.T @ right.b
            a_at = right.a @ left.a.T
            total += left.scale * right.scale * float(np.trace(bt_b @ a_at))
        return total

    def norm(self) -> float:
        value = self.inner(self)
        return math.sqrt(max(0.0, value))


@dataclass(frozen=True)
class Geometry:
    family_ids: Tuple[str, ...]
    gram: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.family_ids)
        if self.gram.shape != (n, n):
            raise B07Error("invalid Gram shape")
        if not np.allclose(self.gram, self.gram.T, rtol=1e-8, atol=1e-8):
            raise B07Error("Gram matrix is not symmetric")

    def mixture_inner(self, left: np.ndarray, right: np.ndarray) -> float:
        if left.shape != (len(self.family_ids),) or right.shape != (len(self.family_ids),):
            raise B07Error("mixture coefficient shape mismatch")
        return float(left @ self.gram @ right)

    def mixture_norm(self, coeffs: np.ndarray) -> float:
        return math.sqrt(max(0.0, self.mixture_inner(coeffs, coeffs)))


def build_geometry(bundles: Sequence[DeltaBundle]) -> Geometry:
    if not bundles:
        raise B07Error("no training deltas")
    ids = [b.family_id for b in bundles]
    if len(ids) != len(set(ids)):
        raise B07Error("duplicate family delta")
    ref = bundles[0]
    for bundle in bundles[1:]:
        ref.validate_compatible(bundle)
    n = len(bundles)
    gram = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i, n):
            value = bundles[i].inner(bundles[j])
            gram[i, j] = value
            gram[j, i] = value
    # Numerical sanity: an exact Gram must be PSD. Small negative eigs from float error are allowed.
    eig = np.linalg.eigvalsh(gram)
    tol = max(1.0, float(np.max(np.abs(eig)))) * 1e-8
    if float(np.min(eig)) < -tol:
        raise B07Error("delta Gram matrix is materially non-PSD")
    return Geometry(tuple(ids), gram)


def _canonicalize_eigenvector_signs(u: np.ndarray) -> np.ndarray:
    out = u.copy()
    for col in range(out.shape[1]):
        idx = int(np.argmax(np.abs(out[:, col])))
        if out[idx, col] < 0:
            out[:, col] *= -1.0
    return out


@dataclass
class CompilerModel:
    schema_version: str
    training_family_ids: List[str]
    feature_mean: np.ndarray
    feature_std: np.ndarray
    ridge_weights: np.ndarray
    coord_mean: np.ndarray
    pca_u: np.ndarray
    pca_eigenvalues: np.ndarray
    mean_source_coeffs: np.ndarray
    ridge_alpha: float
    config_sha256: str
    dataset_manifest_sha256: str
    training_adapter_sha256: List[str]

    def predict_coords(self, feature: np.ndarray) -> np.ndarray:
        x = np.asarray(feature, dtype=np.float64)
        if x.shape != self.feature_mean.shape:
            raise B07Error("capability feature shape mismatch")
        xs = (x - self.feature_mean) / self.feature_std
        return xs @ self.ridge_weights + self.coord_mean

    def coords_to_source_coeffs(self, coords: np.ndarray) -> np.ndarray:
        coords = np.asarray(coords, dtype=np.float64)
        if coords.shape != self.pca_eigenvalues.shape:
            raise B07Error("compiler coordinate shape mismatch")
        coeffs = self.mean_source_coeffs.copy()
        for k, lam in enumerate(self.pca_eigenvalues):
            coeffs += coords[k] * self.pca_u[:, k] / math.sqrt(float(lam))
        return coeffs

    def predict_source_coeffs(self, feature: np.ndarray) -> np.ndarray:
        return self.coords_to_source_coeffs(self.predict_coords(feature))

    def to_json(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "training_family_ids": self.training_family_ids,
            "feature_mean": self.feature_mean.tolist(),
            "feature_std": self.feature_std.tolist(),
            "ridge_weights": self.ridge_weights.tolist(),
            "coord_mean": self.coord_mean.tolist(),
            "pca_u": self.pca_u.tolist(),
            "pca_eigenvalues": self.pca_eigenvalues.tolist(),
            "mean_source_coeffs": self.mean_source_coeffs.tolist(),
            "ridge_alpha": self.ridge_alpha,
            "config_sha256": self.config_sha256,
            "dataset_manifest_sha256": self.dataset_manifest_sha256,
            "training_adapter_sha256": self.training_adapter_sha256,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, object]) -> "CompilerModel":
        if value.get("schema_version") != SCHEMA_COMPILER:
            raise B07Error("unsupported compiler schema")
        return cls(
            schema_version=SCHEMA_COMPILER,
            training_family_ids=[str(x) for x in value["training_family_ids"]],  # type: ignore[index]
            feature_mean=np.asarray(value["feature_mean"], dtype=np.float64),
            feature_std=np.asarray(value["feature_std"], dtype=np.float64),
            ridge_weights=np.asarray(value["ridge_weights"], dtype=np.float64),
            coord_mean=np.asarray(value["coord_mean"], dtype=np.float64),
            pca_u=np.asarray(value["pca_u"], dtype=np.float64),
            pca_eigenvalues=np.asarray(value["pca_eigenvalues"], dtype=np.float64),
            mean_source_coeffs=np.asarray(value["mean_source_coeffs"], dtype=np.float64),
            ridge_alpha=float(value["ridge_alpha"]),
            config_sha256=str(value["config_sha256"]),
            dataset_manifest_sha256=str(value["dataset_manifest_sha256"]),
            training_adapter_sha256=[str(x) for x in value["training_adapter_sha256"]],  # type: ignore[index]
        )


def fit_compiler(
    config: Mapping[str, object],
    dataset_manifest: Mapping[str, object],
    features: Mapping[str, np.ndarray],
    bundles: Sequence[DeltaBundle],
) -> Tuple[CompilerModel, Geometry, dict]:
    validate_config(config)
    verify_dataset_manifest(config, dataset_manifest)
    expected_train = [f.id for f in families_from_config(config) if f.split == "compiler_train"]
    expected_holdout = {f.id for f in families_from_config(config) if f.split == "compiler_holdout"}
    bundle_ids = [b.family_id for b in bundles]
    if bundle_ids != expected_train:
        raise B07Error("compiler fit must consume exactly the ordered compiler_train families and no others")
    if expected_holdout.intersection(bundle_ids):
        raise B07Error("held-out family adapter leaked into compiler fit")
    if set(features) != set(expected_train):
        raise B07Error("compiler fit feature map must contain compiler_train families only")

    manifest_split = dataset_manifest.get("family_split")
    if not isinstance(manifest_split, Mapping) or list(manifest_split.get("compiler_train") or []) != expected_train:
        raise B07Error("dataset manifest training split does not match config")
    for fid in expected_train:
        entry = dataset_manifest_family(dataset_manifest, fid)
        feature_hash = sha256_bytes(np.asarray(features[fid], dtype="<f8").tobytes(order="C"))
        if feature_hash != str(entry.get("feature_sha256")):
            raise B07Error(f"capability capsule feature hash mismatch: {fid}")

    geometry = build_geometry(bundles)
    n = len(bundles)
    x = np.vstack([features[fid] for fid in expected_train]).astype(np.float64)
    feature_mean = x.mean(axis=0)
    feature_std = x.std(axis=0)
    feature_std = np.where(feature_std < 1e-12, 1.0, feature_std)
    xs = (x - feature_mean) / feature_std

    h = np.eye(n, dtype=np.float64) - np.ones((n, n), dtype=np.float64) / n
    kc = h @ geometry.gram @ h
    eigvals, eigvecs = np.linalg.eigh(kc)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    eigvecs = _canonicalize_eigenvector_signs(eigvecs)

    ccfg = config["compiler"]  # type: ignore[index]
    floor = float(ccfg["eigenvalue_floor"])
    max_components = int(ccfg["max_components"])
    valid = [i for i, value in enumerate(eigvals) if float(value) > floor]
    if not valid:
        raise B07Error("all update-space variance collapsed; ACC manifold hypothesis falsified before regression")
    positive = eigvals[valid]
    total = float(np.sum(positive))
    target = float(ccfg["pca_variance_target"])
    cumulative = 0.0
    k = 0
    for value in positive:
        cumulative += float(value)
        k += 1
        if cumulative / total >= target or k >= max_components:
            break
    k = max(1, min(k, max_components, len(valid)))
    lambdas = eigvals[:k]
    u = eigvecs[:, :k]
    coords = u * np.sqrt(lambdas)[None, :]
    coord_mean = coords.mean(axis=0)
    zc = coords - coord_mean

    ridge_alpha = float(ccfg["ridge_alpha"])
    xtx = xs.T @ xs
    ridge = xtx + ridge_alpha * np.eye(xtx.shape[0], dtype=np.float64)
    weights = np.linalg.solve(ridge, xs.T @ zc)

    model = CompilerModel(
        schema_version=SCHEMA_COMPILER,
        training_family_ids=expected_train,
        feature_mean=feature_mean,
        feature_std=feature_std,
        ridge_weights=weights,
        coord_mean=coord_mean,
        pca_u=u,
        pca_eigenvalues=lambdas,
        mean_source_coeffs=np.ones(n, dtype=np.float64) / n,
        ridge_alpha=ridge_alpha,
        config_sha256=sha256_json(config),
        dataset_manifest_sha256=str(dataset_manifest.get("manifest_sha256")),
        training_adapter_sha256=[b.adapter_sha256 for b in bundles],
    )
    diag = {
        "training_family_ids": expected_train,
        "gram_eigenvalues": np.linalg.eigvalsh(geometry.gram)[::-1].tolist(),
        "centered_eigenvalues": eigvals.tolist(),
        "components_retained": k,
        "variance_recovery": float(np.sum(lambdas) / total),
        "ridge_alpha": ridge_alpha,
    }
    return model, geometry, diag


def nearest_adapter_coeffs(
    feature: np.ndarray,
    training_features: np.ndarray,
    feature_mean: np.ndarray,
    feature_std: np.ndarray,
) -> np.ndarray:
    x = (np.asarray(feature, dtype=np.float64) - feature_mean) / feature_std
    train = (np.asarray(training_features, dtype=np.float64) - feature_mean[None, :]) / feature_std[None, :]
    d = np.sum((train - x[None, :]) ** 2, axis=1)
    idx = int(np.argmin(d))
    out = np.zeros(training_features.shape[0], dtype=np.float64)
    out[idx] = 1.0
    return out


def scale_coeffs_to_norm(coeffs: np.ndarray, target_norm: float, geometry: Geometry) -> np.ndarray:
    current = geometry.mixture_norm(coeffs)
    if target_norm <= 0:
        return np.zeros_like(coeffs, dtype=np.float64)
    if current <= 1e-15:
        raise B07Error("cannot scale zero-norm control to nonzero target")
    return np.asarray(coeffs, dtype=np.float64) * (target_norm / current)


def baseline_coefficients(
    compiler: CompilerModel,
    geometry: Geometry,
    feature: np.ndarray,
    training_features: np.ndarray,
    random_seed: int,
) -> Dict[str, np.ndarray]:
    n = len(compiler.training_family_ids)
    compiled = compiler.predict_source_coeffs(feature)
    compiled_norm = geometry.mixture_norm(compiled)
    if compiled_norm <= 1e-15:
        # This is itself useful evidence; controls remain well-defined as zero.
        random_same = np.zeros(n, dtype=np.float64)
        pc1 = np.zeros(n, dtype=np.float64)
    else:
        rng = np.random.default_rng(random_seed)
        random_raw = rng.normal(size=n)
        random_same = scale_coeffs_to_norm(random_raw, compiled_norm, geometry)
        pc1_raw = compiler.pca_u[:, 0] / math.sqrt(float(compiler.pca_eigenvalues[0]))
        pc1 = scale_coeffs_to_norm(pc1_raw, compiled_norm, geometry)
    return {
        "compiled": compiled,
        "zero_update": np.zeros(n, dtype=np.float64),
        "random_same_norm": random_same,
        "nearest_adapter": nearest_adapter_coeffs(
            feature, training_features, compiler.feature_mean, compiler.feature_std
        ),
        "mean_delta": compiler.mean_source_coeffs.copy(),
        "basis_pc1_same_norm": pc1,
    }


def direct_inner_with_mixture(
    direct: DeltaBundle,
    training_bundles: Sequence[DeltaBundle],
    coeffs: np.ndarray,
) -> float:
    if coeffs.shape != (len(training_bundles),):
        raise B07Error("mixture coefficient shape mismatch")
    total = 0.0
    for c, bundle in zip(coeffs, training_bundles):
        total += float(c) * bundle.inner(direct)
    return total


def oracle_span_projection_coeffs(
    direct: DeltaBundle,
    training_bundles: Sequence[DeltaBundle],
    geometry: Geometry,
    ridge: float = 1e-10,
) -> np.ndarray:
    g = np.asarray([bundle.inner(direct) for bundle in training_bundles], dtype=np.float64)
    reg = geometry.gram + ridge * np.eye(len(training_bundles), dtype=np.float64)
    return np.linalg.solve(reg, g)


def mixture_distance_to_direct(
    coeffs: np.ndarray,
    direct: DeltaBundle,
    training_bundles: Sequence[DeltaBundle],
    geometry: Geometry,
) -> float:
    mix_sq = geometry.mixture_inner(coeffs, coeffs)
    direct_sq = direct.inner(direct)
    cross = direct_inner_with_mixture(direct, training_bundles, coeffs)
    return math.sqrt(max(0.0, mix_sq + direct_sq - 2.0 * cross))


def _metric(record: Mapping[str, object], candidate: str, surface: str) -> float:
    candidates = record.get("candidates")
    if not isinstance(candidates, Mapping) or candidate not in candidates:
        raise B07Error(f"missing candidate metric: {candidate}")
    entry = candidates[candidate]
    if not isinstance(entry, Mapping) or surface not in entry:
        raise B07Error(f"missing {candidate}.{surface}")
    value = float(entry[surface])
    if not (0.0 <= value <= 1.0):
        raise B07Error(f"metric outside [0,1]: {candidate}.{surface}")
    return value


def verify_behavioral_results(config: Mapping[str, object], results: Mapping[str, object]) -> None:
    if results.get("schema_version") != SCHEMA_RESULTS:
        raise B07Error("unsupported results schema")
    if str(results.get("config_sha256")) != sha256_json(config):
        raise B07Error("results/config identity mismatch")
    stated = str(results.get("results_sha256", ""))
    unsigned = dict(results)
    unsigned.pop("results_sha256", None)
    if stated != sha256_json(unsigned):
        raise B07Error("behavioral results self-hash mismatch")


def decide_acc(config: Mapping[str, object], results: Mapping[str, object]) -> dict:
    validate_config(config)
    verify_behavioral_results(config, results)
    families = results.get("holdout_families")
    if not isinstance(families, list):
        raise B07Error("results missing holdout_families")
    dcfg = config["decision"]  # type: ignore[index]
    required_count = int(dcfg["required_holdout_families"])
    if len(families) != required_count:
        raise B07Error("wrong number of held-out family results")
    expected_hold = {f.id for f in families_from_config(config) if f.split == "compiler_holdout"}
    result_ids = {str(r.get("family_id")) for r in families if isinstance(r, Mapping)}
    if result_ids != expected_hold:
        raise B07Error("held-out family result set mismatch")

    mandatory_controls = [str(x) for x in dcfg["mandatory_controls"]]
    min_direct_lift = float(dcfg["min_direct_lift"])
    min_margin = float(dcfg["min_control_margin"])
    min_recovery = float(dcfg["min_median_lift_recovery"])
    max_regression = float(dcfg["max_worst_family_regression"])
    require_semantic = bool(dcfg["require_semantic_hidden_positive_direction"])

    family_reports = []
    teacher_failures = []
    recoveries = []
    beat_all_count = 0
    worst_compiled_lift = 1.0

    for record in families:
        if not isinstance(record, Mapping):
            raise B07Error("invalid family result")
        fid = str(record["family_id"])
        base = _metric(record, "base", "hidden")
        direct = _metric(record, "direct_lora", "hidden")
        compiled = _metric(record, "compiled", "hidden")
        direct_lift = direct - base
        compiled_lift = compiled - base
        worst_compiled_lift = min(worst_compiled_lift, compiled_lift)
        if direct_lift < min_direct_lift:
            teacher_failures.append({"family_id": fid, "direct_lift": direct_lift})
        recovery = compiled_lift / max(direct_lift, 1e-9)
        recoveries.append(recovery)

        control_scores = {name: _metric(record, name, "hidden") for name in mandatory_controls}
        strongest_control = max(control_scores.values())
        control_margin = compiled - strongest_control
        semantic_direction_ok = True
        if require_semantic:
            semantic_direction_ok = (
                _metric(record, "compiled", "semantic_hidden")
                - _metric(record, "base", "semantic_hidden")
            ) > 0.0
        beats = control_margin >= min_margin and semantic_direction_ok
        if beats:
            beat_all_count += 1
        family_reports.append({
            "family_id": fid,
            "base": base,
            "direct_lora": direct,
            "compiled": compiled,
            "direct_lift": direct_lift,
            "compiled_lift": compiled_lift,
            "lift_recovery": recovery,
            "strongest_mandatory_control": strongest_control,
            "control_margin": control_margin,
            "semantic_hidden_positive_direction": semantic_direction_ok,
            "beats_all_mandatory_controls": beats,
            "control_scores": control_scores,
        })

    if teacher_failures:
        status = "INCONCLUSIVE_DIRECT_LORA_PRECONDITION"
        acc_killed = False
        go = False
        reasons = [
            "At least one held-out direct LoRA failed the minimum behavioral-lift precondition; the experiment cannot attribute failure to ACC."
        ]
    else:
        median_recovery = float(np.median(np.asarray(recoveries, dtype=np.float64)))
        enough_control_wins = beat_all_count >= int(dcfg["min_families_beating_all_controls"])
        recovery_ok = median_recovery >= min_recovery
        regression_ok = worst_compiled_lift >= -max_regression
        go = enough_control_wins and recovery_ok and regression_ok
        acc_killed = not go
        status = "GO_QWEN3_5_4B_REPLICATION" if go else "KILL_ACC_PREPARE_APA"
        reasons = []
        if not enough_control_wins:
            reasons.append("compiled update did not beat every mandatory control on enough unseen families")
        if not recovery_ok:
            reasons.append("median LiftRecovery below pre-registered threshold")
        if not regression_ok:
            reasons.append("worst unseen-family compiled regression exceeded threshold")
        if go:
            reasons.append("all pre-registered ACC falsification conditions passed")

    decision = {
        "schema_version": SCHEMA_DECISION,
        "task_id": config["task_id"],
        "experiment_id": config["experiment_id"],
        "status": status,
        "acc_killed": acc_killed,
        "go_to_exact_family_4b_replication": go,
        "teacher_precondition_failures": teacher_failures,
        "families_beating_all_controls": beat_all_count,
        "median_lift_recovery": float(np.median(np.asarray(recoveries, dtype=np.float64))) if recoveries else None,
        "worst_compiled_lift": worst_compiled_lift,
        "reasons": reasons,
        "family_reports": family_reports,
        "config_sha256": sha256_json(config),
        "results_sha256": sha256_json(results),
    }
    decision["decision_sha256"] = sha256_json(decision)
    return decision


def make_apa_followup_spec(config: Mapping[str, object], decision: Mapping[str, object]) -> dict:
    if decision.get("status") != "KILL_ACC_PREPARE_APA":
        raise B07Error("APA follow-up is emitted only after a valid ACC kill")
    spec = {
        "schema_version": SCHEMA_APA,
        "trigger_task_id": config["task_id"],
        "trigger_experiment_id": config["experiment_id"],
        "trigger_decision_sha256": decision["decision_sha256"],
        "name": "B07-E1 Plasticity Atlas support-reuse falsifier",
        "objective": "Test whether where-to-update transfers even when exact update prediction fails.",
        "base_model": config["base_model"],
        "data_policy": config["data_policy"],
        "frozen_family_split": {
            "compiler_train": [f.id for f in families_from_config(config) if f.split == "compiler_train"],
            "compiler_holdout": [f.id for f in families_from_config(config) if f.split == "compiler_holdout"],
        },
        "required_controls": [
            "random_same_cardinality_support",
            "global_magnitude_support",
            "per-family_oracle_support_upper_anchor"
        ],
        "minimal_mechanism": [
            "derive support scores only from compiler-train families",
            "freeze a shared support mask before opening holdout outcomes",
            "train holdout adapters restricted to shared support at matched trainable-parameter and step budget",
            "compare hidden behavioral lift against random support and unrestricted tiny-LoRA upper anchor"
        ],
        "kill_condition": "Reject reusable-plasticity hypothesis if frozen support fails to beat random same-cardinality support on >=3/4 holdout families or support overlap is seed-unstable.",
        "complexity_escalation_allowed": False,
        "gpu_execution_authorized": False,
    }
    spec["spec_sha256"] = sha256_json(spec)
    return spec


def read_jsonl(path: os.PathLike[str] | str) -> List[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise B07Error(f"invalid JSONL at line {lineno}: {path}") from exc
            if not isinstance(value, dict):
                raise B07Error(f"JSONL row is not object at line {lineno}: {path}")
            out.append(value)
    return out
