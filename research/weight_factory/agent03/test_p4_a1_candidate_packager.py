import unittest
import p4_a1_candidate_packager as p


class TestCandidatePackager(unittest.TestCase):
    def test_cpu_self_test(self):
        p.self_test()

    def test_non_lora_tensor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside_frozen_topology"):
            p.validate_tensor_shapes([("model.layers.3.self_attn.k_proj.lora_A.weight", (4, 8))])

    def test_changed_elements_count_only_lora_b(self):
        state = {
            "layers.3.self_attn.q_proj.lora_B.weight": [0, 2, 0, -1],
            "layers.3.self_attn.q_proj.lora_A.weight": [3, 0],
        }
        self.assertEqual(p.count_nonzero_B(state), 2)


if __name__ == "__main__":
    unittest.main()
