from __future__ import annotations

import unittest

import joblib
import numpy as np
import pandas as pd

from ml.common import DATA_FILE, FEATURES, TARGET, read_orders


class OlistPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = read_orders(DATA_FILE)
        cls.bundle = joblib.load("artifacts/olist-model.joblib")

    def test_reads_one_row_per_unique_order(self):
        self.assertEqual(len(self.frame), 95_195)
        self.assertEqual(self.frame["order_id"].nunique(), len(self.frame))
        self.assertEqual(set(self.frame[TARGET].unique()), {0, 1})

    def test_preprocessor_handles_missing_and_unknown_values(self):
        order = self.frame.iloc[[0]][FEATURES].copy()
        order.loc[:, "distance_km"] = np.nan
        order.loc[:, "primary_category"] = "future_category"
        transformed = self.bundle["preprocessor"].transform(order)
        self.assertEqual(transformed.shape[0], 1)
        probability = self.bundle["model"].predict_proba(transformed)[0, 1]
        self.assertTrue(np.isfinite(probability))

    def test_saved_model_returns_a_calibrated_probability(self):
        timestamp = pd.Timestamp("2018-07-16T14:30:00Z")
        order = pd.DataFrame(
            [
                {
                    "purchase_year": timestamp.year,
                    "purchase_month": timestamp.month,
                    "purchase_day_of_week": ((timestamp.dayofweek + 1) % 7) + 1,
                    "purchase_hour": timestamp.hour,
                    "promised_delivery_days": 18,
                    "seller_state": "SP",
                    "customer_state": "RJ",
                    "route": "SP → RJ",
                    "same_state": 0,
                    "distance_km": 430,
                    "item_count": 2,
                    "primary_category": "health_beauty",
                    "total_item_value": 149.9,
                    "total_freight_value": 24.9,
                    "total_weight_g": 1600,
                    "total_volume_cm3": 12000,
                    "primary_payment_type": "credit_card",
                    "payment_installments": 4,
                }
            ]
        )[FEATURES]
        transformed = self.bundle["preprocessor"].transform(order)
        raw = self.bundle["model"].predict(
            transformed, output_margin=True
        ).reshape(-1, 1)
        probability = self.bundle["calibrator"].predict_proba(raw)[0, 1]
        self.assertAlmostEqual(probability, 0.15583432, places=6)


if __name__ == "__main__":
    unittest.main()
