"use client";

import { FormEvent, useState } from "react";
import {
  BRAZILIAN_STATE_CODES,
  OLIST_PAYMENT_TYPES,
  type OlistPaymentType,
} from "../../lib/olist-input-contract";

type Prediction = {
  risk_score: number;
  risk_level: "low" | "medium" | "high";
  decision: string;
  factors: Array<{
    name: string;
    effect: string;
    risk_score_point_change: number;
    explanation: string;
  }>;
  model_version: string;
  high_risk_score: number;
  display_note: string;
  disclaimer: string;
};

type ErrorResponse = {
  error?: string;
  issues?: string[];
};

type PredictionDomain = {
  minimum: string;
  maximum: string;
};

const paymentLabels: Record<OlistPaymentType, string> = {
  credit_card: "Credit card",
  boleto: "Boleto",
  voucher: "Voucher",
  debit_card: "Debit card",
};

const categories = [
  "bed_bath_table",
  "health_beauty",
  "sports_leisure",
  "furniture_decor",
  "computers_accessories",
  "housewares",
  "watches_gifts",
  "telephony",
  "garden_tools",
  "auto",
  "toys",
  "cool_stuff",
  "perfumery",
  "baby",
  "electronics",
  "stationery",
  "fashion_bags_accessories",
  "pet_shop",
  "office_furniture",
  "luggage_accessories",
  "construction_tools_construction",
  "home_appliances",
  "musical_instruments",
  "books_general_interest",
  "food",
  "audio",
];

const example = {
  seller_state: "SP",
  customer_state: "RJ",
  promised_delivery_days: "18",
  primary_category: "health_beauty",
  item_count: "2",
  total_item_value: "149.90",
  total_freight_value: "24.90",
  distance_km: "430",
  total_weight_g: "1600",
  total_volume_cm3: "12000",
  primary_payment_type: "credit_card",
  payment_installments: "4",
  purchase_timestamp: "2018-07-16T14:30",
};

function utcInputValue(timestamp: string): string {
  return timestamp.replace("+00:00", "Z").slice(0, 16);
}

export function OlistPredictor({ domain }: { domain: PredictionDomain }) {
  const [form, setForm] = useState(example);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  function update(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrors([]);
    setPrediction(null);

    const payload = {
      ...form,
      promised_delivery_days: Number(form.promised_delivery_days),
      item_count: Number(form.item_count),
      total_item_value: Number(form.total_item_value),
      total_freight_value: Number(form.total_freight_value),
      distance_km: Number(form.distance_km),
      total_weight_g: Number(form.total_weight_g),
      total_volume_cm3: Number(form.total_volume_cm3),
      payment_installments: Number(form.payment_installments),
      purchase_timestamp: new Date(
        `${form.purchase_timestamp}:00.000Z`,
      ).toISOString(),
    };

    try {
      const response = await fetch("/api/olist/predict", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as Prediction & ErrorResponse;
      if (!response.ok) {
        setErrors(body.issues?.length ? body.issues : [body.error ?? "Prediction failed."]);
        return;
      }
      setPrediction(body);
    } catch {
      setErrors(["The prediction service is temporarily unavailable."]);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="predictor-section" aria-labelledby="predictor-title">
      <div className="section-heading">
        <p className="eyebrow">Live model · server-side inference</p>
        <h2 id="predictor-title">Check one order</h2>
        <p>
          Enter facts known when the order is placed. Distance is entered
          explicitly because two state codes cannot determine it honestly.
        </p>
      </div>

      <form className="predictor-form" onSubmit={submit}>
        <div className="form-grid">
          <label>
            Seller state
            <select
              value={form.seller_state}
              onChange={(event) => update("seller_state", event.target.value)}
            >
              {BRAZILIAN_STATE_CODES.map((state) => (
                <option key={state}>{state}</option>
              ))}
            </select>
          </label>
          <label>
            Customer state
            <select
              value={form.customer_state}
              onChange={(event) => update("customer_state", event.target.value)}
            >
              {BRAZILIAN_STATE_CODES.map((state) => (
                <option key={state}>{state}</option>
              ))}
            </select>
          </label>
          <label>
            Promised delivery window, days
            <input
              type="number"
              min="1"
              max="180"
              step="0.01"
              required
              value={form.promised_delivery_days}
              onChange={(event) =>
                update("promised_delivery_days", event.target.value)
              }
            />
          </label>
          <label>
            Shipping distance, km
            <input
              type="number"
              min="0"
              max="10000"
              step="0.01"
              required
              value={form.distance_km}
              onChange={(event) => update("distance_km", event.target.value)}
            />
          </label>
          <label>
            Product category
            <input
              list="olist-categories"
              required
              pattern="[A-Za-z0-9_]+"
              value={form.primary_category}
              onChange={(event) =>
                update("primary_category", event.target.value)
              }
            />
            <datalist id="olist-categories">
              {categories.map((category) => (
                <option key={category} value={category} />
              ))}
            </datalist>
          </label>
          <label>
            Item count
            <input
              type="number"
              min="1"
              max="50"
              step="1"
              required
              value={form.item_count}
              onChange={(event) => update("item_count", event.target.value)}
            />
          </label>
          <label>
            Item value, BRL
            <input
              type="number"
              min="0"
              max="50000"
              step="0.01"
              required
              value={form.total_item_value}
              onChange={(event) =>
                update("total_item_value", event.target.value)
              }
            />
          </label>
          <label>
            Freight value, BRL
            <input
              type="number"
              min="0"
              max="5000"
              step="0.01"
              required
              value={form.total_freight_value}
              onChange={(event) =>
                update("total_freight_value", event.target.value)
              }
            />
          </label>
          <label>
            Parcel weight, g
            <input
              type="number"
              min="0"
              max="250000"
              step="1"
              required
              value={form.total_weight_g}
              onChange={(event) =>
                update("total_weight_g", event.target.value)
              }
            />
          </label>
          <label>
            Parcel volume, cm³
            <input
              type="number"
              min="0"
              max="2000000"
              step="1"
              required
              value={form.total_volume_cm3}
              onChange={(event) =>
                update("total_volume_cm3", event.target.value)
              }
            />
          </label>
          <label>
            Payment method
            <select
              value={form.primary_payment_type}
              onChange={(event) =>
                update("primary_payment_type", event.target.value)
              }
            >
              {OLIST_PAYMENT_TYPES.map((paymentType) => (
                <option key={paymentType} value={paymentType}>
                  {paymentLabels[paymentType]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Installments
            <input
              type="number"
              min="0"
              max="36"
              step="1"
              required
              value={form.payment_installments}
              onChange={(event) =>
                update("payment_installments", event.target.value)
              }
            />
          </label>
          <label className="wide-field">
            Purchase date and time
            <input
              type="datetime-local"
              required
              min={utcInputValue(domain.minimum)}
              max={utcInputValue(domain.maximum)}
              value={form.purchase_timestamp}
              onChange={(event) =>
                update("purchase_timestamp", event.target.value)
              }
            />
            <small>
              UTC, within the historical Olist range{" "}
              {utcInputValue(domain.minimum)} – {utcInputValue(domain.maximum)}
            </small>
          </label>
        </div>

        <div className="form-actions">
          <button type="submit" disabled={pending}>
            {pending ? "Calculating…" : "Estimate delay risk"}
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setForm(example);
              setPrediction(null);
              setErrors([]);
            }}
          >
            Load example order
          </button>
        </div>
      </form>

      {errors.length > 0 && (
        <div className="form-errors" role="alert">
          <strong>Prediction was not calculated.</strong>
          <ul>
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {prediction && (
        <article
          className={`prediction-result risk-${prediction.risk_level}`}
          aria-live="polite"
        >
          <div>
            <p className="eyebrow">Relative risk score</p>
            <strong className="probability">
              {prediction.risk_score.toFixed(0)}
              <small>/100</small>
            </strong>
            <p className="risk-label">
              {prediction.risk_level} risk · {prediction.decision}
            </p>
          </div>
          <div>
            <h3>Sensitivity scenarios</h3>
            <p>
              Each row replaces one feature group with a fixed reference order.
              These comparisons are not causal attributions.
            </p>
            <ul className="factor-list">
              {prediction.factors.map((factor) => (
                <li key={factor.name}>
                  <strong>{factor.name}</strong>
                  <span>
                    {factor.effect} by about{" "}
                    {factor.risk_score_point_change.toFixed(1)} risk-score
                    points compared with the fixed reference order
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <footer>
            <span>Model {prediction.model_version}</span>
            <span>{prediction.display_note}</span>
            <span>{prediction.disclaimer}</span>
          </footer>
        </article>
      )}
    </section>
  );
}
