import tempfile, unittest
from pathlib import Path
import torch
from safetensors.torch import save_file
from interference_atlas import analyze

class TestAtlas(unittest.TestCase):
    def test_opposed_vectors_flag_directional_risk(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.safetensors'; b=Path(d)/'b.safetensors'
            save_file({'model.layers.0.q_proj.weight':torch.tensor([1.,2.,0.,-1.])},str(a))
            save_file({'model.layers.0.q_proj.weight':torch.tensor([-1.,-2.,0.,1.])},str(b))
            r=analyze(a,b,1e-8)
            self.assertAlmostEqual(r['summary']['weighted_cosine'],-1.0,places=5)
            self.assertGreater(r['summary']['weighted_directional_risk'],0.9)
            self.assertEqual(r['summary']['weighted_sign_conflict'],1.0)
    def test_orthogonal_vectors_have_low_directional_risk(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.safetensors'; b=Path(d)/'b.safetensors'
            save_file({'x':torch.tensor([1.,0.])},str(a)); save_file({'x':torch.tensor([0.,1.])},str(b))
            r=analyze(a,b,1e-8)
            self.assertAlmostEqual(r['summary']['weighted_cosine'],0.0,places=5)
            self.assertEqual(r['summary']['weighted_directional_risk'],0.0)
    def test_key_mismatch_fail_closed_signal(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.safetensors'; b=Path(d)/'b.safetensors'
            save_file({'x':torch.tensor([1.])},str(a)); save_file({'y':torch.tensor([1.])},str(b))
            r=analyze(a,b,1e-8)
            self.assertFalse(r['compatible_keyset'])

if __name__=='__main__': unittest.main()