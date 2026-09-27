import json
import subprocess
from pathlib import Path

import pytest

import w05_future_sealed_custody_gate_v1 as g


def git(repo: Path, *args: str) -> str:
    cp = subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return cp.stdout.decode().strip()


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "AQLEVON Test")
    git(repo, "config", "user.email", "aqlevon-test@example.invalid")
    (repo / "README").write_text("root\n", encoding="utf-8")
    commit_all(repo, "root")
    return repo


def make_pack():
    pack = {"schema_version": 1, "pack_kind": "TEST_FUTURE_PACK", "tasks": [{"id": "synthetic-test-only"}]}
    pack["pack_sha256"] = g.self_digest(pack, "pack_sha256")
    return pack


def make_record(secret: bytes, plaintext: bytes, pack_sha: str):
    return g.seal_preregistration({
        "scope": g.FUTURE_SCOPE,
        "score_visibility_at_registration": g.NO_SCORES,
        "sealed_pack_sha256": pack_sha,
        "sealed_commitment_sha256": "1" * 64,
        "secret_file_sha256": g.sha256_bytes(secret),
        "sealed_plaintext_file_sha256": g.sha256_bytes(plaintext),
    })


def anchor_prereg(repo: Path, record: dict, path: str = "custody/prereg.json"):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(g.canonical_bytes(record))
    return p, commit_all(repo, "anchor preregistration")


def make_start_receipt(record: dict, prereg_commit: str, prereg_path: str, candidate_sha: str):
    return g.seal_evaluation_start_receipt({
        "score_visibility_at_receipt": g.NO_SCORES,
        "evaluation_started": False,
        "preregistration_sha256": record["record_sha256"],
        "preregistration_anchor_commit": prereg_commit,
        "preregistration_anchor_path": prereg_path,
        "candidate_manifest_sha256": candidate_sha,
        "evaluation_policy_sha256": "2" * 64,
    })


def anchor_start(repo: Path, receipt: dict, path: str = "custody/start.json"):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(g.canonical_bytes(receipt))
    return p, commit_all(repo, "anchor evaluation start receipt")


def prepare_valid(tmp_path: Path):
    repo = init_repo(tmp_path)
    secret = b"synthetic-future-secret-for-unit-test-only-0123456789"
    pack = make_pack()
    plaintext = g.canonical_bytes(pack)
    sf = tmp_path / "secret.bin"
    pf = tmp_path / "pack.json"
    sf.write_bytes(secret)
    pf.write_bytes(plaintext)

    record = make_record(secret, plaintext, pack["pack_sha256"])
    prereg_path = "custody/prereg.json"
    prereg_file, prereg_commit = anchor_prereg(repo, record, prereg_path)
    candidate_sha = "3" * 64
    start = make_start_receipt(record, prereg_commit, prereg_path, candidate_sha)
    start_path = "custody/start.json"
    start_file, start_commit = anchor_start(repo, start, start_path)
    return repo, sf, pf, record, prereg_file, prereg_commit, prereg_path, start_file, start_commit, start_path, candidate_sha


def prove(prepared):
    repo, sf, pf, record, prereg_file, prereg_commit, prereg_path, start_file, start_commit, start_path, candidate_sha = prepared
    return g.verify_chronology(
        repo, prereg_file, prereg_commit, prereg_path,
        start_file, start_commit, start_path, candidate_sha,
    )


def test_future_material_requires_real_git_chronology_and_passes(tmp_path: Path):
    prepared = prepare_valid(tmp_path)
    chronology = prove(prepared)
    repo, sf, pf, record, *_ = prepared
    result = g.verify_future_material(record, sf, pf, chronology["proof"])
    assert chronology["proof"]["status"] == "PASS_PREREGISTRATION_ANCHORED_BEFORE_EVALUATION_START"
    assert chronology["proof"]["caller_supplied_timestamp_authoritative"] is False
    assert result["status"] == "PASS_FUTURE_MATERIAL_HASH_BOUND_AND_CHRONOLOGY_PROVEN"
    assert result["private_content_emitted"] is False
    assert result["authoritative_for_legacy_w05"] is False
    assert "tasks" not in result


def test_legacy_w05_identities_are_rejected():
    record = g.seal_preregistration({
        "scope": g.FUTURE_SCOPE,
        "score_visibility_at_registration": g.NO_SCORES,
        "sealed_pack_sha256": g.LEGACY_W05["sealed_pack_sha256"],
        "sealed_commitment_sha256": g.LEGACY_W05["sealed_commitment_sha256"],
        "secret_file_sha256": g.LEGACY_W05["secret_file_sha256"],
        "sealed_plaintext_file_sha256": g.LEGACY_W05["sealed_plaintext_file_sha256"],
    })
    errors = g.validate_preregistration(record)
    assert any(e.startswith("legacy_w05_identity_forbidden:") for e in errors)


def test_score_visibility_must_be_preregistered():
    secret = b"s" * 40
    pack = make_pack()
    plaintext = g.canonical_bytes(pack)
    record = make_record(secret, plaintext, pack["pack_sha256"])
    record["score_visibility_at_registration"] = "SCORES_ALREADY_SEEN"
    record["record_sha256"] = g.self_digest(record, "record_sha256")
    assert "score_visibility_boundary" in g.validate_preregistration(record)


def test_nonexistent_anchor_fails_closed(tmp_path: Path):
    prepared = list(prepare_valid(tmp_path))
    prepared[5] = "f" * 40
    with pytest.raises(g.CustodyGateError, match="preregistration_anchor_not_found"):
        prove(prepared)


def test_anchor_that_does_not_contain_exact_preregistration_fails_closed(tmp_path: Path):
    prepared = prepare_valid(tmp_path)
    repo, sf, pf, record, prereg_file, prereg_commit, prereg_path, start_file, start_commit, start_path, candidate_sha = prepared
    other = dict(record)
    other["sealed_commitment_sha256"] = "9" * 64
    other["record_sha256"] = g.self_digest(other, "record_sha256")
    supplied = tmp_path / "supplied-prereg.json"
    supplied.write_bytes(g.canonical_bytes(other))
    with pytest.raises(g.CustodyGateError, match="preregistration_anchor_bytes_mismatch"):
        g.verify_chronology(
            repo, supplied, prereg_commit, prereg_path,
            start_file, start_commit, start_path, candidate_sha,
        )


def test_preregistration_created_after_evaluation_start_fails_closed(tmp_path: Path):
    repo = init_repo(tmp_path)
    root_commit = git(repo, "rev-parse", "HEAD")
    secret = b"x" * 40
    pack = make_pack()
    plaintext = g.canonical_bytes(pack)
    record = make_record(secret, plaintext, pack["pack_sha256"])
    candidate_sha = "3" * 64

    # Branch A: preregistration is created after the common root.
    git(repo, "checkout", "-b", "late-prereg", root_commit)
    prereg_file, prereg_commit = anchor_prereg(repo, record)

    # Branch B: evaluation-start receipt is independently anchored without the
    # preregistration commit in its ancestry, even though it references that hash.
    git(repo, "checkout", "-b", "eval-start", root_commit)
    start = make_start_receipt(record, prereg_commit, "custody/prereg.json", candidate_sha)
    start_file, start_anchor_commit = anchor_start(repo, start)
    supplied_prereg = tmp_path / "supplied-prereg.json"
    supplied_prereg.write_bytes(g.canonical_bytes(record))

    with pytest.raises(g.CustodyGateError, match="preregistration_anchor_not_before_evaluation_start"):
        g.verify_chronology(
            repo, supplied_prereg, prereg_commit, "custody/prereg.json",
            start_file, start_anchor_commit, "custody/start.json", candidate_sha,
        )


def test_tampered_anchor_reference_fails_closed(tmp_path: Path):
    prepared = prepare_valid(tmp_path)
    repo, sf, pf, record, prereg_file, prereg_commit, prereg_path, start_file, start_commit, start_path, candidate_sha = prepared

    # Anchor a later, self-consistent start receipt whose preregistration path
    # reference has been tampered. The outer caller still supplies the true path.
    tampered = make_start_receipt(record, prereg_commit, "custody/other.json", candidate_sha)
    start_file.write_bytes(g.canonical_bytes(tampered))
    tampered_start_commit = commit_all(repo, "tamper prereg anchor reference")
    with pytest.raises(g.CustodyGateError, match="evaluation_start_preregistration_anchor_path_mismatch"):
        g.verify_chronology(
            repo, prereg_file, prereg_commit, prereg_path,
            start_file, tampered_start_commit, start_path, candidate_sha,
        )


def test_start_receipt_candidate_mismatch_fails_closed(tmp_path: Path):
    prepared = prepare_valid(tmp_path)
    repo, sf, pf, record, prereg_file, prereg_commit, prereg_path, start_file, start_commit, start_path, candidate_sha = prepared
    with pytest.raises(g.CustodyGateError, match="evaluation_start_candidate_manifest_mismatch"):
        g.verify_chronology(
            repo, prereg_file, prereg_commit, prereg_path,
            start_file, start_commit, start_path, "4" * 64,
        )


def test_secret_hash_mismatch_fails_closed(tmp_path: Path):
    prepared = prepare_valid(tmp_path)
    chronology = prove(prepared)
    repo, sf, pf, record, *_ = prepared
    sf.write_bytes(b"different")
    with pytest.raises(g.CustodyGateError, match="secret_file_sha256_mismatch"):
        g.verify_future_material(record, sf, pf, chronology["proof"])


def test_pack_self_digest_tamper_fails(tmp_path: Path):
    prepared = prepare_valid(tmp_path)
    chronology = prove(prepared)
    repo, sf, pf, record, *_ = prepared
    tampered = make_pack()
    tampered["tasks"] = [{"id": "changed"}]
    tampered_bytes = g.canonical_bytes(tampered)
    pf.write_bytes(tampered_bytes)
    record = dict(record)
    record["sealed_plaintext_file_sha256"] = g.sha256_bytes(tampered_bytes)
    record["record_sha256"] = g.self_digest(record, "record_sha256")
    proof = dict(chronology["proof"])
    proof["preregistration_sha256"] = record["record_sha256"]
    proof["chronology_sha256"] = g.self_digest(proof, "chronology_sha256")
    with pytest.raises(g.CustodyGateError, match="sealed_pack_self_digest_mismatch"):
        g.verify_future_material(record, sf, pf, proof)
