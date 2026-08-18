# Release 2026-08-18 — Analytics delivery workflow

> **Portfolio simulation.** CR-001 and INC-001 model a simulated stakeholder/change/incident workflow. The code, tests, artifacts, commits and production deployment listed here are real repository work performed on the release date.

## PR-style summary

**Problem:** The regional monitor fixed “delayed” at more than five minutes while the historical experience already supported 5/10/15/30; historical ingestion also accepted a syntactically valid empty daily array.

**Change:** Add threshold maps to live/historical regional aggregation, a client-side selector and threshold-specific problem rankings; keep serious delay fixed above 15 minutes. Add pre-publication and cache-read partition validation locally and equivalent completeness gates to the Fabric notebook design.

**Analytics delivery:** Add simulated requirements, backlog, change request, incident, stakeholder memo, traceability, Power BI semantic/report/DAX pack, Fabric pipeline/runbook and credentialed manual-task boundary.

## Acceptance evidence

- `npm run typecheck` — passed during implementation.
- `npm run test:rail` — 9 tests passed, including valid/invalid/non-overwrite partition controls.
- `npx tsx --test tests/rail-monitoring.test.ts` — 8 tests passed, including threshold boundaries and fixed serious delay.
- `python -m rail.build_regional_history` — rebuilt all 365 partitions and wrote the threshold-aware historical artifact.
- `npm test` — production build, 10 rendered/API tests and 17 TypeScript parity/rail tests passed after the final dependency update.
- `npm run test:ml` — 8 ML tests plus Python→TypeScript parity passed.
- `npm run typecheck` and `npm run lint` — passed.
- `npm audit` — 0 vulnerabilities after updating Vinext/Cloudflare/RSC/Wrangler and `nanoid` through normal package resolution, without overrides.
- Production deployment status is recorded after the exact commit is pushed; it is not pre-claimed here.

## Compatibility and risk

Legacy scalar `delayedTrains`, `delayedShare`, `disruptionScore`, `reliabilityScore`, `status`, `problemStations` and `problemRoutes` remain the five-minute view. New `*ByThreshold` fields extend the contract. A higher selected threshold will mechanically lower the delayed-share component and can improve the project-defined score; the UI labels the choice to prevent unlabeled comparison.

No source period, train population, cancellation logic, region geometry, historical denominator or public-data attribution changed.

The dependency refresh moved Vinext from `0.0.50` to `1.0.0-beta.6` and Cloudflare build tooling to patched releases to remove audit findings in `image-size`, `undici` and `nanoid`. The complete production build and test suite passed after the update.

## Rollback

The site deployment can return to the previous version through the hosting release history. Data artifacts are Git-versioned. Do not roll back only the UI while leaving an incompatible API artifact; revert the implementation commit as one contract change. A rejected source partition already retains the previous valid cache/Gold output.
