"""
Unit tests for FlippAdFetcher with mocked API responses.
"""

import unittest
from unittest.mock import patch
from src.fetcher import FlippAdFetcher


class TestFlippAdFetcher(unittest.TestCase):

    def setUp(self):
        self.fetcher = FlippAdFetcher()

    @patch.object(FlippAdFetcher, "_get_json")
    def test_get_flyers_for_zip(self, mock_get_json):
        mock_get_json.return_value = {
            "flyers": [
                {
                    "id": 8131286,
                    "merchant": "Tom Thumb",
                    "merchant_id": 2381,
                    "name": "Weekly Ad",
                    "postal_code": "00000",
                    "valid_from": "2026-09-16T00:00:00-04:00",
                    "valid_to": "2026-09-22T23:59:59-04:00",
                    "width": 10737.0,
                    "height": 2560.0,
                },
                {
                    "id": 7777777,
                    "merchant": "Kroger",
                    "merchant_id": 100,
                    "name": "Weekly Circular",
                    "postal_code": "00000",
                    "valid_from": "2026-09-16T00:00:00-04:00",
                    "valid_to": "2026-09-22T23:59:59-04:00",
                },
            ]
        }

        flyers = self.fetcher.get_flyers_for_zip("00000", merchant_filter="Tom Thumb")
        self.assertEqual(len(flyers), 1)
        self.assertEqual(flyers[0].id, 8131286)
        self.assertEqual(flyers[0].merchant, "Tom Thumb")

    @patch.object(FlippAdFetcher, "_get_json")
    def test_get_flyer_pages_and_items_coordinate_mapping(self, mock_get_json):
        mock_get_json.return_value = {
            "pages": [
                {"id": 1, "page": 1, "left": 0.0, "right": 1463.0, "top": 0.0, "bottom": -2560.0},
                {"id": 2, "page": 2, "left": 1463.0, "right": 3000.0, "top": 0.0, "bottom": -2560.0},
            ],
            "items": [
                {
                    "id": 101,
                    "name": "Lucerne Eggs",
                    "price": 0.97,
                    "left": 500.0,
                    "right": 800.0,
                    "top": -500.0,
                    "bottom": -700.0,
                    "brand": "Lucerne",
                },
                {
                    "id": 102,
                    "name": "Laundry Detergent",
                    "price": 9.99,
                    "left": 2000.0,
                    "right": 2500.0,
                    "top": -500.0,
                    "bottom": -700.0,
                    "brand": "Tide",
                },
            ],
        }

        pages, items = self.fetcher.get_flyer_pages_and_items(8131286, front_page_only=True)
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(items), 1)  # only page 1 item
        self.assertEqual(items[0].name, "Lucerne Eggs")
        self.assertEqual(items[0].page_number, 1)
        self.assertTrue(items[0].is_front_page)


if __name__ == "__main__":
    unittest.main()
