# Power BI report and interaction specification

> **Portfolio simulation.** This is a build-ready report contract. Visuals still require native Power BI Desktop review before they can be claimed as delivered.

## Global behaviour

- Persistent slicers: coverage date, delay threshold, train category/type; the threshold is single-select with default 5.
- Slicer sync: date/threshold across all analytical pages; weather conditions only on Weather Study.
- Visual titles include the selected threshold where relevant, for example `On-time rate (≤ 10 min)`.
- Selection interactions cross-filter supporting visuals. Disable an interaction only when the target intentionally shows a benchmark and label that benchmark.
- Tooltips always include scheduled/completed denominator, cancelled count and missing-final-actual count.
- Empty results show “No observations for current filters”, never `0.0%`.

## 1. Executive Overview

Decision: is reliability materially outside the default service picture, and where should review begin?

- KPI cards: Scheduled Journeys, Completed Journey Coverage, On-time Rate, Delay Rate, Cancellation Rate, P90 Final Delay.
- Secondary strip: selected threshold, Policy Sensitivity vs 5 Minutes, Data Coverage Start/End, Last Successful Retrieval UTC and Refresh Age Hours.
- Monthly line: On-time Rate with completed journey volume on a separate aligned panel (avoid dual-axis ambiguity).
- Ranked exception table: five routes with sufficient sample, lowest selected-threshold on-time rate, plus volume and P90.
- Narrative note: counts trains, not passengers; one-year comparison is descriptive.

## 2. Routes

- Scatter: Completed Journeys (x) vs On-time Rate (y), size by Scheduled Journeys, tooltip with P90/cancellation/directions.
- Table: route, scheduled, completed, on-time rate, cancellation, P90 and observed months.
- Filter ranking to `Route Has Sufficient Sample = 1`; still permit an explicit “show small samples” exploration toggle.

## 3. Stations

- Bar/table pair: Station On-time Rate, Scheduled Arrivals, missing actual and cancellations.
- Filter default to `Station Has Sufficient Sample = 1`.
- Conditional colour expresses the rate scale, while a separate icon/text flag expresses sample sufficiency.

## 4. Time Patterns

- Small multiples or separate charts for month, weekday, Finland-local departure hour and train type.
- Keep a common percentage scale when comparing categories; show completed volume under each view.

## 5. Lahti–Helsinki

- Direction cards and distributions, not a combined-route rate alone.
- Show arrival delay, departure delay and Median Delay Accumulation.
- Direction must remain visible in every tooltip and exported table.

## 6. Weather Study

- Show condition sample size and on-time rate, with a persistent “descriptive association, not causal” callout.
- Allow overlapping conditions and say so. Suppress/rule-mark small groups such as the 32-journey strong-wind sample.

## 7. Data Quality & Method

- Cards/table: Duplicate Journey Rows, Missing Final Actual, Missing Final Actual Rate, Completed Journey Coverage, coverage dates, last retrieval and refresh age.
- Explain journey/station grains, threshold denominator, whole vs partial cancellations, deleted-train endpoint limitation and source licences.
- Add a source-partition audit table when connected to Fabric: partition, retrieval, record count, hash and status.

## 8. Regional Operations

- Window selector: daily or governed rolling seven days; never sum pre-aggregated rates.
- Map/table: all 19 regions from `Dim Region`; Åland is labelled `No rail service`.
- Cards/tooltips: observed, measured, coverage, delayed count/share for the selected disconnected threshold, serious `>15`, cancellations, latest complete partition and Gold publication age.
- Show `Low sample` as a separate icon/text field and a Wilson interval only beside delayed share. Do not present it as score uncertainty.
- Default ranking excludes low-support regions but retains an explicit show-all option.

## Accessibility and layout review

- Use semantic titles, alt text, logical tab order and minimum WCAG AA text contrast.
- Never encode outcome by colour alone; pair with labels/icons.
- Provide a phone layout for Executive Overview and Data Quality & Method.
- Test 100%, 125% and 150% Windows display scaling and export-to-PDF page breaks.
