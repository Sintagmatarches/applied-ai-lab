# Release 2026-08-23 — Rail KPI regression contract

> **Portfolio simulation.** The fixture, test and CI execution are real repository controls; no external production release process is implied.

KPI contract: rail-kpi-v1  
Fixture SHA-256: 4744fa57a74ba6e2fc982ace7d95329aecce854cdd2a01db5fb28163421c1f89

## Approved analytical contract

The fixed synthetic fixture protects overall, route and station outputs at the 5-, 10-, 15- and 30-minute thresholds. It covers early arrivals, exact threshold boundaries, serious delays, missing actuals and cancellations without using live source data.

CI executes the contract through `python -m unittest discover -s rail/tests`. A regression reports the full analytical path, expected value and actual value for every changed field.

## Intentional definition changes

1. Explain the definition and denominator change in a new dated release note.
2. Update the deterministic input or approved output in `rail/tests/fixtures/kpi-regression-v1.json`.
3. Recalculate the canonical SHA-256 of the fixture `input` and `expected` objects.
4. Point `approval.release_note` at the new note and record that hash in both places.
5. Run the rail tests and review the field-level diff before approval.

Normal movement in live Digitraffic data never changes this fixture and therefore cannot be mistaken for a code regression.
