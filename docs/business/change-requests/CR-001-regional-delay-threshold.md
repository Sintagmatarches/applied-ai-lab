# CR-001 — Align regional monitoring to selectable delay policy

> **Simulated stakeholder request.** The requester and approval below are portfolio-simulation roles, not real people or organisations.

## Request

**From:** Simulated Service Performance Manager  
**To:** Simulated Data/BI Analyst  
**Priority:** P1  
**Requested outcome:** “The monthly reliability pack can be discussed at 5, 10, 15 or 30 minutes, but the live region map only says delayed after 5 minutes. Let the operating team choose the same threshold on the map and keep severe disruption independently defined at over 15 minutes.”

## Analyst clarification

The analyst translated the request into four decisions:

1. The source snapshot returns counts for all four thresholds so switching is instant and does not increase API load.
2. Delayed count/share, affected problem lists and the 45% delay-share component of the score use the selected threshold.
3. Serious delays remain strictly greater than 15 minutes, regardless of selection.
4. The selected threshold is visible in national and regional labels and the method note.

## Impact analysis

| Area | Expected impact |
| --- | --- |
| Business interpretation | Higher thresholds produce fewer “delayed” trains; users must not compare scores without the threshold context |
| API contract | Add threshold count/share maps; retain legacy 5-minute scalar fields during transition |
| Historical artifact | Rebuild threshold fields from the same completed source partitions; no target period change |
| UI | Add accessible segmented control; derive score/status locally from selected threshold |
| Tests | Cover 12-minute and 18-minute examples, severe invariance, no-service and no-data |
| Documentation | Update KPI contract, methodology, data dictionary, change log and traceability |
| Deployment | Cache-bust application assets/API URLs and deploy exact tested commit |

## Acceptance criteria

The acceptance criteria are maintained in [BL-001](../backlog/BL-001-regional-threshold.md). No requirement changes the underlying source, observation grain, cancellation logic or historical period.

## Validation and sign-off

**Portfolio-simulation sign-off rule:** automated tests must prove the threshold boundary behaviour and the repository must show the exact implementation/test/document links in the [traceability matrix](../traceability.md). Final release status and executed commands are recorded in the dated release note; this document does not pre-claim completion.
