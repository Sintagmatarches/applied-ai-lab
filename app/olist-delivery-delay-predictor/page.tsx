import type { Metadata } from "next";
import { LabShell } from "../lab-shell";
import metrics from "../../artifacts/metrics.json";
import model from "../../artifacts/olist-model.json";
import { OlistPredictor } from "./predictor";

export const metadata: Metadata = {
  title: "Olist Delivery Delay Predictor",
  description:
    "A live, server-scored demonstration model for Olist delivery-delay risk.",
};

export default function OlistDeliveryDelayPredictor() {
  const selected = metrics.final_test.top_risk_groups["10%"];
  const comparison = [
    ["Logistic regression (selected)", metrics.final_candidate_test.logistic],
    ["XGBoost", metrics.final_candidate_test.xgboost],
    ["CatBoost", metrics.final_candidate_test.catboost],
  ] as const;

  return (
    <LabShell activeProject="olist">
      <div className="olist-page">
        <header className="project-intro">
          <p className="eyebrow">Applied AI Lab · Project 01</p>
          <h1>Olist Delivery Delay Predictor</h1>
          <p className="intro-copy">
            A real model trained on order-time facts and strictly earlier
            order history to rank delivery-delay risk without presenting an
            unreliable probability as precise.
          </p>
          <div className="project-facts" aria-label="Project facts">
            <span>
              {(
                metrics.splits.train.rows +
                metrics.splits.calibration.rows +
                metrics.splits.test.rows
              ).toLocaleString("en-US")} historical orders
            </span>
            <span>4 sequential backtests</span>
            <span>Server-side prediction</span>
          </div>
        </header>

        <OlistPredictor
          domain={{
            minimum: model.prediction_domain.purchase_timestamp_min,
            maximum: model.prediction_domain.purchase_timestamp_max,
          }}
        />

        <section className="evidence-section" aria-labelledby="results-title">
          <div className="section-heading">
            <p className="eyebrow">Held-out evidence</p>
            <h2 id="results-title">What the final time test showed</h2>
            <p>
              The newest {metrics.final_test.rows.toLocaleString("en-US")} orders
              were never used to select the model or choose its calibration.
              They contain {metrics.final_test.late_orders.toLocaleString("en-US")}{" "}
              one-day-late deliveries.
              Precision, Delay capture, False / found, and the confusion matrix
              are calculated for the 10% of test orders with the highest risk
              score. PR-AUC and ROC-AUC are calculated across the complete final
              test period.
            </p>
          </div>

          <dl className="metric-list">
            <div>
              <dt>Precision</dt>
              <dd>{(selected.precision * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Delay capture</dt>
              <dd>{(selected.recall * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>False / found</dt>
              <dd>
                {selected.false_warnings_per_detected_late_order.toFixed(1)}
              </dd>
            </div>
            <div>
              <dt>PR-AUC</dt>
              <dd>{(metrics.final_test.pr_auc * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>PR-AUC lift</dt>
              <dd>{metrics.final_test.pr_auc_lift.toFixed(2)}×</dd>
            </div>
            <div>
              <dt>ROC-AUC</dt>
              <dd>{(metrics.final_test.roc_auc * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Evaluated group</dt>
              <dd>Top 10%</dd>
            </div>
          </dl>

          <div className="confusion-copy">
            <p>
              <strong>{selected.detected_late_orders}</strong> real late
              orders detected
            </p>
            <p>
              <strong>{selected.false_warnings}</strong> false warnings
            </p>
            <p>
              <strong>{selected.missed_late_orders}</strong> late orders missed
            </p>
            <p>
              <strong>{selected.correct_safe_orders}</strong> on-time orders
              correctly left unflagged
            </p>
          </div>
        </section>

        <section className="evidence-section" aria-labelledby="comparison-title">
          <div className="section-heading">
            <p className="eyebrow">Model comparison</p>
            <h2 id="comparison-title">
              Selection used rolling time validation
            </h2>
            <p>
              Logistic regression had the best stability-adjusted delay capture
              in a fixed top-10% review queue across four earlier sequential
              backtests. PR-AUC lift over each period&apos;s prevalence and ROC-AUC
              broke ties. The table reports every candidate on the untouched
              final period.
            </p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Detected</th>
                  <th>False warnings</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>PR-AUC</th>
                  <th>PR lift</th>
                  <th>ROC-AUC</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map(([name, result]) => (
                  <tr key={name}>
                    <th>{name}</th>
                    <td>
                      {result.top_risk_groups["10%"].detected_late_orders}
                    </td>
                    <td>
                      {result.top_risk_groups["10%"].false_warnings}
                    </td>
                    <td>
                      {(
                        result.top_risk_groups["10%"].precision * 100
                      ).toFixed(1)}
                      %
                    </td>
                    <td>
                      {(result.top_risk_groups["10%"].recall * 100).toFixed(
                        1,
                      )}
                      %
                    </td>
                    <td>{(result.pr_auc * 100).toFixed(1)}%</td>
                    <td>{result.pr_auc_lift.toFixed(2)}×</td>
                    <td>{(result.roc_auc * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="method-section" aria-labelledby="method-title">
          <div>
            <p className="eyebrow">Method</p>
            <h2 id="method-title">No future information</h2>
          </div>
          <div className="method-copy">
            <p>
              Training: {metrics.splits.train.rows.toLocaleString("en-US")} older
              orders. Calibration:{" "}
              {metrics.splits.calibration.rows.toLocaleString("en-US")} following
              orders. Final test: {metrics.splits.test.rows.toLocaleString("en-US")}{" "}
              newest orders, ending August 2018. Model choice came from four
              earlier rolling time checks. Imputation, scaling and category
              encoding were fitted on training data only.
            </p>
            <p>
              The model adds prior state, route and category delay rates,
              recent 7/30/90-day route activity, state experience, freight
              ratio, delivery-window-to-distance ratio and season. Order counts
              use only earlier purchase days. Historical delay
              rates are stricter: they include only orders already delivered on
              an earlier day, so a pending order cannot leak its future label.
            </p>
          </div>
        </section>

        <aside className="limitation-note">
          <h2>Important limitation</h2>
          <p>
            Calibration did not transfer reliably to the newest period, so the
            live result uses a relative risk score from 0 to 100 rather than an
            exact probability. Seller and category describe the deterministic
            highest-value item in multi-seller orders; the public form uses
            seller state rather than seller ID. Sensitivity scenarios are
            comparisons with a fixed reference order, not causal explanations.
          </p>
        </aside>
      </div>
    </LabShell>
  );
}
