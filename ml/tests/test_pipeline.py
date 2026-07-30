from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import joblib
import numpy as np
import pandas as pd

from ml.common import FEATURES, TARGET, read_orders
from ml.temporal_features import add_temporal_features


def synthetic_orders() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2017-09-04T10:00:00Z",
            "2017-09-12T14:30:00Z",
            "2017-10-03T09:15:00Z",
            "2018-01-08T16:45:00Z",
            "2018-03-19T11:20:00Z",
            "2018-07-16T14:30:00Z",
        ],
        utc=True,
    )
    seller_states = ["SP", "SP", "RJ", "SP", "MG", "SP"]
    customer_states = ["RJ", "SP", "RJ", "MG", "SP", "RJ"]
    targets = [0, 1, 0, 1, 0, 0]

    return pd.DataFrame(
        {
            "order_id": [f"synthetic-{index}" for index in range(6)],
            "order_purchase_timestamp": timestamps,
            "purchase_year": timestamps.year,
            "purchase_month": timestamps.month,
            "purchase_day_of_week": timestamps.dayofweek + 1,
            "purchase_hour": timestamps.hour,
            "promised_delivery_days": [12, 8, 15, 10, 20, 18],
            "same_state": [
                int(seller == customer)
                for seller, customer in zip(
                    seller_states,
                    customer_states,
                    strict=True,
                )
            ],
            "distance_km": [430, 50, 20, 580, 610, 430],
            "item_count": [1, 2, 1, 3, 1, 2],
            "total_item_value": [89.9, 149.9, 45.0, 220.0, 72.5, 149.9],
            "total_freight_value": [18.0, 24.9, 9.0, 32.0, 21.0, 24.9],
            "total_weight_g": [800, 1600, 500, 2400, 900, 1600],
            "total_volume_cm3": [6000, 12000, 4000, 18000, 7000, 12000],
            "payment_installments": [2, 4, 1, 5, 2, 4],
            "seller_state": seller_states,
            "customer_state": customer_states,
            "route": [
                f"{seller} → {customer}"
                for seller, customer in zip(
                    seller_states,
                    customer_states,
                    strict=True,
                )
            ],
            "primary_category": [
                "health_beauty",
                "health_beauty",
                "books_general_interest",
                "furniture_decor",
                "sports_leisure",
                "health_beauty",
            ],
            "primary_payment_type": [
                "credit_card",
                "credit_card",
                "voucher",
                "credit_card",
                "boleto",
                "credit_card",
            ],
            TARGET: targets,
        }
    )


class OlistPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = synthetic_orders()
        cls.enriched = add_temporal_features(cls.frame)
        cls.bundle = joblib.load("artifacts/olist-model.joblib")

    def test_read_orders_validates_and_sorts_a_csv(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            self.frame.sample(frac=1, random_state=7).to_csv(
                path,
                index=False,
            )
            loaded = read_orders(path)

        self.assertEqual(len(loaded), len(self.frame))
        self.assertEqual(loaded["order_id"].nunique(), len(loaded))
        self.assertEqual(set(loaded[TARGET].unique()), {0, 1})
        self.assertTrue(loaded["order_purchase_timestamp"].is_monotonic_increasing)

    def test_preprocessor_handles_missing_and_unknown_values(self):
        order = self.enriched.iloc[[0]][FEATURES].copy()
        order["distance_km"] = order["distance_km"].astype(float)
        order.loc[:, "distance_km"] = np.nan
        order.loc[:, "primary_category"] = "future_category"

        transformed = self.bundle["preprocessor"].transform(order)
        probability = self.bundle["model"].predict_proba(transformed)[0, 1]

        self.assertEqual(transformed.shape[0], 1)
        self.assertTrue(np.isfinite(probability))

    def test_temporal_history_excludes_same_day_and_future_labels(self):
        sample = self.frame.iloc[[0, 1, 2]].copy()
        sample.loc[:, "order_purchase_timestamp"] = pd.to_datetime(
            [
                "2018-01-01T08:00:00Z",
                "2018-01-01T18:00:00Z",
                "2018-01-02T08:00:00Z",
            ]
        )
        sample.loc[:, TARGET] = [1, 0, 0]
        enriched = add_temporal_features(sample)

        self.assertAlmostEqual(
            enriched.iloc[0]["prior_global_late_rate"],
            0.05,
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["prior_global_late_rate"],
            0.05,
        )
        self.assertAlmostEqual(
            enriched.iloc[2]["prior_global_late_rate"],
            0.5,
        )

        changed_future = sample.copy()
        changed_future.loc[2, TARGET] = 1
        changed = add_temporal_features(changed_future)
        self.assertAlmostEqual(
            enriched.iloc[0]["seller_state_prior_late_rate"],
            changed.iloc[0]["seller_state_prior_late_rate"],
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["route_prior_late_rate"],
            changed.iloc[1]["route_prior_late_rate"],
        )

    def test_saved_model_accepts_the_training_feature_contract(self):
        self.assertEqual(self.bundle["features"], FEATURES)

        order = self.enriched.iloc[[5]][FEATURES]
        transformed = self.bundle["preprocessor"].transform(order)
        probability = self.bundle["model"].predict_proba(transformed)[0, 1]

        self.assertTrue(np.isfinite(probability))
        self.assertGreaterEqual(probability, 0)
        self.assertLessEqual(probability, 1)


if __name__ == "__main__":
    unittest.main()
