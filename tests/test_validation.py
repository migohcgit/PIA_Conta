import unittest
from src.validation.validator import validate_data

class ValidationTests(unittest.TestCase):
    def test_missing_assets_warning(self):
        issues = validate_data({"total_liabilities": 10})
        self.assertTrue(any(i["code"] == "MISSING_TOTAL_ASSETS" for i in issues))

if __name__ == "__main__":
    unittest.main()
