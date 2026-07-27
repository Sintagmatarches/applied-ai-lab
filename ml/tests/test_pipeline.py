from __future__ import annotations

import unittest

import joblib
import numpy as np
import pandas as pd

from ml.common import DATA_FILE, FEATURES, TARGET, read_orders
from ml.temporal_features import add_temporal_features


class OlistPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = read_orders(DATA_FILE)
        cls.enriched = add_temporal_features(cls.frame)
        cls.bundle = joblib.load("artifacts/olist-model.joblib")

    def test_reads_one_row_per_unique_order(self):
        self.assertEqual(len(self.frame), 95_195)
        self.assertEqual(self.frame["order_id"].nunique(), len(self.frame))
        self.assertEqual(set(self.frame[TARGET].unique()), {0, 1})

    def test_preprocessor_handles_missing_and_unknown_values(self):
        order = self.enriched.iloc[[0]][FEATURES].copy()
        order.loc[:, "distance_km"] = np.nan
        order.loc[:, "primary_category"] = "future_category"
        transformed = self.bundle["preprocessor"].transform(order)
        self.assertEqual(transformed.shape[0], 1)
        probability = self.bundle["model"].predict_proba(transformed)[0, 1]
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
            enriched.iloc[0]["prior_global_late_rate"], 0.05
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["prior_global_late_rate"], 0.05
        )
        self.assertAlmostEqual(
            enriched.iloc[2]["prior_global_late_rate"], 0.5
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

    def test_saved_model_returns_a_calibrated_probability(self):
        route = self.frame.loc[
            (self.frame["seller_state"] == "SP")
            & (self.frame["customer_state"] == "RJ"),
            "route",
        ].iloc[0]
        order = self.frame.iloc[0].to_dict()
        order.update(
            {
                "order_id": "synthetic",
                "order_purchase_timestamp": pd.Timestamp(
                    "2018-07-16T14:30:00Z"
                ),
                "purchase_year": 2018,
                "purchase_month": 7,
                "purchase_day_of_week": 2,
                "purchase_hour": 14,
                "promised_delivery_days": 18,
                "seller_state": "SP",
                "customer_state": "RJ",
                "route": route,
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
                "late_1d": 0,
            }
        )
        combined = pd.concat(
            [self.frame, pd.DataFrame([order])],
            ignore_index=True,
        ).sort_values(["order_purchase_timestamp", "order_id"])
        prepared = add_temporal_features(combined)
        model_order = prepared.loc[
            prepared["order_id"] == "synthetic", FEATURES
        ]
        transformed = self.bundle["preprocessor"].transform(model_order)
        raw = self.bundle["model"].decision_function(transformed)[0]
        probability = 1 / (1 + np.exp(-raw))
        self.assertAlmostEqual(probability, 0.03453398, places=6)


if __name__ == "__main__":
    unittest.main()
