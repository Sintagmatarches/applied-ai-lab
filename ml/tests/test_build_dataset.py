"""Test deterministic joins and feature rules in the dataset builder."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from ml.build_dataset import SOURCE_FILES, build_dataset


class BuildDatasetTest(unittest.TestCase):
    """Build a tiny set of linked Olist tables and verify the output row."""

    def test_builds_deterministic_order_level_features(self):
        # The fixture includes two items, two sellers, and two payments so the
        # primary-record and aggregation rules are visible in one small case.
        with TemporaryDirectory() as directory:
            raw = Path(directory)
            tables = {
                "olist_orders_dataset.csv": pd.DataFrame(
                    [
                        {
                            "order_id": "o1",
                            "customer_id": "c1",
                            "order_status": "delivered",
                            "order_purchase_timestamp": "2018-07-16 10:00:00",
                            "order_approved_at": "2018-07-16 11:00:00",
                            "order_delivered_carrier_date": "2018-07-17 10:00:00",
                            "order_delivered_customer_date": "2018-07-23 10:00:00",
                            "order_estimated_delivery_date": "2018-07-20 10:00:00",
                        },
                        {
                            "order_id": "ignored",
                            "customer_id": "c1",
                            "order_status": "canceled",
                            "order_purchase_timestamp": "2018-07-17 10:00:00",
                            "order_approved_at": None,
                            "order_delivered_carrier_date": None,
                            "order_delivered_customer_date": None,
                            "order_estimated_delivery_date": "2018-07-22 10:00:00",
                        },
                    ]
                ),
                "olist_customers_dataset.csv": pd.DataFrame(
                    [
                        {
                            "customer_id": "c1",
                            "customer_unique_id": "u1",
                            "customer_zip_code_prefix": 20000,
                            "customer_city": "rio",
                            "customer_state": "RJ",
                        }
                    ]
                ),
                "olist_order_items_dataset.csv": pd.DataFrame(
                    [
                        {
                            "order_id": "o1",
                            "order_item_id": 1,
                            "product_id": "p1",
                            "seller_id": "s1",
                            "shipping_limit_date": "2018-07-17 00:00:00",
                            "price": 40.0,
                            "freight_value": 8.0,
                        },
                        {
                            "order_id": "o1",
                            "order_item_id": 2,
                            "product_id": "p2",
                            "seller_id": "s2",
                            "shipping_limit_date": "2018-07-17 00:00:00",
                            "price": 90.0,
                            "freight_value": 12.0,
                        },
                    ]
                ),
                "olist_products_dataset.csv": pd.DataFrame(
                    [
                        {
                            "product_id": "p1",
                            "product_category_name": "beleza_saude",
                            "product_name_lenght": 10,
                            "product_description_lenght": 20,
                            "product_photos_qty": 1,
                            "product_weight_g": 500,
                            "product_length_cm": 10,
                            "product_height_cm": 10,
                            "product_width_cm": 10,
                        },
                        {
                            "product_id": "p2",
                            "product_category_name": "esporte_lazer",
                            "product_name_lenght": 10,
                            "product_description_lenght": 20,
                            "product_photos_qty": 1,
                            "product_weight_g": 1000,
                            "product_length_cm": 20,
                            "product_height_cm": 10,
                            "product_width_cm": 10,
                        },
                    ]
                ),
                "olist_sellers_dataset.csv": pd.DataFrame(
                    [
                        {
                            "seller_id": "s1",
                            "seller_zip_code_prefix": 10000,
                            "seller_city": "sao paulo",
                            "seller_state": "SP",
                        },
                        {
                            "seller_id": "s2",
                            "seller_zip_code_prefix": 30000,
                            "seller_city": "belo horizonte",
                            "seller_state": "MG",
                        },
                    ]
                ),
                "olist_order_payments_dataset.csv": pd.DataFrame(
                    [
                        {
                            "order_id": "o1",
                            "payment_sequential": 1,
                            "payment_type": "voucher",
                            "payment_installments": 1,
                            "payment_value": 20.0,
                        },
                        {
                            "order_id": "o1",
                            "payment_sequential": 2,
                            "payment_type": "credit_card",
                            "payment_installments": 4,
                            "payment_value": 130.0,
                        },
                    ]
                ),
                "olist_geolocation_dataset.csv": pd.DataFrame(
                    [
                        {
                            "geolocation_zip_code_prefix": 10000,
                            "geolocation_lat": -23.55,
                            "geolocation_lng": -46.63,
                            "geolocation_city": "sao paulo",
                            "geolocation_state": "SP",
                        },
                        {
                            "geolocation_zip_code_prefix": 20000,
                            "geolocation_lat": -22.91,
                            "geolocation_lng": -43.17,
                            "geolocation_city": "rio",
                            "geolocation_state": "RJ",
                        },
                        {
                            "geolocation_zip_code_prefix": 30000,
                            "geolocation_lat": -19.92,
                            "geolocation_lng": -43.94,
                            "geolocation_city": "belo horizonte",
                            "geolocation_state": "MG",
                        },
                    ]
                ),
                "product_category_name_translation.csv": pd.DataFrame(
                    [
                        {
                            "product_category_name": "beleza_saude",
                            "product_category_name_english": "health_beauty",
                        },
                        {
                            "product_category_name": "esporte_lazer",
                            "product_category_name_english": "sports_leisure",
                        },
                    ]
                ),
            }
            # Reviews are not used, but the official archive includes them and
            # source completeness is intentionally checked.
            tables["olist_order_reviews_dataset.csv"] = pd.DataFrame(
                columns=[
                    "review_id",
                    "order_id",
                    "review_score",
                    "review_comment_title",
                    "review_comment_message",
                    "review_creation_date",
                    "review_answer_timestamp",
                ]
            )
            for name in SOURCE_FILES:
                tables[name].to_csv(raw / name, index=False)

            frame, manifest = build_dataset(raw, verify_checksums=False)

        self.assertEqual(len(frame), 1)
        order = frame.iloc[0]
        self.assertEqual(order["seller_state"], "MG")
        self.assertEqual(order["primary_seller_id"], "s2")
        self.assertEqual(order["seller_ids"], "s1|s2")
        self.assertEqual(order["seller_item_values"], "40|90")
        self.assertEqual(order["seller_count"], 2)
        self.assertEqual(order["category_count"], 2)
        self.assertEqual(order["seller_zip"], 30000)
        self.assertEqual(order["customer_zip"], 20000)
        self.assertEqual(order["primary_category"], "sports_leisure")
        self.assertEqual(order["primary_payment_type"], "credit_card")
        self.assertEqual(order["item_count"], 2)
        self.assertEqual(order["total_item_value"], 130.0)
        self.assertEqual(order["total_freight_value"], 20.0)
        self.assertEqual(order["total_weight_g"], 1500.0)
        self.assertEqual(order["total_volume_cm3"], 3000.0)
        self.assertEqual(order["purchase_day_of_week"], 1)
        self.assertEqual(order["route"], "MG → RJ")
        self.assertEqual(order["late_1d"], 1)
        self.assertEqual(
            order["label_available_timestamp"].isoformat(),
            "2018-07-23T10:00:00+00:00",
        )
        self.assertEqual(
            order["order_estimated_delivery_date"].isoformat(),
            "2018-07-20T10:00:00+00:00",
        )
        self.assertGreater(order["distance_km"], 0)
        self.assertEqual(manifest["model_rows"], 1)


if __name__ == "__main__":
    unittest.main()
