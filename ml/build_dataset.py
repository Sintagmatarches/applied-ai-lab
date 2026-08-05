from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DATA_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/olist_orders_model.csv")
MANIFEST_FILE = Path("data/olist-build-manifest.json")
SOURCE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
SOURCE_LICENSE = "CC BY-NC-SA 4.0"
SECONDS_PER_DAY = 86_400

SOURCE_FILES = (
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
)

EXPECTED_SOURCE_SHA256 = {
    "olist_customers_dataset.csv": "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2",
    "olist_geolocation_dataset.csv": "b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6",
    "olist_orders_dataset.csv": "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf",
    "olist_order_items_dataset.csv": "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279",
    "olist_order_payments_dataset.csv": "4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0",
    "olist_products_dataset.csv": "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc",
    "olist_sellers_dataset.csv": "1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e",
    "product_category_name_translation.csv": "a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_sources(
    raw_dir: Path, verify_checksums: bool = True
) -> dict[str, pd.DataFrame]:
    missing = [name for name in SOURCE_FILES if not (raw_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing Olist source files: "
            + ", ".join(missing)
            + ". Download the public Kaggle dataset first."
        )
    if verify_checksums:
        changed = [
            name
            for name, expected in EXPECTED_SOURCE_SHA256.items()
            if _sha256(raw_dir / name) != expected
        ]
        if changed:
            raise ValueError(
                "Olist source checksums changed: "
                + ", ".join(changed)
                + ". Review the upstream dataset and update the pinned hashes intentionally."
            )
    return {Path(name).stem: pd.read_csv(raw_dir / name) for name in SOURCE_FILES}


def _utc_timestamp(values: pd.Series) -> pd.Series:
    # The source contains naive Brazilian wall-clock strings. The project
    # deliberately preserves those calendar values and marks them UTC so that
    # Python and JavaScript derive identical year/month/weekday/hour features.
    return pd.to_datetime(values, utc=True, errors="coerce")


def _robust_zip_coordinates(geolocation: pd.DataFrame) -> pd.DataFrame:
    valid = geolocation[
        geolocation["geolocation_lat"].between(-35, 6)
        & geolocation["geolocation_lng"].between(-75, -30)
    ]
    return (
        valid.groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(
            latitude=("geolocation_lat", "median"),
            longitude=("geolocation_lng", "median"),
        )
        .rename(columns={"geolocation_zip_code_prefix": "zip_code_prefix"})
    )


def _haversine_km(
    latitude_a: pd.Series,
    longitude_a: pd.Series,
    latitude_b: pd.Series,
    longitude_b: pd.Series,
) -> pd.Series:
    radius_km = 6_371.0088
    lat_a = np.radians(latitude_a.astype(float))
    lon_a = np.radians(longitude_a.astype(float))
    lat_b = np.radians(latitude_b.astype(float))
    lon_b = np.radians(longitude_b.astype(float))
    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a
    value = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_a) * np.cos(lat_b) * np.sin(delta_lon / 2) ** 2
    )
    return pd.Series(
        2 * radius_km * np.arcsin(np.sqrt(value)),
        index=latitude_a.index,
    )


def _aggregate_items(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    items = tables["olist_order_items_dataset"].copy()
    products = tables["olist_products_dataset"].copy()
    sellers = tables["olist_sellers_dataset"].copy()
    translation = tables["product_category_name_translation"].copy()

    products = products.merge(
        translation,
        on="product_category_name",
        how="left",
        validate="many_to_one",
    )
    products["primary_category"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    )
    products["product_volume_cm3"] = (
        products["product_length_cm"]
        * products["product_height_cm"]
        * products["product_width_cm"]
    )

    item_details = items.merge(
        products[
            [
                "product_id",
                "primary_category",
                "product_weight_g",
                "product_volume_cm3",
            ]
        ],
        on="product_id",
        how="left",
        validate="many_to_one",
    ).merge(
        sellers[["seller_id", "seller_state", "seller_zip_code_prefix"]],
        on="seller_id",
        how="left",
        validate="many_to_one",
    )

    primary = (
        item_details.sort_values(
            [
                "order_id",
                "price",
                "freight_value",
                "order_item_id",
                "seller_id",
                "product_id",
            ],
            ascending=[True, False, False, True, True, True],
            kind="stable",
        )
        .drop_duplicates("order_id")
        .rename(columns={"seller_zip_code_prefix": "seller_zip"})[
            [
                "order_id",
                "seller_state",
                "seller_zip",
                "primary_category",
            ]
        ]
    )

    totals = item_details.groupby("order_id", as_index=False).agg(
        item_count=("order_item_id", "size"),
        total_item_value=("price", "sum"),
        total_freight_value=("freight_value", "sum"),
        total_weight_g=("product_weight_g", lambda values: values.sum(min_count=1)),
        total_volume_cm3=(
            "product_volume_cm3",
            lambda values: values.sum(min_count=1),
        ),
    )
    return totals.merge(primary, on="order_id", validate="one_to_one")


def _aggregate_payments(payments: pd.DataFrame) -> pd.DataFrame:
    primary = (
        payments.sort_values(
            ["order_id", "payment_value", "payment_sequential", "payment_type"],
            ascending=[True, False, True, True],
            kind="stable",
        )
        .drop_duplicates("order_id")
        .rename(columns={"payment_type": "primary_payment_type"})
    )
    totals = payments.groupby("order_id", as_index=False).agg(
        payment_count=("payment_sequential", "size"),
        total_payment_value=("payment_value", "sum"),
    )
    return totals.merge(
        primary[["order_id", "primary_payment_type", "payment_installments"]],
        on="order_id",
        validate="one_to_one",
    )


def build_dataset(
    raw_dir: Path = RAW_DATA_DIR, verify_checksums: bool = True
) -> tuple[pd.DataFrame, dict]:
    tables = _read_sources(raw_dir, verify_checksums=verify_checksums)
    orders = tables["olist_orders_dataset"].copy()
    source_order_count = len(orders)
    orders = orders.loc[orders["order_status"].eq("delivered")].copy()
    for column in (
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ):
        orders[column] = _utc_timestamp(orders[column])
    orders = orders.dropna(
        subset=[
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
    )

    customers = tables["olist_customers_dataset"][
        ["customer_id", "customer_state", "customer_zip_code_prefix"]
    ].rename(columns={"customer_zip_code_prefix": "customer_zip"})
    frame = (
        orders.merge(
            customers,
            on="customer_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            _aggregate_items(tables), on="order_id", how="inner", validate="one_to_one"
        )
        .merge(
            _aggregate_payments(tables["olist_order_payments_dataset"]),
            on="order_id",
            how="left",
            validate="one_to_one",
        )
    )

    coordinates = _robust_zip_coordinates(tables["olist_geolocation_dataset"])
    seller_coordinates = coordinates.rename(
        columns={
            "zip_code_prefix": "seller_zip",
            "latitude": "seller_latitude",
            "longitude": "seller_longitude",
        }
    )
    customer_coordinates = coordinates.rename(
        columns={
            "zip_code_prefix": "customer_zip",
            "latitude": "customer_latitude",
            "longitude": "customer_longitude",
        }
    )
    frame = frame.merge(
        seller_coordinates,
        on="seller_zip",
        how="left",
        validate="many_to_one",
    ).merge(
        customer_coordinates,
        on="customer_zip",
        how="left",
        validate="many_to_one",
    )
    frame["distance_km"] = _haversine_km(
        frame["seller_latitude"],
        frame["seller_longitude"],
        frame["customer_latitude"],
        frame["customer_longitude"],
    )

    purchase = frame["order_purchase_timestamp"]
    frame["purchase_year"] = purchase.dt.year
    frame["purchase_month"] = purchase.dt.month
    frame["purchase_day_of_week"] = purchase.dt.dayofweek + 1
    frame["purchase_hour"] = purchase.dt.hour
    frame["promised_delivery_days"] = (
        frame["order_estimated_delivery_date"] - purchase
    ).dt.total_seconds() / SECONDS_PER_DAY
    frame["same_state"] = frame["seller_state"].eq(frame["customer_state"]).astype(int)
    frame["route"] = frame["seller_state"] + " → " + frame["customer_state"]
    frame["late_1d"] = (
        frame["order_delivered_customer_date"]
        > frame["order_estimated_delivery_date"] + pd.Timedelta(days=1)
    ).astype(int)
    frame["label_available_timestamp"] = frame["order_delivered_customer_date"]
    frame["primary_category"] = frame["primary_category"].fillna("__missing__")
    frame["primary_payment_type"] = frame["primary_payment_type"].fillna("__missing__")

    frame = frame.loc[frame["promised_delivery_days"] > 0].copy()
    columns = [
        "order_id",
        "order_purchase_timestamp",
        "label_available_timestamp",
        "purchase_year",
        "purchase_month",
        "purchase_day_of_week",
        "purchase_hour",
        "promised_delivery_days",
        "same_state",
        "distance_km",
        "item_count",
        "total_item_value",
        "total_freight_value",
        "total_weight_g",
        "total_volume_cm3",
        "payment_installments",
        "seller_state",
        "customer_state",
        "route",
        "primary_category",
        "primary_payment_type",
        "late_1d",
    ]
    frame = (
        frame[columns]
        .sort_values(["order_purchase_timestamp", "order_id"], kind="stable")
        .reset_index(drop=True)
    )

    manifest = {
        "source": SOURCE_URL,
        "license": SOURCE_LICENSE,
        "timestamp_policy": (
            "Naive source wall-clock values are parsed as UTC so Python and "
            "JavaScript use identical calendar components."
        ),
        "primary_item_policy": (
            "Highest item price, then freight value, then stable item/seller/product IDs."
        ),
        "source_orders": source_order_count,
        "model_rows": int(len(frame)),
        "late_orders": int(frame["late_1d"].sum()),
        "source_files": {
            name: {
                "sha256": _sha256(raw_dir / name),
                "bytes": (raw_dir / name).stat().st_size,
            }
            for name in SOURCE_FILES
        },
    }
    return frame, manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the point-in-time Olist order-level training table."
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE)
    args = parser.parse_args()

    frame, manifest = build_dataset(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False, date_format="%Y-%m-%dT%H:%M:%S.%fZ")
    manifest["output"] = str(args.output).replace("\\", "/")
    manifest["output_sha256"] = _sha256(args.output)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Built {len(frame):,} orders ({frame['late_1d'].mean():.2%} late); "
        f"dataset: {args.output}; manifest: {args.manifest}"
    )


if __name__ == "__main__":
    main()
