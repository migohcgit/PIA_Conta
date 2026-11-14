import unittest
from src.ingestion.common import parse_number

class IngestionTests(unittest.TestCase):
    def test_us_number(self):
        self.assertEqual(parse_number("1,234.56"), 1234.56)

    def test_european_number(self):
        self.assertEqual(parse_number("1.234,56"), 1234.56)

    def test_parentheses_negative(self):
        self.assertEqual(parse_number("(250)"), -250.0)

if __name__ == "__main__":
    unittest.main()
