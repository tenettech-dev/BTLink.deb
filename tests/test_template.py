import unittest
from pathlib import Path
from main import make_dll

ROOT=Path(__file__).resolve().parents[1]/'src'

class TemplateTests(unittest.TestCase):
    def test_personalized_at_install_time(self):
        blob=make_dll(ROOT/'BTVERIFY-template.dll','ABCDEFGHIJKL')
        self.assertNotIn(b'000000000000',blob)
        self.assertIn(b'ABCDEFGHIJKL',blob)

    def test_rejects_bad_length(self):
        with self.assertRaises(RuntimeError):make_dll(ROOT/'BTVERIFY-template.dll','ABCD')

    def test_compiled_template_is_pe32(self):
        b=(ROOT/'BTVERIFY-template.dll').read_bytes()
        self.assertEqual(b[:2],b'MZ')
        self.assertIn(b'BTVERIFY:',b)
        self.assertEqual(b.count(b'000000000000'),1)
