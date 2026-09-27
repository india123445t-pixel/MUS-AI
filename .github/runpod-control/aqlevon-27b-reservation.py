#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

RESERVATION_KIND = "AQLEVON_27B_AUTH_RESERVATION_V1"
CONSUMPTION_KIND = "AQLEVON_27B_AUTH_CONSUMPTION_V2"
AUTHORIZATION_KIND = "AQLEVON_MANAGER_PAID_AUTHORIZATION_V2"
CONTROL_PLANE_CONTRACT = "AQLEVON_27B_CONTROL_PLANE_V2"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing_{label}:{path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"invalid_{label}_object")
    return data


def validate_authorization(auth: dict[str, Any], expected_authorization_id: str | None) -> str:
    auth_id = str(auth.get("authorization_id") or "")
    if not auth_id:
        raise ValueError("missing_authorization_id")
    if expected_authorization_id and auth_id != expected_authorization_id:
        raise ValueError(f"authorization_id_mismatch:{auth_id}")
    if auth.get("kind") != AUTHORIZATION_KIND:
        raise ValueError("legacy_or_invalid_authorization_kind")
    if auth.get("control_plane_contract") != CONTROL_PLANE_CONTRACT:
        raise ValueError("authorization_control_plane_contract_mismatch")
    if auth.get("fresh_authorization") is not True:
        raise ValueError("authorization_not_marked_fresh")
    if not str(auth.get("issued_at_utc") or "").strip():
        raise ValueError("authorization_missing_issued_at")
    required_true = (
        "single_use",
        "training_authorized",
        "automatic_cleanup_required",
        "artifact_preservation_required",
        "no_main_merge",
        "sealed_eval_forbidden",
    )
    for key in required_true:
        if auth.get(key) is not True:
            raise ValueError(f"authorization_flag_not_true:{key}")
    return auth_id


def reservation_id(auth_id: str, run_id: str, run_attempt: str) -> str:
    payload = f"{auth_id}\0{run_id}\0{run_attempt}".encode()
    return hashlib.sha256(payload).hexdigest()


def validate_source_sha(source_sha: str) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", source_sha):
        raise ValueError("invalid_source_sha")


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def atomic_replace(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def verify_claim(
    authorization: Path,
    reservation: Path,
    consumed: Path,
    run_id: str,
    run_attempt: str,
    source_sha: str,
    expected_authorization_id: str | None,
    *,
    require_precreate: bool = False,
    require_created: bool = False,
    pod_id: str | None = None,
) -> dict[str, Any]:
    validate_source_sha(source_sha)
    auth = load_json(authorization, "authorization")
    auth_id = validate_authorization(auth, expected_authorization_id)
    expected_rid = reservation_id(auth_id, run_id, run_attempt)
    res = load_json(reservation, "reservation")
    con = load_json(consumed, "consumption")

    if res.get("kind") != RESERVATION_KIND:
        raise ValueError("invalid_reservation_kind")
    if con.get("kind") != CONSUMPTION_KIND:
        raise ValueError("invalid_consumption_kind")
    for obj, label in ((res, "reservation"), (con, "consumption")):
        if obj.get("authorization_id") != auth_id:
            raise ValueError(f"{label}_authorization_mismatch")
        if obj.get("reservation_id") != expected_rid:
            raise ValueError(f"{label}_reservation_id_mismatch")
        if str(obj.get("run_id")) != str(run_id) or str(obj.get("run_attempt")) != str(run_attempt):
            raise ValueError(f"{label}_run_identity_mismatch")
        if str(obj.get("source_sha")) != str(source_sha):
            raise ValueError(f"{label}_source_sha_mismatch")
    if res.get("single_use_claimed") is not True or con.get("single_use_consumed") is not True:
        raise ValueError("single_use_not_claimed")

    if require_precreate:
        if res.get("state") != "RESERVED_BEFORE_PROVIDER_CREATE":
            raise ValueError("reservation_not_precreate")
        if con.get("consumption_state") != "CONSUMED_BY_PRECREATE_RESERVATION":
            raise ValueError("consumption_not_precreate")
        if res.get("provider_create_attempted") is not False or con.get("provider_create_attempted") is not False:
            raise ValueError("provider_create_already_attempted")
        if res.get("pod_id") is not None or con.get("pod_id") is not None:
            raise ValueError("precreate_claim_has_pod_id")

    if require_created:
        if res.get("state") != "PROVIDER_CREATED":
            raise ValueError("reservation_not_provider_created")
        if con.get("consumption_state") != "PROVIDER_CREATED":
            raise ValueError("consumption_not_provider_created")
        if res.get("provider_create_attempted") is not True or con.get("provider_create_attempted") is not True:
            raise ValueError("provider_create_not_recorded")
        expected_pod = str(pod_id or "")
        if not expected_pod:
            raise ValueError("missing_expected_pod_id")
        if str(res.get("pod_id") or "") != expected_pod or str(con.get("pod_id") or "") != expected_pod:
            raise ValueError("pod_id_mismatch")

    return {"authorization_id": auth_id, "reservation_id": expected_rid}


def reserve(args: argparse.Namespace) -> None:
    validate_source_sha(args.source_sha)
    auth = load_json(args.authorization, "authorization")
    auth_id = validate_authorization(auth, args.expected_authorization_id)
    if args.reservation.exists() or args.consumed.exists():
        raise ValueError("reservation_or_consumption_already_exists")
    rid = reservation_id(auth_id, args.run_id, args.run_attempt)
    now = utc_now()
    res = {
        "kind": RESERVATION_KIND,
        "authorization_id": auth_id,
        "reservation_id": rid,
        "run_id": str(args.run_id),
        "run_attempt": str(args.run_attempt),
        "source_sha": args.source_sha,
        "reserved_at_utc": now,
        "state": "RESERVED_BEFORE_PROVIDER_CREATE",
        "single_use_claimed": True,
        "provider_create_attempted": False,
        "pod_id": None,
    }
    con = {
        "kind": CONSUMPTION_KIND,
        "authorization_id": auth_id,
        "reservation_id": rid,
        "run_id": str(args.run_id),
        "run_attempt": str(args.run_attempt),
        "source_sha": args.source_sha,
        "consumed_at_utc": now,
        "consumption_state": "CONSUMED_BY_PRECREATE_RESERVATION",
        "single_use_consumed": True,
        "provider_create_attempted": False,
        "pod_id": None,
    }
    write_exclusive(args.reservation, res)
    try:
        write_exclusive(args.consumed, con)
    except Exception:
        # Keep the reservation file in place. Partial claim creation fails closed.
        raise
    print("AQLEVON_27B_PRECREATE_RESERVATION_LOCAL", rid)


def mark_created(args: argparse.Namespace) -> None:
    info = verify_claim(
        args.authorization,
        args.reservation,
        args.consumed,
        args.run_id,
        args.run_attempt,
        args.source_sha,
        args.expected_authorization_id,
        require_precreate=True,
    )
    res = load_json(args.reservation, "reservation")
    con = load_json(args.consumed, "consumption")
    now = utc_now()
    res.update(
        {
            "state": "PROVIDER_CREATED",
            "provider_create_attempted": True,
            "provider_created_at_utc": now,
            "pod_id": args.pod_id,
        }
    )
    con.update(
        {
            "consumption_state": "PROVIDER_CREATED",
            "provider_create_attempted": True,
            "provider_created_at_utc": now,
            "pod_id": args.pod_id,
        }
    )
    atomic_replace(args.reservation, res)
    atomic_replace(args.consumed, con)
    print("AQLEVON_27B_PROVIDER_CREATE_RECORDED", info["reservation_id"])


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--reservation", required=True, type=Path)
    parser.add_argument("--consumed", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--expected-authorization-id")


def main() -> int:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)

    p_reserve = subs.add_parser("reserve")
    add_common(p_reserve)

    p_verify = subs.add_parser("verify")
    add_common(p_verify)
    p_verify.add_argument("--require-precreate", action="store_true")
    p_verify.add_argument("--require-created", action="store_true")
    p_verify.add_argument("--pod-id")

    p_created = subs.add_parser("mark-created")
    add_common(p_created)
    p_created.add_argument("--pod-id", required=True)

    args = parser.parse_args()
    if args.command == "reserve":
        reserve(args)
    elif args.command == "verify":
        info = verify_claim(
            args.authorization,
            args.reservation,
            args.consumed,
            args.run_id,
            args.run_attempt,
            args.source_sha,
            args.expected_authorization_id,
            require_precreate=args.require_precreate,
            require_created=args.require_created,
            pod_id=args.pod_id,
        )
        print("AQLEVON_27B_RESERVATION_VERIFIED", info["reservation_id"])
    elif args.command == "mark-created":
        mark_created(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
