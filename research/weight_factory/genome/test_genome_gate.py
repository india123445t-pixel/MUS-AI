import unittest
from genome_gate import source_training_allowed, source_recipe_allowed, validate_registry, validate_genome, can_promote_gene, load_json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class GenomeGateTests(unittest.TestCase):
    def setUp(self):
        self.reg=load_json(ROOT/'source_registry_v3.json')
        self.genome=load_json(ROOT/'genome_manifest_v2.json')
    def src(self,sid): return next(x for x in self.reg['sources'] if x['id']==sid)
    def test_registry_valid(self): self.assertEqual(validate_registry(self.reg),[])
    def test_genome_valid(self): self.assertEqual(validate_genome(self.genome),[])
    def test_hosted_models_denied_for_training(self):
        for sid in ('hosted_openai','hosted_anthropic','hosted_gemini'):
            self.assertFalse(source_training_allowed(self.src(sid)))
    def test_qwen_flash_next_not_commercial_training_source(self):
        self.assertFalse(source_training_allowed(self.src('qwen_flash_next')))
    def test_open_weight_teachers_allowed_under_registry(self):
        for sid in ('teacher_deepseek_v4_pro','teacher_glm52','teacher_gpt_oss_120b'):
            self.assertTrue(source_training_allowed(self.src(sid)))
    def test_permissive_research_recipes_are_recipe_only(self):
        for sid in ('agent0_recipe','evogm_recipe','qwen_agentworld'):
            self.assertTrue(source_recipe_allowed(self.src(sid)))
            self.assertFalse(source_training_allowed(self.src(sid)))
    def test_unclear_or_noncommercial_recipes_fail_closed(self):
        for sid in ('rzero_recipe','drzero_recipe'):
            self.assertFalse(source_recipe_allowed(self.src(sid)))
            self.assertFalse(source_training_allowed(self.src(sid)))
    def test_incomplete_community_checkpoint_is_quarantined(self):
        self.assertFalse(source_training_allowed(self.src('community_qwen38_fable5_coding_distilled')))
    def test_self_evolution_gene_has_hard_verifiers(self):
        g=next(x for x in self.genome['genes'] if x['id']=='R0-L')
        self.assertTrue({'objective_verifier','novelty_scan','benchmark_distance'}.issubset(set(g['verifiers'])))
    def test_gene_promotion_fail_closed(self):
        ok,missing=can_promote_gene({'artifact_hash':'abc','exact_lineage':'base@rev'})
        self.assertFalse(ok); self.assertIn('contamination_pass',missing)
    def test_gene_promotion_contract(self):
        m={k:True for k in self.genome['promotion_requirements']}
        m['artifact_hash']='abc';m['exact_lineage']='base@rev'
        ok,missing=can_promote_gene(m);self.assertTrue(ok);self.assertEqual(missing,[])

if __name__=='__main__': unittest.main()
