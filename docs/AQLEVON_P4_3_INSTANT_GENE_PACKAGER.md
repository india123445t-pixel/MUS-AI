# AQLEVON P4.3 — Instant Gene Packager

Worker 04 / task `P4.3-A04-INSTANT-GENE-PACKAGER`.

This is zero-wait preparation only. No real candidate is packaged or promoted.

## Pre-created output directory / schema

The finalizer writes exactly:
- `<output-dir>/gene_package_v1.json` — existing `AQLEVON_GENE_PACKAGE_V1` schema.
- `<output-dir>/single_gene_activation_request.json` — reversible, immutable-base single-gene activation request.

It consumes authoritative Candidate Artifact Manifest, Worker-05 Evaluation Decision Receipt, Manager acceptance SHA, Worker-06 runtime receipt(s), and exact candidate artifact directory. It refuses W05 status other than `PROMOTION_ELIGIBLE`, validates exact artifact bytes, and delegates all package/base/layout/topology rules to the already-tested P4 Gene Package implementation.

## Exact one-command path after W05 + Manager acceptance

```bash
cd research/weight_factory/genome &&
python3 p4_3_instant_gene_packager.py \
  --candidate /evidence/candidate_artifact_manifest.json \
  --evaluation /evidence/evaluation_decision_receipt.json \
  --manager-acceptance-sha256 '<64-lowercase-hex>' \
  --compute-receipt /evidence/runtime_attempt_receipt.json \
  --artifact-root /evidence/candidate_artifact \
  --output-dir /evidence/gene_package
```

One-function API:
`p4_3_instant_gene_packager.finalize(...)`.

## Fail-closed boundary

Wrong candidate/evaluation hashes, rejected W05 status, tampered/missing/extra artifact bytes, invalid runtime receipt, training-binding mismatch, or invalid Manager SHA fail before a package is emitted. Runtime activation additionally rejects base repo/revision/base-manifest/tokenizer/config/layout/topology mismatch.

No quantization, multi-gene routing, production mutation, or 27B training is enabled here.

Changing the canonical Gene Package schema or authority requirements is `REQUIRES_MANAGER_REBIND`; this P4.3 wrapper does not do so.
