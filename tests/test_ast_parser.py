"""
test_ast_parser.py
Unit tests for the lexical Tokenizer and DealASTParser pipeline.
"""

import unittest
from src.normalizer.tokenizer import tokenize, TokenType
from src.normalizer.ast_parser import DealASTParser


class TestASTParser(unittest.TestCase):
    def setUp(self):
        self.parser = DealASTParser()

    def test_tokenize_semantic_types(self):
        text = "Lucerne Chunk, Shredded or Sliced Cheese 24-32 oz"
        tokens = tokenize(text)
        types = [t.type for t in tokens]
        values = [t.value for t in tokens]

        self.assertEqual(types[0], TokenType.BRAND)
        self.assertEqual(values[0], "Lucerne")
        self.assertEqual(types[1], TokenType.WORD)
        self.assertEqual(values[1], "Chunk")
        self.assertEqual(types[2], TokenType.COMMA)
        self.assertEqual(types[3], TokenType.WORD)
        self.assertEqual(values[3], "Shredded")
        self.assertEqual(types[4], TokenType.COORD)
        self.assertEqual(types[5], TokenType.WORD)
        self.assertEqual(values[5], "Sliced")
        self.assertEqual(types[6], TokenType.HEAD_NOUN)
        self.assertEqual(values[6], "Cheese")
        self.assertEqual(types[7], TokenType.UNIT_SPEC)
        self.assertEqual(values[7], "24-32 oz")

    def test_right_distribution_shared_head_noun_and_size(self):
        text = "Lucerne Chunk, Shredded or Sliced Cheese 24-32 oz"
        items = self.parser.disaggregate(text)
        self.assertEqual(
            items,
            [
                "Lucerne Chunk Cheese 24-32 oz",
                "Lucerne Shredded Cheese 24-32 oz",
                "Lucerne Sliced Cheese 24-32 oz",
            ],
        )

    def test_right_distribution_two_item_shared_head_noun(self):
        text = "O Organics Red or Green Grapes"
        items = self.parser.disaggregate(text)
        self.assertEqual(
            items,
            [
                "O Organics Red Grapes",
                "O Organics Green Grapes",
            ],
        )

    def test_left_distribution_shared_product(self):
        text = "Dole or Our Brand Salad Blend or Kit"
        items = self.parser.disaggregate(text)
        self.assertEqual(
            items,
            [
                "Dole Salad Blend or Kit",
                "Our Brand Salad Blend or Kit",
            ],
        )

    def test_brand_pair_shared_size(self):
        text = "Doritos, Tostitos 6-13 oz"
        items = self.parser.disaggregate(text)
        self.assertEqual(
            items,
            [
                "Doritos 6-13 oz",
                "Tostitos 6-13 oz",
            ],
        )

    def test_right_distribution_sugar_varieties(self):
        text = "Our Brand Confectioners' or Brown Sugar"
        items = self.parser.disaggregate(text)
        self.assertEqual(
            items,
            [
                "Our Brand Confectioners' Sugar",
                "Our Brand Brown Sugar",
            ],
        )

    def test_complex_bundle_segmentation(self):
        text = "Nature's Promise Greenhouse Grown Dole or Our Brand Salad Blend or Kit, Bolthouse Dressing or NatureSweet Cherub or Golden Cherub Tomatoes"
        items = self.parser.disaggregate(text)
        self.assertEqual(len(items), 6)
        self.assertEqual(items[0], "Nature's Promise Greenhouse Grown Salad Blend or Kit")
        self.assertEqual(items[1], "Dole Salad Blend or Kit")
        self.assertEqual(items[2], "Our Brand Salad Blend or Kit")
        self.assertEqual(items[3], "Bolthouse Dressing")
        self.assertEqual(items[4], "NatureSweet Cherub Tomatoes")
        self.assertEqual(items[5], "NatureSweet Golden Cherub Tomatoes")


if __name__ == "__main__":
    unittest.main()
