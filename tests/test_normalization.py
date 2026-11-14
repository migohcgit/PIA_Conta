import unittest
from src.normalization.normalizer import canonicalize

class NormalizationTests(unittest.TestCase):
    def test_english_alias(self):
        self.assertEqual(canonicalize("TOTAL ASSETS"), "total_assets")

    def test_spanish_alias(self):
        self.assertEqual(canonicalize("Activo circulante"), "current_assets")

    def test_unknown_label(self):
        self.assertIsNone(canonicalize("A label not in the catalog"))

if __name__ == "__main__":
    unittest.main()
