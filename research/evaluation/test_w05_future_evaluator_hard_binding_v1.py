import json
import subprocess
from pathlib import Path

import pytest

import w05_future_evaluator_hard_binding_v1 as hb
import w05_future_sealed_custody_gate_v1 as custody


def git(repo: Path, *args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return cp.stdout.decode().strip()


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class MockScorer:
    def __init__(self):
        self.calls = 0
        self.authorizations = []

    def __call__(self, authorization):
        self.calls += 1
        self.authorizations.append(dict(authorization))
        return {"synthetic_score": 1, "scored": True}


def make_pack():
    pack = {
        "schema_version": 1,
        "pack_kind": "SYNTHETIC_FUTURE_W05_TEST_PACK",
        "tasks": [{"id": "synthetic-only"}],
    }
    pack["pack_sha256"] = custody.self_digest(pack, "pack_sha256")
    return pack


def setup_valid_bundle(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "AQLEVON Agent02 Test")
    git(repo, "config", "user.email", "agent02-test@example.invalid")
    (repo / "README").write_text("root\n", encoding="utf-8")
    root_commit = commit_all(repo, "root")

    secret = b"synthetic-future-secret-only-for-agent02-wave2-tests"
    pack = make_pack()
    plaintext = custody.canonical_bytes(pack)
    secret_file = tmp_path / "future-secret.bin"
    pack_file = tmp_path / "future-pack.json"
    secret_file.write_bytes(secret)
    pack_file.write_bytes(plaintext)

    prereg = custody.seal_preregistration({
        "scope": custody.FUTURE_SCOPE,
        "score_visibility_at_registration": custody.NO_SCORES,
        "sealed_pack_sha256": pack["pack_sha256"],
        "sealed_commitment_sha256": "1" * 64,
        "secret_file_sha256": custody.sha256_bytes(secret),
        "sealed_plaintext_file_sha256": custody.sha256_bytes(plaintext),
    })
    prereg_path = "custody/preregistration.json"
    prereg_file = repo / prereg_path
    prereg_file.parent.mkdir(parents=True, exist_ok=True)
    prereg_file.write_bytes(custody.canonical_bytes(prereg))
    prereg_commit = commit_all(repo, "anchor preregistration")

    candidate_sha = "3" * 64
    policy_sha = "4" * 64
    start_receipt = custody.seal_evaluation_start_receipt({
        "score_visibility_at_receipt": custody.NO_SCORES,
        "evaluation_started": False,
        "preregistration_sha256": prereg["record_sha256"],
        "preregistration_anchor_commit": prereg_commit,
        "preregistration_anchor_path": prereg_path,
        "candidate_manifest_sha256": candidate_sha,
        "evaluation_policy_sha256": policy_sha,
    })
    start_path = "custody/evaluation-start.json"
    start_file = repo / start_path
    start_file.write_bytes(custody.canonical_bytes(start_receipt))
    start_commit = commit_all(repo, "anchor evaluation start")

    return {
        "repo": repo,
        "root_commit": root_commit,
        "secret_file": secret_file,
        "pack_file": pack_file,
        "prereg": prereg,
        "prereg_file": prereg_file,
        "prereg_path": prereg_path,
        "prereg_commit": prereg_commit,
        "start_receipt": start_receipt,
        "start_file": start_file,
        "start_path": start_path,
        "start_commit": start_commit,
        "candidate_sha": candidate_sha,
        "policy_sha": policy_sha,
    }


def run_bound(bundle, scorer, **overrides):
    args = {
        "repo": bundle["repo"],
        "preregistration_file": bundle["prereg_file"],
        "preregistration_anchor_commit": bundle["prereg_commit"],
        "preregistration_anchor_path": bundle["prereg_path"],
        "evaluation_start_receipt_file": bundle["start_file"],
        "evaluation_start_anchor_commit": bundle["start_commit"],
        "evaluation_start_anchor_path": bundle["start_path"],
        "expected_candidate_manifest_sha256": bundle["candidate_sha"],
        "expected_evaluation_policy_sha256": bundle["policy_sha"],
        "secret_file": bundle["secret_file"],
        "sealed_plaintext_file": bundle["pack_file"],
        "scorer": scorer,
    }
    args.update(overrides)
    return hb.run_future_w05_evaluator(**args)


def test_positive_invokes_scorer_exactly_once_after_all_gates(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()

    result = run_bound(bundle, scorer)

    assert result["status"] == hb.FINAL_STATUS
    assert result["scorer_invocations"] == 1
    assert scorer.calls == 1
    assert len(scorer.authorizations) == 1
    authorization = scorer.authorizations[0]
    assert authorization["status"] == hb.BINDING_STATUS
    assert authorization["candidate_manifest_sha256"] == bundle["candidate_sha"]
    assert authorization["evaluation_policy_sha256"] == bundle["policy_sha"]
    assert authorization["private_content_emitted"] is False
    assert authorization["historical_w05_authority"] is False
    serialized = json.dumps(authorization, sort_keys=True)
    assert str(bundle["secret_file"]) not in serialized
    assert str(bundle["pack_file"]) not in serialized
    assert "tasks" not in serialized


def test_nonexistent_anchor_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()

    with pytest.raises(custody.CustodyGateError, match="preregistration_anchor_not_found"):
        run_bound(bundle, scorer, preregistration_anchor_commit="f" * 40)

    assert scorer.calls == 0


def test_preregistration_byte_mismatch_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()
    changed = dict(bundle["prereg"])
    changed["sealed_commitment_sha256"] = "9" * 64
    changed["record_sha256"] = custody.self_digest(changed, "record_sha256")
    bundle["prereg_file"].write_bytes(custody.canonical_bytes(changed))

    with pytest.raises(custody.CustodyGateError, match="preregistration_anchor_bytes_mismatch"):
        run_bound(bundle, scorer)

    assert scorer.calls == 0


def test_evaluation_start_byte_mismatch_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()
    changed = dict(bundle["start_receipt"])
    changed["evaluation_policy_sha256"] = "8" * 64
    changed["receipt_sha256"] = custody.self_digest(changed, "receipt_sha256")
    bundle["start_file"].write_bytes(custody.canonical_bytes(changed))

    with pytest.raises(custody.CustodyGateError, match="evaluation_start_anchor_bytes_mismatch"):
        run_bound(bundle, scorer)

    assert scorer.calls == 0


def test_late_sibling_chronology_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()
    supplied_prereg = tmp_path / "supplied-preregistration.json"
    supplied_prereg.write_bytes(custody.canonical_bytes(bundle["prereg"]))

    git(bundle["repo"], "checkout", "-b", "sibling-evaluation-start", bundle["root_commit"])
    sibling_start_file = bundle["repo"] / bundle["start_path"]
    sibling_start_file.parent.mkdir(parents=True, exist_ok=True)
    sibling_start_file.write_bytes(custody.canonical_bytes(bundle["start_receipt"]))
    sibling_start_commit = commit_all(bundle["repo"], "sibling evaluation start")

    with pytest.raises(custody.CustodyGateError, match="preregistration_anchor_not_before_evaluation_start"):
        run_bound(
            bundle,
            scorer,
            preregistration_file=supplied_prereg,
            evaluation_start_receipt_file=sibling_start_file,
            evaluation_start_anchor_commit=sibling_start_commit,
        )

    assert scorer.calls == 0


def test_candidate_mismatch_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()

    with pytest.raises(custody.CustodyGateError, match="evaluation_start_candidate_manifest_mismatch"):
        run_bound(bundle, scorer, expected_candidate_manifest_sha256="5" * 64)

    assert scorer.calls == 0


def test_evaluation_policy_mismatch_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()

    with pytest.raises(hb.EvaluatorBindingError, match="evaluation_policy_sha256_mismatch"):
        run_bound(bundle, scorer, expected_evaluation_policy_sha256="6" * 64)

    assert scorer.calls == 0


def test_material_hash_mismatch_never_invokes_scorer(tmp_path: Path):
    bundle = setup_valid_bundle(tmp_path)
    scorer = MockScorer()
    bundle["secret_file"].write_bytes(b"tampered-synthetic-secret")

    with pytest.raises(custody.CustodyGateError, match="secret_file_sha256_mismatch"):
        run_bound(bundle, scorer)

    assert scorer.calls == 0
