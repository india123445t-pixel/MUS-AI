import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict

from training_signal_gate_v1 import (
    ADMIT, DENY, QUARANTINE, assess_record, build_protected_manifest,
    record_content_sha256, sha256_text, source_registry_sha256,
)
from training_shard_manifest_v1 import (
    MANIFEST_KIND, RECORD_DIGEST_SCHEME, ManifestError,
    build_training_shard_manifest, validate_training_shard_manifest,
)

ROOT = pathlib.Path(__file__).resolve().parent
POLICY = json.loads((ROOT / 'training_signal_policy_v1.json').read_text(encoding='utf-8'))
GATE_CODE = (ROOT / 'training_signal_gate_v1.py').read_bytes()


def registry():
    return {
        'schema_version': 5,
        'policy': 'default_deny',
        'sources': [
            {'id': 'source-a', 'kind': 'synthetic_dataset', 'admission': 'candidate_allow', 'license': 'internal'},
            {'id': 'source-b', 'kind': 'dataset', 'admission': 'allow', 'license': 'Apache-2.0'},
        ],
    }


def base_record(reg, rid='r1', source_id='source-a'):
    entry = next(x for x in reg['sources'] if x['id'] == source_id)
    row = {
        'record_id': rid,
        'prompt': f'Prompt {rid}',
        'answer': f'Answer {rid}',
        'source': {
            'id': source_id,
            'revision': 'rev-' + source_id,
            'immutable_revision': True,
            'content_sha256': sha256_text('artifact/' + source_id),
            'registry_sha256': source_registry_sha256(reg),
            'kind': entry['kind'],
            'admission': entry['admission'],
            'license_status': 'cleared',
            'provenance_status': 'complete',
        },
        'protected_eval': False,
        'contamination': {'holdout_scan_completed': True, 'protected_eval_hits': 0},
        'dedup': {'is_canonical': True, 'semantic_duplicate_score': 0.1},
        'verifiers': [{
            'type': 'exact', 'passed': True,
            'target_failure_modes': ['wrong_answer'],
            'fault_injection_passed': True,
            'independent_observation': True,
        }],
        'baseline': {'attempts': 10, 'successes': 4},
        'language_lane': 'other',
        'synthetic': True,
    }
    row['record_content_sha256'] = record_content_sha256(row)
    return row


def with_decision(row, policy, protected, reg):
    row = copy.deepcopy(row)
    row['record_content_sha256'] = record_content_sha256(row)
    row['training_signal_decision'] = asdict(assess_record(row, policy, protected, reg))
    return row


def fixture():
    reg = registry()
    protected = build_protected_manifest(['private-holdout-alpha beta gamma delta epsilon zeta eta theta'], 8, 'p2-test')
    admitted = [with_decision(base_record(reg, 'r2', 'source-b'), POLICY, protected, reg),
                with_decision(base_record(reg, 'r1', 'source-a'), POLICY, protected, reg)]
    q = base_record(reg, 'q1'); q['baseline'] = {'attempts': 10, 'successes': 10}
    q = with_decision(q, POLICY, protected, reg)
    d = base_record(reg, 'd1'); d['source']['license_status'] = 'audit_required'
    d = with_decision(d, POLICY, protected, reg)
    assert all(r['training_signal_decision']['decision'] == ADMIT for r in admitted)
    assert q['training_signal_decision']['decision'] == QUARANTINE
    assert d['training_signal_decision']['decision'] == DENY
    provenance = {'bundle_id': 'prov-v1', 'license_receipt_sha256': sha256_text('license-evidence')}
    return reg, protected, admitted, [q], [d], provenance


def build(**overrides):
    reg, protected, admitted, quarantine, denied, provenance = fixture()
    kwargs = dict(
        admitted=admitted,
        quarantined=quarantine,
        denied=denied,
        policy=copy.deepcopy(POLICY),
        registry=reg,
        protected_contamination_manifest=protected,
        admission_gate_code=GATE_CODE,
        provenance_license_evidence_bundle=provenance,
    )
    kwargs.update(overrides)
    return build_training_shard_manifest(**kwargs)


class TrainingShardManifestTests(unittest.TestCase):
    def test_build_valid_manifest(self):
        manifest, shard = build()
        self.assertEqual(manifest['manifest_kind'], MANIFEST_KIND)
        self.assertEqual(manifest['row_count'], 2)
        self.assertEqual(manifest['decision_counts'], {'ADMIT': 2, 'QUARANTINE': 1, 'DENY': 1})
        self.assertEqual(manifest['admitted_record_content_digest_scheme'], RECORD_DIGEST_SCHEME)
        self.assertEqual(validate_training_shard_manifest(manifest), (True, 'ok'))
        self.assertEqual(hashlib.sha256(shard).hexdigest(), manifest['shard_file_sha256'])
        self.assertEqual(len(shard), manifest['byte_size'])

    def test_deterministic_under_input_reordering(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        m1, s1 = build_training_shard_manifest(
            admitted=admitted, quarantined=quarantine, denied=denied, policy=copy.deepcopy(POLICY), registry=reg,
            protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
            provenance_license_evidence_bundle=provenance)
        m2, s2 = build_training_shard_manifest(
            admitted=list(reversed(admitted)), quarantined=list(reversed(quarantine)), denied=list(reversed(denied)),
            policy=copy.deepcopy(POLICY), registry=reg, protected_contamination_manifest=protected,
            admission_gate_code=GATE_CODE, provenance_license_evidence_bundle=copy.deepcopy(provenance))
        self.assertEqual(s1, s2)
        self.assertEqual(m1, m2)

    def test_manifest_exports_hashes_not_training_plaintext(self):
        manifest, _ = build()
        text = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn('Prompt r1', text)
        self.assertNotIn('Answer r1', text)
        self.assertNotIn('private-holdout-alpha', text)

    def test_provenance_bundle_not_embedded(self):
        reg, protected, admitted, quarantine, denied, _ = fixture()
        secret = {'internal_note': 'DO-NOT-EXPORT-PLAINTEXT', 'license': 'ok'}
        manifest, _ = build_training_shard_manifest(
            admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
            protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
            provenance_license_evidence_bundle=secret)
        self.assertNotIn('DO-NOT-EXPORT-PLAINTEXT', json.dumps(manifest))
        self.assertEqual(len(manifest['provenance_license_evidence_bundle_sha256']), 64)

    def test_admitted_content_tamper_fails_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        admitted[0]['answer'] = 'tampered'
        with self.assertRaisesRegex(ManifestError, 'content_hash_mismatch'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_partition_mismatch_fails_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        with self.assertRaisesRegex(ManifestError, 'non_admit_row_in_admitted_partition|decision_partition_mismatch'):
            build_training_shard_manifest(
                admitted=quarantine, quarantined=admitted, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_duplicate_record_id_across_decisions_fails_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        denied[0]['record_id'] = admitted[0]['record_id']
        denied[0]['record_content_sha256'] = record_content_sha256(denied[0])
        denied[0]['training_signal_decision'] = asdict(assess_record(denied[0], POLICY, protected, reg))
        with self.assertRaisesRegex(ManifestError, 'duplicate_record_id_across_decisions'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_empty_admitted_shard_fails_closed(self):
        reg, protected, _, quarantine, denied, provenance = fixture()
        with self.assertRaisesRegex(ManifestError, 'empty_admitted_shard'):
            build_training_shard_manifest(
                admitted=[], quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_source_revision_must_be_immutable(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        admitted[0]['source']['immutable_revision'] = False
        with self.assertRaisesRegex(ManifestError, 'source_revision_not_immutable'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_source_registry_binding_must_match(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        admitted[0]['source']['registry_sha256'] = '0' * 64
        with self.assertRaisesRegex(ManifestError, 'source_registry_hash_mismatch'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_source_must_exist_in_registry(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        admitted[0]['source']['id'] = 'not-in-registry'
        admitted[0]['record_content_sha256'] = record_content_sha256(admitted[0])
        with self.assertRaisesRegex(ManifestError, 'source_not_in_registry'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_duplicate_admitted_content_fails_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        clone = copy.deepcopy(admitted[0]); clone['record_id'] = 'r-clone'
        # Force the same claimed content identity; producer must reject duplicate content identities before shard freeze.
        clone['record_content_sha256'] = admitted[0]['record_content_sha256']
        admitted.append(clone)
        with self.assertRaises(ManifestError):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_required_language_audit_receipt_missing_fails_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        row = admitted[0]
        row['language_lane'] = 'darija'
        row['language_quality_audit'] = {'passed': True, 'auditor_class': 'native_moroccan_review'}
        row['record_content_sha256'] = record_content_sha256(row)
        with self.assertRaisesRegex(ManifestError, 'language_quality_audit.receipt_sha256'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_required_language_audit_receipt_is_bound(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        receipt = sha256_text('darija-audit')
        row = admitted[0]
        row['language_lane'] = 'darija'
        row['language_quality_audit'] = {'passed': True, 'auditor_class': 'native_moroccan_review', 'receipt_sha256': receipt}
        row['record_content_sha256'] = record_content_sha256(row)
        manifest, _ = build_training_shard_manifest(
            admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
            protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
            provenance_license_evidence_bundle=provenance)
        self.assertEqual(manifest['language_audit_receipt_sha256'], [receipt])

    def test_protected_manifest_tamper_fails_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        protected['record_count'] += 1
        with self.assertRaisesRegex(ManifestError, 'invalid_protected_contamination_manifest'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)



    def test_policy_identity_changes_manifest_identity(self):
        m1, _ = build()
        p = copy.deepcopy(POLICY); p['learnability']['note'] += ' variant'
        m2, _ = build(policy=p)
        self.assertNotEqual(m1['admission_policy_sha256'], m2['admission_policy_sha256'])
        self.assertNotEqual(m1['manifest_id'], m2['manifest_id'])

    def test_policy_semantic_change_must_replay_same_decisions(self):
        p = copy.deepcopy(POLICY); p['learnability']['max_student_success_rate'] = 0.30
        with self.assertRaisesRegex(ManifestError, 'admission_replay_mismatch'):
            build(policy=p)

    def test_gate_code_must_match_executed_gate(self):
        with self.assertRaisesRegex(ManifestError, 'admission_gate_code_does_not_match_executed_gate'):
            build(admission_gate_code=GATE_CODE + b'\n# variant\n')

    def test_provenance_identity_changes_manifest_identity(self):
        m1, _ = build()
        m2, _ = build(provenance_license_evidence_bundle={'bundle_id': 'other'})
        self.assertNotEqual(m1['provenance_license_evidence_bundle_sha256'], m2['provenance_license_evidence_bundle_sha256'])
        self.assertNotEqual(m1['manifest_id'], m2['manifest_id'])

    def test_decision_evidence_tamper_fails_replay(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        denied[0]['training_signal_decision']['reasons'].append('extra_reason')
        with self.assertRaisesRegex(ManifestError, 'admission_replay_mismatch'):
            build_training_shard_manifest(
                admitted=admitted, quarantined=quarantine, denied=denied, policy=POLICY, registry=reg,
                protected_contamination_manifest=protected, admission_gate_code=GATE_CODE,
                provenance_license_evidence_bundle=provenance)

    def test_created_from_is_sorted_unique(self):
        manifest, _ = build()
        sources = manifest['created_from']
        tuples = [(x['source_id'], x['revision'], x['source_artifact_sha256']) for x in sources]
        self.assertEqual(tuples, sorted(set(tuples)))

    def test_current_p1_gate_does_not_invent_contamination_receipts(self):
        manifest, _ = build()
        self.assertEqual(manifest['protected_training_contamination_evidence']['receipt_sha256'], [])

    def test_manifest_self_tamper_is_detected(self):
        manifest, _ = build()
        manifest['row_count'] += 1
        ok, reason = validate_training_shard_manifest(manifest)
        self.assertFalse(ok)
        self.assertIn(reason, {'row_count_decision_count_mismatch', 'manifest_id_mismatch', 'manifest_digest_mismatch'})

    def test_manifest_id_tamper_is_detected(self):
        manifest, _ = build()
        manifest['manifest_id'] = 'aqlevon-training-shard-v1:' + '0' * 64
        self.assertEqual(validate_training_shard_manifest(manifest), (False, 'manifest_id_mismatch'))

    def test_unknown_manifest_fields_are_rejected(self):
        manifest, _ = build()
        manifest['downstream_verified'] = True
        ok, reason = validate_training_shard_manifest(manifest)
        self.assertFalse(ok)
        self.assertTrue(reason.startswith('manifest_extra:'))

    def test_cli_build_is_deterministic_and_fail_closed(self):
        reg, protected, admitted, quarantine, denied, provenance = fixture()
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)
            files = {
                'a.jsonl': admitted, 'q.jsonl': quarantine, 'd.jsonl': denied,
            }
            for name, rows in files.items():
                (td / name).write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows), encoding='utf-8')
            (td / 'policy.json').write_text(json.dumps(POLICY), encoding='utf-8')
            (td / 'registry.json').write_text(json.dumps(reg), encoding='utf-8')
            (td / 'protected.json').write_text(json.dumps(protected), encoding='utf-8')
            (td / 'prov.json').write_text(json.dumps(provenance), encoding='utf-8')
            (td / 'gate.py').write_bytes(GATE_CODE)
            base = [sys.executable, str(ROOT / 'training_shard_manifest_v1.py'), 'build',
                    '--admitted', str(td / 'a.jsonl'), '--quarantine', str(td / 'q.jsonl'), '--denied', str(td / 'd.jsonl'),
                    '--policy', str(td / 'policy.json'), '--source-registry', str(td / 'registry.json'),
                    '--protected-contamination-manifest', str(td / 'protected.json'), '--admission-gate-code', str(td / 'gate.py'),
                    '--provenance-license-evidence', str(td / 'prov.json')]
            cp1 = subprocess.run(base + ['--output-shard', str(td/'s1.jsonl'), '--output-manifest', str(td/'m1.json')], capture_output=True, text=True)
            cp2 = subprocess.run(base + ['--output-shard', str(td/'s2.jsonl'), '--output-manifest', str(td/'m2.json')], capture_output=True, text=True)
            self.assertEqual(cp1.returncode, 0, cp1.stderr + cp1.stdout)
            self.assertEqual(cp2.returncode, 0, cp2.stderr + cp2.stdout)
            self.assertEqual((td/'s1.jsonl').read_bytes(), (td/'s2.jsonl').read_bytes())
            self.assertEqual((td/'m1.json').read_bytes(), (td/'m2.json').read_bytes())
            # Corrupt the policy: command must return non-zero and create no successful manifest.
            (td / 'policy.json').write_text('{bad', encoding='utf-8')
            cp3 = subprocess.run(base + ['--output-shard', str(td/'bad-s.jsonl'), '--output-manifest', str(td/'bad-m.json')], capture_output=True, text=True)
            self.assertEqual(cp3.returncode, 2)
            self.assertFalse((td/'bad-m.json').exists())


if __name__ == '__main__':
    unittest.main()
