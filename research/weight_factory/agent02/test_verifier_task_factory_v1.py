#!/usr/bin/env python3
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import verifier_task_factory_v1 as f

SECRET=b"test-only-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
CODE_SHA=hashlib.sha256((ROOT/"verifier_task_factory_v1.py").read_bytes()).hexdigest()


def build():
    return f.build_factory(SECRET,CODE_SHA)


class FactoryTests(unittest.TestCase):
    def test_exactly_50_tasks_25_twins(self):
        b=build(); tasks=b['public_pack']['tasks']
        self.assertEqual(len(tasks),50)
        self.assertEqual(sum(t['verifier_mode']=='vulnerable' for t in tasks),25)
        self.assertEqual(sum(t['verifier_mode']=='hardened' for t in tasks),25)
        pairs={}
        for t in tasks: pairs.setdefault(t['semantic_core_id'],set()).add(t['verifier_mode'])
        self.assertEqual(len(pairs),25)
        self.assertTrue(all(v=={'vulnerable','hardened'} for v in pairs.values()))

    def test_split_is_semantic_core_disjoint(self):
        b=build(); s=b['split_manifest']
        self.assertFalse(set(s['train_semantic_core_ids']) & set(s['eval_semantic_core_ids']))
        self.assertEqual((len(s['train_semantic_core_ids']),len(s['eval_semantic_core_ids'])),(18,7))

    def test_only_hardened_train_tasks_are_training_eligible(self):
        b=build(); tasks=b['public_pack']['tasks']
        eligible=[t for t in tasks if t['training_eligible']]
        self.assertEqual(len(eligible),18)
        self.assertTrue(all(t['verifier_mode']=='hardened' and t['semantic_split']=='train' for t in eligible))
        self.assertTrue(all(not t['training_eligible'] for t in tasks if t['verifier_mode']=='vulnerable'))
        self.assertTrue(all(not t['training_eligible'] for t in tasks if t['semantic_split']=='eval'))

    def test_bundle_is_deterministic(self):
        self.assertEqual(f.canonical_p2_json_bytes(build()), f.canonical_p2_json_bytes(build()))

    def test_manifest_and_pack_validation(self):
        b=build(); self.assertEqual(f.validate_factory_bundle(b['manifest'],b['public_pack'],b['sealed_pack'],b['split_manifest']),(True,'ok'))

    def test_tampered_manifest_fails(self):
        b=build(); b['manifest']['task_count']=49
        ok,reason=f.validate_factory_bundle(b['manifest'],b['public_pack'],b['sealed_pack'],b['split_manifest'])
        self.assertFalse(ok); self.assertEqual(reason,'factory_manifest_digest_mismatch')

    def test_unknown_hash_profile_fails(self):
        b=build(); b['public_pack']['hash_profile']='other'
        ok,reason=f.validate_factory_bundle(b['manifest'],b['public_pack'],b['sealed_pack'],b['split_manifest'])
        self.assertFalse(ok); self.assertEqual(reason,'public_pack_hash_profile_mismatch')

    def test_float_rejected_from_authoritative_hash(self):
        with self.assertRaisesRegex(f.FactoryError,'float_forbidden'):
            f.canonical_p2_json_bytes({'x':1.25})

    def test_non_ascii_authoritative_key_rejected(self):
        with self.assertRaisesRegex(f.FactoryError,'non_ascii'):
            f.canonical_p2_json_bytes({'é':1})

    def test_public_pack_has_no_oracle_program_or_hidden_fixture(self):
        pack=build()['public_pack']
        forbidden={'oracle_program','hidden_fixtures','__hidden_canary__','visible_expected_state'}
        def walk(v):
            if isinstance(v,dict):
                self.assertFalse(forbidden & set(v), forbidden & set(v))
                for child in v.values(): walk(child)
            elif isinstance(v,list):
                for child in v: walk(child)
        walk(pack)
        blob=f.canonical_p2_json_bytes(pack)
        self.assertNotIn(SECRET,blob)

    def test_secret_never_appears_in_public_or_manifest(self):
        b=build(); needle=SECRET
        self.assertNotIn(needle,f.canonical_p2_json_bytes(b['public_pack']))
        self.assertNotIn(needle,f.canonical_p2_json_bytes(b['manifest']))
        self.assertEqual(b['manifest']['canary_secret_sha256'],hashlib.sha256(SECRET).hexdigest())

    def test_oracle_passes_all_hardened_tasks(self):
        b=build(); by_core={v['semantic_core_id']:v for v in b['sealed_pack']['verifiers']}
        hard=[t for t in b['public_pack']['tasks'] if t['verifier_mode']=='hardened']
        for task in hard:
            result=f.verify_submission(task,by_core[task['semantic_core_id']],by_core[task['semantic_core_id']]['oracle_program'])
            self.assertTrue(result['passed'],(task['task_id'],result))
            self.assertEqual(result['checked_hidden_fixtures'],3)

    def test_public_hardcode_exploit_passes_vulnerable_but_fails_hardened_all_cores(self):
        b=build(); by_core={v['semantic_core_id']:v for v in b['sealed_pack']['verifiers']}
        tasks=b['public_pack']['tasks']
        for core in sorted(by_core):
            vuln=next(t for t in tasks if t['semantic_core_id']==core and t['verifier_mode']=='vulnerable')
            hard=next(t for t in tasks if t['semantic_core_id']==core and t['verifier_mode']=='hardened')
            exploit=[{'op':'replace_state','state':copy.deepcopy(by_core[core]['visible_expected_state'])}]
            self.assertTrue(f.verify_submission(vuln,by_core[core],exploit)['passed'])
            self.assertFalse(f.verify_submission(hard,by_core[core],exploit)['passed'])

    def test_extra_side_effect_then_restore_rejected(self):
        b=build(); task=next(t for t in b['public_pack']['tasks'] if t['semantic_core_id']=='core-01' and t['verifier_mode']=='hardened')
        v=next(v for v in b['sealed_pack']['verifiers'] if v['semantic_core_id']=='core-01')
        p=copy.deepcopy(v['oracle_program'])+[{'op':'set','key':'junk','value':1},{'op':'delete','key':'junk'}]
        result=f.verify_submission(task,v,p)
        self.assertFalse(result['passed']); self.assertIn('side_effect',result['reason'])

    def test_hidden_canary_mutation_rejected(self):
        b=build(); task=next(t for t in b['public_pack']['tasks'] if t['semantic_core_id']=='core-01' and t['verifier_mode']=='hardened')
        v=next(v for v in b['sealed_pack']['verifiers'] if v['semantic_core_id']=='core-01')
        p=copy.deepcopy(v['oracle_program'])+[{'op':'set','key':'__hidden_canary__','value':'x'}]
        result=f.verify_submission(task,v,p)
        self.assertFalse(result['passed'])

    def test_semantics_preserving_perturbations_keep_core_binding(self):
        b=build(); task=next(t for t in b['public_pack']['tasks'] if t['semantic_core_id']=='core-03' and t['verifier_mode']=='hardened')
        v=next(v for v in b['sealed_pack']['verifiers'] if v['semantic_core_id']=='core-03')
        for variant in ('concise','strict','tool_json'):
            p=f.perturb_public_task(task,variant)
            self.assertEqual(p['semantic_core_sha256'],task['semantic_core_sha256'])
            self.assertNotEqual(p['task_sha256'],task['task_sha256'])
            self.assertTrue(f.verify_submission(p,v,v['oracle_program'])['passed'])

    def test_unknown_perturbation_fails_closed(self):
        b=build(); task=b['public_pack']['tasks'][0]
        with self.assertRaisesRegex(f.FactoryError,'unknown_perturbation'):
            f.perturb_public_task(task,'random')

    def test_sft_export_contains_only_18_train_hardened_records(self):
        b=build(); records=f.export_sft_control_records(b)
        self.assertEqual(len(records),18)
        ids={r['record_id'] for r in records}
        self.assertEqual(ids,set(b['split_manifest']['training_eligible_task_ids']))
        self.assertTrue(all('-hardened' in x for x in ids))
        self.assertTrue(all('core-19' not in x and 'core-20' not in x and 'core-21' not in x and 'core-22' not in x and 'core-23' not in x and 'core-24' not in x and 'core-25' not in x for x in ids))

    def test_sft_export_does_not_contain_hidden_canaries(self):
        blob=f.canonical_p2_json_bytes(f.export_sft_control_records(build()))
        self.assertNotIn(b'__hidden_canary__',blob)
        self.assertNotIn(SECRET,blob)

    def test_all_tasks_are_owned_and_no_external_dataset_ids(self):
        for t in build()['public_pack']['tasks']:
            p=t['provenance']
            self.assertEqual(p['owner'],'AQLEVON')
            self.assertEqual(p['source_class'],'aqlevon_owned_synthetic')
            self.assertEqual(p['external_dataset_ids'],[])
            self.assertIs(p['protected_eval_ingested'],False)
            self.assertEqual(p['license_status'],'aqlevon_owned')

    def test_factory_manifest_declares_no_protected_or_unclear_ingestion(self):
        p=build()['manifest']['provenance']
        self.assertIs(p['protected_eval_ingested'],False)
        self.assertIs(p['unclear_license_material_ingested'],False)
        self.assertEqual(p['external_dataset_ids'],[])

    def test_task_pair_semantic_core_hash_matches_verifier(self):
        b=build(); by={v['semantic_core_id']:v for v in b['sealed_pack']['verifiers']}
        for t in b['public_pack']['tasks']:
            self.assertEqual(t['semantic_core_sha256'],by[t['semantic_core_id']]['semantic_core_sha256'])

    def test_hidden_canary_values_unique(self):
        vals=[]
        for v in build()['sealed_pack']['verifiers']:
            for h in v['hidden_fixtures']: vals.append(h['initial_state']['__hidden_canary__'])
        self.assertEqual(len(vals),75); self.assertEqual(len(vals),len(set(vals)))

    def test_canary_secret_minimum_length_enforced(self):
        with self.assertRaisesRegex(f.FactoryError,'canary_secret_too_short'):
            f.build_factory(b'short',CODE_SHA)

    def test_invalid_code_hash_fails_closed(self):
        with self.assertRaisesRegex(f.FactoryError,'invalid_factory_code_sha256'):
            f.build_factory(SECRET,'bad')

    def test_candidate_unknown_op_fails_closed(self):
        b=build(); task=next(t for t in b['public_pack']['tasks'] if t['verifier_mode']=='hardened')
        v=next(v for v in b['sealed_pack']['verifiers'] if v['semantic_core_id']==task['semantic_core_id'])
        result=f.verify_submission(task,v,[{'op':'shell','cmd':'rm -rf /'}])
        self.assertFalse(result['passed']); self.assertTrue(result['reason'].startswith('program_error:'))

    def test_cli_build_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            td=pathlib.Path(td); secret=td/'secret'; secret.write_bytes(SECRET)
            o1=td/'o1'; o2=td/'o2'
            base=[sys.executable,str(ROOT/'verifier_task_factory_v1.py'),'build','--canary-secret-file',str(secret)]
            a=subprocess.run(base+['--output-dir',str(o1)],capture_output=True,text=True)
            b=subprocess.run(base+['--output-dir',str(o2)],capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stderr+a.stdout); self.assertEqual(b.returncode,0,b.stderr+b.stdout)
            for name in ('factory_manifest.json','public_task_pack.json','sealed_verifier_pack.json','split_manifest.json','sft_control_records.json'):
                self.assertEqual((o1/name).read_bytes(),(o2/name).read_bytes(),name)

    def test_cli_short_secret_fails_without_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            td=pathlib.Path(td); secret=td/'secret'; secret.write_bytes(b'x')
            out=td/'out'
            cp=subprocess.run([sys.executable,str(ROOT/'verifier_task_factory_v1.py'),'build','--canary-secret-file',str(secret),'--output-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(cp.returncode,2)
            self.assertFalse((out/'factory_manifest.json').exists())

    def test_authoritative_bundle_has_no_floats(self):
        def walk(v):
            if isinstance(v,float): return False
            if isinstance(v,list): return all(walk(x) for x in v)
            if isinstance(v,dict): return all(walk(x) for x in v.values())
            return True
        self.assertTrue(walk(build()))

    def test_manifest_counts_exact(self):
        m=build()['manifest']
        self.assertEqual(m['task_count'],50)
        self.assertEqual(m['semantic_core_count'],25)
        self.assertEqual(m['vulnerable_task_count'],25)
        self.assertEqual(m['hardened_task_count'],25)
        self.assertEqual(m['training_eligible_count'],18)
        self.assertEqual(m['eval_hardened_count'],7)

    def test_public_expected_state_hash_prevents_plaintext_answer_export(self):
        b=build()
        for t in b['public_pack']['tasks']:
            self.assertNotIn('visible_expected_state',t)
            self.assertTrue(f._valid_sha256(t['public_expected_state_sha256']))

    def test_vulnerable_tasks_are_explicitly_red_team_only(self):
        for t in build()['public_pack']['tasks']:
            if t['verifier_mode']=='vulnerable':
                self.assertIs(t['red_team_only'],True)
                self.assertIs(t['training_eligible'],False)

    def test_committed_public_catalog_matches_factory_output(self):
        path=ROOT/'p3_public_task_pack_v1.json'
        self.assertTrue(path.exists())
        committed=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(f.canonical_p2_json_bytes(committed),f.canonical_p2_json_bytes(build()['public_pack']))

    def test_committed_split_manifest_matches_factory_output(self):
        path=ROOT/'p3_task_split_manifest_v1.json'
        self.assertTrue(path.exists())
        committed=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(f.canonical_p2_json_bytes(committed),f.canonical_p2_json_bytes(build()['split_manifest']))

    def test_canary_secret_rotates_sealed_evidence_not_public_catalog(self):
        b1=build()
        secret2=b'another-test-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        b2=f.build_factory(secret2,CODE_SHA)
        self.assertEqual(f.canonical_p2_json_bytes(b1['public_pack']),f.canonical_p2_json_bytes(b2['public_pack']))
        self.assertEqual(f.canonical_p2_json_bytes(b1['split_manifest']),f.canonical_p2_json_bytes(b2['split_manifest']))
        self.assertNotEqual(b1['sealed_pack']['pack_sha256'],b2['sealed_pack']['pack_sha256'])
        self.assertNotEqual(b1['manifest']['hidden_canary_root_sha256'],b2['manifest']['hidden_canary_root_sha256'])
        self.assertNotEqual(b1['manifest']['manifest_sha256'],b2['manifest']['manifest_sha256'])


if __name__=='__main__':
    unittest.main()