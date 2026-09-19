import copy, json, pathlib, tempfile, unittest
import gene1_data_verifier_pack_v1 as g

SECRET_A=b'A'*32
SECRET_B=b'B'*32

class Gene1PackTests(unittest.TestCase):
    def setUp(self):
        self.training=g.build_training_bundle()
        self.sealed=g.build_sealed_eval(SECRET_A)
        self.manifest,self.commit,self.split=g.build_commitments(self.training,self.sealed)

    def test_counts(self):
        self.assertEqual(len(self.training['cores']),56)
        self.assertEqual(len(self.training['training_pack']['tasks']),112)
        self.assertEqual(len(self.training['rows']),56)
        self.assertEqual(self.sealed['semantic_core_count'],28)
        self.assertEqual(self.sealed['task_count'],56)

    def test_all_families_train_and_eval(self):
        self.assertEqual(set(c['family'] for c in self.training['cores']),set(g.FAMILIES))
        self.assertEqual(set(t['family'] for t in self.sealed['tasks']),set(g.FAMILIES))

    def test_train_eval_core_disjoint(self):
        self.assertTrue(set(self.split['train_semantic_core_ids']).isdisjoint(self.split['eval_semantic_core_ids']))

    def test_training_only_hardened_eligible(self):
        for t in self.training['training_pack']['tasks']:
            self.assertEqual(t['training_eligible'],t['verifier_mode']=='hardened')

    def test_vulnerable_oracle_not_public(self):
        for t in self.training['training_pack']['tasks']:
            if t['verifier_mode']=='vulnerable': self.assertNotIn('oracle_program',t)

    def test_training_hardened_oracle_present(self):
        self.assertTrue(all('oracle_program' in t for t in self.training['training_pack']['tasks'] if t['verifier_mode']=='hardened'))

    def test_public_train_pack_has_no_eval_ids(self):
        text=json.dumps(self.training['training_pack'],sort_keys=True)
        self.assertNotIn('eval-',text)

    def test_secret_rotation_changes_sealed_not_training(self):
        s2=g.build_sealed_eval(SECRET_B)
        self.assertNotEqual(self.sealed['pack_sha256'],s2['pack_sha256'])
        self.assertEqual(self.training['training_pack']['pack_sha256'],g.build_training_bundle()['training_pack']['pack_sha256'])

    def test_secret_required(self):
        with self.assertRaises(g.GenePackError): g.build_sealed_eval(b'x')

    def test_eval_is_deterministic_given_secret(self):
        self.assertEqual(self.sealed,g.build_sealed_eval(SECRET_A))

    def test_training_is_deterministic(self):
        self.assertEqual(self.training['training_pack'],g.build_training_bundle()['training_pack'])
        self.assertEqual(self.training['shard_bytes'],g.build_training_bundle()['shard_bytes'])

    def test_training_manifest_valid(self):
        self.assertEqual(g.validate_bundle(self.training,self.manifest,self.commit,self.split),(True,'ok'))

    def test_manifest_tamper_rejected(self):
        bad=copy.deepcopy(self.manifest); bad['row_count']+=1
        self.assertNotEqual(g.validate_bundle(self.training,bad,self.commit,self.split),(True,'ok'))

    def test_commitment_tamper_rejected(self):
        bad=copy.deepcopy(self.commit); bad['task_count']+=1
        self.assertNotEqual(g.validate_bundle(self.training,self.manifest,bad,self.split),(True,'ok'))

    def test_split_tamper_rejected(self):
        bad=copy.deepcopy(self.split); bad['eval_semantic_core_ids'].append(bad['train_semantic_core_ids'][0]); bad['manifest_sha256']=g.self_hash(bad,'manifest_sha256')
        self.assertEqual(g.validate_bundle(self.training,self.manifest,self.commit,bad),(False,'split_overlap'))

    def test_p2_hash_float_forbidden(self):
        with self.assertRaises(g.GenePackError): g.canonical_bytes({'x':1.25})

    def test_p2_hash_nonascii_key_forbidden(self):
        with self.assertRaises(g.GenePackError): g.canonical_bytes({'é':1})

    def test_newline_nfkc_normalization(self):
        a=g.canonical_bytes({'x':'Ａ\r\nB'})
        b=g.canonical_bytes({'x':'A\nB'})
        self.assertEqual(a,b)

    def test_source_registry_default_deny(self):
        self.assertEqual(self.training['source_registry']['policy'],'default_deny')
        self.assertEqual(len(self.training['source_registry']['sources']),1)

    def test_provenance_no_external_datasets(self):
        p=self.training['provenance']
        self.assertEqual(p['external_dataset_ids'],[])
        self.assertFalse(p['protected_eval_ingested'])
        self.assertFalse(p['unclear_license_material_ingested'])

    def test_admission_evidence_is_static_and_honest(self):
        a=self.training['admission']
        self.assertEqual(a['decision'],'ADMIT_STATIC_DATA_INTEGRITY')
        self.assertEqual(a['empirical_student_baseline'],'DEFERRED_TO_SURROGATE_TOURNAMENT_NOT_FABRICATED')
        self.assertFalse(a['protected_eval_ingested'])

    def test_sealed_commitment_has_exact_content_hashes(self):
        self.assertEqual(self.commit['contamination_commitment_scheme'],g.CONTAMINATION_COMMITMENT_SCHEME)
        self.assertEqual(len(self.commit['protected_eval_content_sha256']),56)
        self.assertEqual(len(set(self.commit['protected_eval_content_sha256'])),56)

    def test_empirical_baseline_truth_boundary(self):
        self.assertEqual(self.manifest['empirical_student_baseline_status'],'NOT_MEASURED_BY_WORKER_02_NO_GPU_CLAIM')

    def test_shard_records_have_unique_content_hashes(self):
        vals=[r['record_content_sha256'] for r in self.training['rows']]
        self.assertEqual(len(vals),len(set(vals)))

    def test_shard_canonical_line_count(self):
        self.assertEqual(len(self.training['shard_bytes'].splitlines()),56)
        self.assertTrue(self.training['shard_bytes'].endswith(b'\n'))

    def test_shard_manifest_hash_binds_exact_bytes(self):
        self.assertEqual(self.manifest['shard_file_sha256'],g.sha256_bytes(self.training['shard_bytes']))
        self.assertEqual(self.manifest['byte_size'],len(self.training['shard_bytes']))

    def test_record_hash_domain_matches_p2(self):
        r=self.training['rows'][0]
        expected=g.sha256_obj({'domain':'AQLEVON_TRAINING_ROW_CONTENT_V1','record_id':r['record_id'],'prompt':r['prompt'],'answer':r['answer']})
        self.assertEqual(r['record_content_sha256'],expected)

    def test_hardened_oracles_pass_all_training_cores(self):
        tasks={t['semantic_core_id']:t for t in self.training['training_pack']['tasks'] if t['verifier_mode']=='hardened'}
        for c in self.training['cores']:
            self.assertTrue(g.verify(tasks[c['core_id']],c,c['oracle_program'])['passed'],c['core_id'])

    def test_visible_state_hardcode_attack_fails_hardened(self):
        tasks={t['semantic_core_id']:t for t in self.training['training_pack']['tasks'] if t['verifier_mode']=='hardened'}
        for c in self.training['cores']:
            attack=[{'op':'replace_state','state':c['expected_state']}]
            self.assertFalse(g.verify(tasks[c['core_id']],c,attack)['passed'],c['core_id'])

    def test_visible_state_hardcode_attack_passes_vulnerable(self):
        tasks={t['semantic_core_id']:t for t in self.training['training_pack']['tasks'] if t['verifier_mode']=='vulnerable'}
        for c in self.training['cores']:
            attack=[{'op':'replace_state','state':c['expected_state']}]
            self.assertTrue(g.verify(tasks[c['core_id']],c,attack)['passed'],c['core_id'])

    def test_wrong_side_effect_fails_hardened(self):
        c=next(x for x in self.training['cores'] if x['family']=='increment')
        t=next(x for x in self.training['training_pack']['tasks'] if x['semantic_core_id']==c['core_id'] and x['verifier_mode']=='hardened')
        # correct final value + decoy rewritten to same value still touches forbidden path
        key=[k for k in c['initial_state'] if k.startswith('counter_')][0]
        decoy=[k for k in c['initial_state'] if k.startswith('decoy_')][0]
        by=c['expected_state'][key]-c['initial_state'][key]
        p=[{'op':'increment','key':key,'by':by},{'op':'set','key':decoy,'value':c['initial_state'][decoy]}]
        self.assertEqual(g.verify(t,c,p)['reason'],'side_effect_mismatch')

    def test_prompt_perturbations_are_distinct(self):
        for c in self.training['cores']:
            self.assertEqual(len(set(c['prompt_perturbations'])),3)

    def test_eval_contains_anti_shortcut_variants(self):
        self.assertTrue(all(len(t['anti_shortcut_variants'])==3 for t in self.sealed['tasks']))

    def test_eval_contains_canaries(self):
        self.assertTrue(all(len(t['hidden_canary'])==32 for t in self.sealed['tasks']))

    def test_eval_plaintext_not_in_commitment(self):
        txt=json.dumps(self.commit,sort_keys=True)
        self.assertNotIn('oracle_program',txt)
        self.assertNotIn('expected_state',txt)
        self.assertNotIn('hidden_canary',txt)

    def test_commitment_forbids_training_visibility(self):
        self.assertEqual(self.commit['training_worker_visibility'],'FORBIDDEN')
        self.assertFalse(self.commit['plaintext_committed_to_git'])

    def test_write_bundle_outputs_public_and_private_files(self):
        with tempfile.TemporaryDirectory() as d:
            out=pathlib.Path(d); result=g.write_bundle(out,SECRET_A)
            self.assertEqual(result['training_rows'],'56')
            self.assertEqual(result['eval_tasks'],'56')
            self.assertTrue((out/'gene1_training_shard_v1.jsonl').exists())
            self.assertTrue((out/'gene1_sealed_eval_pack_PRIVATE_v1.json').exists())

    def test_manifest_self_digest_stable(self):
        self.assertRegex(self.manifest['manifest_sha256'],r'^[0-9a-f]{64}$')
        self.assertEqual(self.manifest['manifest_sha256'],g.self_hash(self.manifest,'manifest_sha256'))

if __name__=='__main__': unittest.main(verbosity=2)