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
  const selected = metrics.models.xgboost.test.working_threshold;
  const comparison = [
    ["Always on time", metrics.models.dummy.test.working_threshold],
    ["Logistic regression", metrics.models.logistic.test.working_threshold],
    ["XGBoost (selected)", selected],
  ] as const;

  return (
    <LabShell activeProject="olist">
      <div className="olist-page">
        <header className="project-intro">
          <p className="eyebrow">Applied AI Lab · Project 01</p>
          <h1>Olist Delivery Delay Predictor</h1>
          <p className="intro-copy">
            A real model trained on order-time facts to estimate whether a
            delivered Olist order would arrive at least 24 hours after its
            promised date.
          </p>
          <div className="project-facts" aria-label="Project facts">
            <span>95,195 historical orders</span>
            <span>Strict chronological test</span>
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
              tune its threshold. They contain 620 one-day-late deliveries.
            </p>
          </div>

          <dl className="metric-list">
            <div>
              <dt>Precision</dt>
              <dd>{(selected.precision * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Recall</dt>
              <dd>{(selected.recall * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>F1</dt>
              <dd>{(selected.f1 * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>PR-AUC</dt>
              <dd>{(selected.pr_auc * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>ROC-AUC</dt>
              <dd>{(selected.roc_auc * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Working threshold</dt>
              <dd>{(selected.threshold * 100).toFixed(1)}%</dd>
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
              XGBoost won on validation PR-AUC. The table below reports every
              candidate on the untouched final period; these results did not
              change the selection.
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
                    <td>{result.detected_late_orders}</td>
                    <td>{result.false_warnings}</td>
                    <td>{(result.precision * 100).toFixed(1)}%</td>
                    <td>{(result.recall * 100).toFixed(1)}%</td>
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
              orders. Final test: 14,280 newest orders, ending August 2018.
              Imputation, scaling and category encoding were fitted on training
              data only.
            </p>
            <p>
              The model uses purchase calendar fields, seller and customer
              states, route, promised window, user-supplied distance, category,
              item count, values, parcel size and payment facts. It excludes
              order ID, the full timestamp, the target and every fact revealed
              after purchase.
            </p>
          </div>
        </section>

        <aside className="limitation-note">
          <h2>Important limitation</h2>
          <p>
            Performance weakened on the newest period because both order mix
            and delay prevalence changed. The calibrated model still
            overestimates the average final-period risk. This tool is an honest
            historical demonstration—not an operational SLA or guarantee.
          </p>
        </aside>
      </div>
    </LabShell>
  );
}
