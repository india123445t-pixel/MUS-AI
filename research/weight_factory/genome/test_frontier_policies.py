import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent

class FrontierPolicyTests(unittest.TestCase):
    def load(self, name):
        return json.loads((ROOT / name).read_text(encoding='utf-8'))

    def test_cross_arch_fail_closed(self):
        p=self.load('cross_arch_distillation_policy_v1.json')
        self.assertEqual(p['default_mode'],'verified_output_only')
        self.assertIn('output_only_control_arm',p['experiment_requirements'])
        self.assertIn('direct_tensor_splice_across_architectures',p['forbidden'])
        self.assertIn('no_hosted_service_output_harvest',p['teacher_requirements'])

    def test_merge_is_same_base_and_pareto(self):
        p=self.load('evolutionary_merge_policy_v1.json')
        self.assertTrue(p['eligibility']['same_exact_base_revision'])
        self.assertEqual(p['fitness']['type'],'pareto')
        self.assertIn('catastrophic_regression',p['fitness']['hard_reject'])
        self.assertIn('EvoGM_style_generative_search',p['search_methods'])

    def test_adaptive_reasoning_is_cost_aware_but_correctness_first(self):
        p=self.load('adaptive_reasoning_policy_v1.json')
        self.assertTrue(p['reward_contract']['correctness_dominates'])
        self.assertTrue(p['reward_contract']['compute_penalty_only_after_correctness_gate'])
        self.assertIn('overthinking_rate',p['metrics'])
        self.assertIn('premature_stop_rate',p['metrics'])

    def test_registry_additions_are_default_research_only(self):
        p=self.load('source_registry_v5_additions.json')
        self.assertGreaterEqual(len(p['sources']),7)
        for src in p['sources']:
            self.assertNotEqual(src['admission'],'allow_unconditional')

if __name__ == '__main__':
    unittest.main()