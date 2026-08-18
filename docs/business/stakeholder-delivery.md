# Simulated stakeholder delivery

> **Portfolio simulation / simulated stakeholder delivery.** This memo demonstrates how a Data/BI Analyst could communicate the public Finland Rail analysis to a fictional Network Operations leadership group. It is not advice delivered to, commissioned by or validated by a real rail operator. Every quantitative statement below is traceable to committed project artifacts; no revenue, passenger or operational-impact number is invented.

## Executive summary

The current product combines two decision horizons: a live region-first exception monitor and a dated twelve-month reliability analysis. The historical snapshot contains 403,054 modelled passenger journeys from 1 August 2025 through 31 July 2026; 400,518 have a completed final arrival. At the default five-minute policy, 95.81% of completed journeys were on time, while the whole-train cancellation rate was 0.49%.

The national headline conceals material service and route variation. June 2026 was about 92.4% within five minutes. Direct Lahti → Helsinki services reached 91.0%, compared with 93.7% in the opposite direction. Among frequent end-to-end routes, Helsinki–Rovaniemi was 72.0% within five minutes. IC reached 86.8% versus 97.6% for the high-volume HL commuter type; these are different operating populations, so volumes, routes and cancellation rates must remain visible alongside the comparison.

The delivery change resolves a definition mismatch: simulated stakeholders can now apply the same 5/10/15/30-minute policy in the live region map and historical BI analysis. Serious disruption remains independently fixed at more than 15 minutes. The score is a project-defined descriptive index, not an official Fintraffic service level.

## Decision-oriented findings

| Evidence | Interpretation | Simulated stakeholder action |
| --- | --- | --- |
| 95.81% within 5 minutes; 98.91% within 15 minutes | A large share of exceptions are between policy thresholds; threshold context materially changes the headline | State the selected threshold in every review and never compare unlabeled scores |
| June 2026 about 92.4% within 5 minutes | One month is notably below the twelve-month network result | Drill into route/train-type mix and incidents; do not claim a seasonal trend from one year |
| Lahti → Helsinki 91.0% vs reverse 93.7% | Direction can be hidden by canonical route aggregation | Keep direction in the corridor page/tooltips before prioritising investigation |
| Helsinki–Rovaniemi 72.0% among frequent routes | A high-volume threshold-qualified exception deserves review | Compare monthly persistence, P90 and cancellations; do not infer cause from this aggregate |
| Freezing corridor departures 90.2% vs 92.8% with none of selected adverse conditions | There is a descriptive association in the scoped sample | Treat as a hypothesis only; strong-wind sample (32 completed journeys) is withheld and no causal claim is made |

## Recommendations

1. Use LIVE for exception triage, 24 HOURS for recent confirmation and HISTORICAL/Power BI for pattern review; never substitute one horizon for another.
2. Default leadership reporting to five minutes but make the threshold visible and use the new selector for policy sensitivity, not to choose the most flattering result.
3. Review repeated route/direction exceptions with volume, P90, cancellation and missing-data context before requesting operational action.
4. Treat missing actual timing and source freshness as reportable quality outcomes. Do not count missing observations as on time.
5. Deploy the prepared Fabric partition gate before operating a scheduled historical refresh; retain the last known-good Gold output on a failed date.

## Simulated sprint outcome

| User story | Delivered evidence | Acceptance status |
| --- | --- | --- |
| As a Service Performance Manager, I can choose 5/10/15/30 minutes on the region map | threshold maps in API/historical artifact; accessible UI control; threshold-specific problem lists | Passed automated boundary tests |
| As a Network Operations lead, I still see serious `>15` events when using a 30-minute policy | fixed `severeDelays` and ranking severity independent of threshold | Passed automated invariance test |
| As a Data Product Owner, I can block an empty or wrong-date daily partition | local/Fabric validation before publish and cache revalidation | Passed valid/invalid/non-overwrite Python tests |
| As an analyst, I can trace the request through release | CR-001, BL-001/002, traceability matrix, incident, release note and logical Git commits | Repository evidence complete |
| As a BI developer, I have an implementable native handoff | semantic model, DAX, report interaction spec, Fabric pipeline/runbook and manual checklists | Repository preparation complete; tenant execution pending |

## Limitations to present with the result

- Counts are trains/arrivals, not passengers, seats, revenue or societal impact.
- A train crossing regions is counted once in each region; regional national totals are observations, not unique trains.
- LIVE estimates can be revised and cancellations can change.
- One year supports within-period comparison, not a long-run reliability claim.
- Route/train-type/weather comparisons are descriptive and can reflect service mix or omitted factors.
- Non-empty but abnormally sparse source partitions remain a residual risk until a seasonal-volume anomaly control is agreed.

## Evidence sources

- headline and slice metrics: `artifacts/rail-summary.json` and README result table;
- source/quality counts: `artifacts/rail-quality.json`;
- regional threshold contract: `artifacts/rail-regional-history.json` and `lib/rail-monitoring.ts`;
- definitions/limitations: `docs/rail/methodology.md` and `docs/rail/monitoring.md`;
- automated delivery evidence: `tests/rail-monitoring.test.ts`, `rail/tests/test_pipeline.py` and the dated release note.
