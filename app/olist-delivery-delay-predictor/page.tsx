import type { Metadata } from "next";
import { LabShell } from "../lab-shell";
import metrics from "../../artifacts/metrics.json";
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
            <span>95,195 historical orders</span>
            <span>4 sequential backtests</span>
            <span>Server-side prediction</span>
          </div>
        </header>

        <OlistPredictor />

        <section className="evidence-section" aria-labelledby="results-title">
          <div className="section-heading">
            <p className="eyebrow">Held-out evidence</p>
            <h2 id="results-title">What the final time test showed</h2>
            <p>
              The newest 14,280 orders were never used to select the model or
              choose its calibration. They contain 620 one-day-late
              deliveries. Metrics below describe the 10% highest-risk group.
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
            <h2 id="comparison-title">Selection used validation only</h2>
            <p>
              Logistic regression had the best average and stability-adjusted
              PR-AUC across four earlier sequential backtests. The table below
              reports every candidate on the untouched final period.
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
              Training: 66,636 older orders. Validation: 14,279 following
              orders reserved for calibration. Final test: 14,280 newest
              orders, ending August 2018. Model choice came from four earlier
              rolling time checks. Imputation, scaling and category encoding
              were fitted on training data only.
            </p>
            <p>
              The model adds prior state, route and category delay rates,
              recent 7/30/90-day route activity, state experience, freight
              ratio, delivery-window-to-distance ratio and season. Each
              historical value excludes the order’s date and every later date.
            </p>
          </div>
        </section>

        <aside className="limitation-note">
          <h2>Important limitation</h2>
          <p>
            The separate calibration period did not transfer reliably: average
            final-period probability remained too high. The live result
            therefore uses a relative risk score from 0 to 100, not an exact
            probability. The export has seller state but no seller ID, so
            state-level history is the honest available proxy.
          </p>
        </aside>
      </div>
    </LabShell>
  );
}
