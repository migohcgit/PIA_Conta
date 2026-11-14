import unittest
from src.interpretation.interpreter import interpret_ratio

class InterpretationTests(unittest.TestCase):
    def test_combined_ratio_under_100(self):
        self.assertIn("Below 100%", interpret_ratio("combined_ratio", .95))

    def test_missing_value(self):
        self.assertIn("could not be calculated", interpret_ratio("current_ratio", None))

if __name__ == "__main__":
    unittest.main()
