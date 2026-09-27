import json
from pathlib import Path

import pytest

import w05_future_sealed_custody_gate_v1 as g


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
        "anchor_kind": "git_commit",
        "immutable_reference": "deadbeef" * 5,
        "anchored_at_utc": "2026-09-27T10:00:00Z",
    })


def test_future_material_passes_without_content_output(tmp_path: Path):
    secret = b"synthetic-future-secret-for-unit-test-only-0123456789"
    pack = make_pack()
    plaintext = g.canonical_bytes(pack)
    secret_file = tmp_path / "secret.bin"
    pack_file = tmp_path / "pack.json"
    secret_file.write_bytes(secret)
    pack_file.write_bytes(plaintext)
    record = make_record(secret, plaintext, pack["pack_sha256"])

    result = g.verify_future_material(record, secret_file, pack_file)
    assert result["status"] == "PASS_FUTURE_MATERIAL_HASH_BOUND"
    assert result["private_content_emitted"] is False
    assert result["authoritative_for_legacy_w05"] is False
    assert "tasks" not in result


def test_legacy_w05_identities_are_rejected():
    body = {
        "scope": g.FUTURE_SCOPE,
        "score_visibility_at_registration": g.NO_SCORES,
        "sealed_pack_sha256": g.LEGACY_W05["sealed_pack_sha256"],
        "sealed_commitment_sha256": g.LEGACY_W05["sealed_commitment_sha256"],
        "secret_file_sha256": g.LEGACY_W05["secret_file_sha256"],
        "sealed_plaintext_file_sha256": g.LEGACY_W05["sealed_plaintext_file_sha256"],
        "anchor_kind": "git_commit",
        "immutable_reference": "abc123",
        "anchored_at_utc": "2026-09-27T10:00:00Z",
    }
    record = g.seal_preregistration(body)
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


def test_secret_hash_mismatch_fails_closed(tmp_path: Path):
    secret = b"a" * 40
    pack = make_pack()
    plaintext = g.canonical_bytes(pack)
    sf = tmp_path / "secret.bin"
    pf = tmp_path / "pack.json"
    sf.write_bytes(b"different")
    pf.write_bytes(plaintext)
    record = make_record(secret, plaintext, pack["pack_sha256"])
    with pytest.raises(g.CustodyGateError, match="secret_file_sha256_mismatch"):
        g.verify_future_material(record, sf, pf)


def test_pack_self_digest_tamper_fails(tmp_path: Path):
    secret = b"b" * 40
    pack = make_pack()
    plaintext = g.canonical_bytes(pack)
    record = make_record(secret, plaintext, pack["pack_sha256"])
    sf = tmp_path / "secret.bin"
    pf = tmp_path / "pack.json"
    sf.write_bytes(secret)
    tampered = dict(pack)
    tampered["tasks"] = [{"id": "changed"}]
    tampered_bytes = g.canonical_bytes(tampered)
    pf.write_bytes(tampered_bytes)
    record["sealed_plaintext_file_sha256"] = g.sha256_bytes(tampered_bytes)
    record["record_sha256"] = g.self_digest(record, "record_sha256")
    with pytest.raises(g.CustodyGateError, match="sealed_pack_self_digest_mismatch"):
        g.verify_future_material(record, sf, pf)
