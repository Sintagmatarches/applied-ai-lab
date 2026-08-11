"""Test the feature contract, leakage controls, and saved Python model."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import joblib
import numpy as np
import pandas as pd

from ml.common import BASELINE_FEATURES, TARGET, read_orders
from ml.model_selection import Candidate, _candidate_model, build_preprocessor
from ml.temporal_features import add_temporal_features


def synthetic_orders() -> pd.DataFrame:
    """Create a small chronological dataset with known delivery outcomes."""

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
    promised_days = np.array([12, 8, 15, 10, 20, 18])
    seller_ids = ["seller-sp", "seller-sp", "seller-rj", "seller-sp", "seller-mg", "seller-sp"]

    return pd.DataFrame(
        {
            "order_id": [f"synthetic-{index}" for index in range(6)],
            "order_purchase_timestamp": timestamps,
            "label_available_timestamp": timestamps
            + pd.to_timedelta([5, 4, 6, 3, 7, 5], unit="D"),
            "order_estimated_delivery_date": timestamps
            + pd.to_timedelta(promised_days, unit="D"),
            "purchase_year": timestamps.year,
            "purchase_month": timestamps.month,
            "purchase_day_of_week": timestamps.dayofweek + 1,
            "purchase_hour": timestamps.hour,
            "promised_delivery_days": promised_days,
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
            "primary_seller_id": seller_ids,
            "seller_ids": seller_ids,
            "seller_item_values": ["89.9", "149.9", "45", "220", "72.5", "149.9"],
            "seller_count": [1, 1, 1, 1, 1, 1],
            "category_count": [1, 1, 1, 1, 1, 1],
            "seller_zip": [10000, 10000, 20000, 10000, 30000, 10000],
            "customer_zip": [20000, 10000, 20000, 30000, 10000, 20000],
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
    """Check the most important guarantees of the ML pipeline."""

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
        order = self.enriched.iloc[[0]][BASELINE_FEATURES].copy()
        order["distance_km"] = order["distance_km"].astype(float)
        order.loc[:, "distance_km"] = np.nan
        order.loc[:, "primary_category"] = "future_category"

        transformed = self.bundle["preprocessor"].transform(order)
        probability = self.bundle["model"].predict_proba(transformed)[0, 1]

        self.assertEqual(transformed.shape[0], 1)
        self.assertTrue(np.isfinite(probability))

    def test_temporal_history_uses_available_outcomes_not_earlier_purchases(self):
        # The first late result is not known until January 3. An order on
        # January 2 must not use that future outcome in its history features.
        sample = self.frame.iloc[[0, 1, 2]].copy()
        sample.loc[:, "order_purchase_timestamp"] = pd.to_datetime(
            [
                "2018-01-01T08:00:00Z",
                "2018-01-02T18:00:00Z",
                "2018-01-04T08:00:00Z",
            ]
        )
        sample.loc[:, "label_available_timestamp"] = pd.to_datetime(
            [
                "2018-01-03T08:00:00Z",
                "2018-01-02T20:00:00Z",
                "2018-01-05T08:00:00Z",
            ]
        )
        sample.loc[:, TARGET] = [1, 0, 0]
        enriched = add_temporal_features(sample)

        self.assertAlmostEqual(
            enriched.iloc[0]["prior_global_late_rate"],
            0.05,
        )
        self.assertAlmostEqual(enriched.iloc[1]["prior_global_late_rate"], 0.05)
        self.assertAlmostEqual(
            enriched.iloc[2]["prior_global_late_rate"],
            0.5,
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["seller_state_prior_order_count_log"],
            np.log1p(1),
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["seller_state_prior_late_rate"],
            0.05,
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["primary_seller_prior_late_rate"],
            0.05,
        )

        # Changing a future label must not alter features for earlier orders.
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

    def test_multi_seller_history_aggregation_is_value_weighted_and_delayed(self):
        sample = self.frame.iloc[[0, 2, 3]].copy().reset_index(drop=True)
        sample.loc[:, "order_purchase_timestamp"] = pd.to_datetime(
            ["2018-01-01T08:00:00Z", "2018-01-01T09:00:00Z", "2018-01-03T08:00:00Z"]
        )
        sample.loc[:, "order_estimated_delivery_date"] = pd.to_datetime(
            ["2018-01-10T08:00:00Z", "2018-01-10T09:00:00Z", "2018-01-12T08:00:00Z"]
        )
        sample.loc[:, "label_available_timestamp"] = pd.to_datetime(
            ["2018-01-02T08:00:00Z", "2018-01-02T09:00:00Z", "2018-01-06T08:00:00Z"]
        )
        sample.loc[:, TARGET] = [1, 0, 0]
        sample.loc[:, "primary_seller_id"] = ["s1", "s2", "s1"]
        sample.loc[:, "seller_ids"] = ["s1", "s2", "s1|s2"]
        sample.loc[:, "seller_item_values"] = ["80", "20", "80|20"]
        sample.loc[:, "seller_count"] = [1, 1, 2]
        enriched = add_temporal_features(sample)

        s1_rate = (1 + 20 * 0.5) / 21
        s2_rate = (0 + 20 * 0.5) / 21
        self.assertAlmostEqual(
            enriched.iloc[2]["primary_seller_prior_late_rate"], s1_rate
        )
        self.assertAlmostEqual(
            enriched.iloc[2]["seller_prior_late_rate_weighted"],
            0.8 * s1_rate + 0.2 * s2_rate,
        )
        self.assertAlmostEqual(
            enriched.iloc[2]["seller_prior_late_rate_max"], s1_rate
        )
        self.assertEqual(enriched.iloc[2]["multi_seller"], 1)

    def test_temporal_feature_generation_is_reproducible_and_chronological(self):
        first = add_temporal_features(self.frame)
        second = add_temporal_features(self.frame.copy())
        columns = [
            "primary_seller_prior_late_rate",
            "seller_prior_late_rate_weighted",
            "global_order_count_30d_log",
            "business_days_in_promise_window",
        ]
        pd.testing.assert_frame_equal(first[columns], second[columns])
        self.assertTrue(np.isfinite(first[columns].to_numpy(dtype=float)).all())

    def test_saved_model_accepts_the_training_feature_contract(self):
        self.assertEqual(self.bundle["features"], BASELINE_FEATURES)
        self.assertEqual(
            self.bundle["feature_contract"]["weekday"],
            "ISO-8601 Monday=1 through Sunday=7",
        )

        order = self.enriched.iloc[[5]][BASELINE_FEATURES]
        transformed = self.bundle["preprocessor"].transform(order)
        probability = self.bundle["model"].predict_proba(transformed)[0, 1]

        self.assertTrue(np.isfinite(probability))
        self.assertGreaterEqual(probability, 0)
        self.assertLessEqual(probability, 1)

    def test_model_fit_is_reproducible(self):
        preprocessor = build_preprocessor(list(BASELINE_FEATURES))
        x = preprocessor.fit_transform(self.enriched[BASELINE_FEATURES])
        y = self.enriched[TARGET].to_numpy(dtype=int)
        candidate = Candidate(
            "reproducibility-check",
            "logistic",
            {"C": 0.3, "class_weight": None, "penalty": "l1"},
        )
        first = _candidate_model(candidate).fit(x, y).predict_proba(x)[:, 1]
        second = _candidate_model(candidate).fit(x, y).predict_proba(x)[:, 1]

        np.testing.assert_array_equal(first, second)


if __name__ == "__main__":
    unittest.main()
