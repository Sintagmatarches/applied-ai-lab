# Prioritised analytics backlog

> **Portfolio simulation.** These are issue-ready work items for the simulated Network Operations Analytics team. “Implemented” means the repository contains verifiable code/tests after this delivery; it does not imply use by a real organisation.

| ID | Priority | Work item | State | Depends on |
| --- | --- | --- | --- | --- |
| BL-001 | P1 | Regional delay-policy selector (5/10/15/30) | Implemented in this delivery | Existing regional monitor |
| BL-002 | P1 | Reject incomplete Digitraffic daily partitions | Implemented in this delivery | Historical ingestion |
| BL-003 | P2 | Add minimum-sample confidence state to region status | Ready | BL-001 |
| BL-004 | P2 | Add data-freshness SLA alerting and runbook | Ready | BL-002, Fabric deployment |
| BL-005 | P2 | Add region dimension and regional snapshot fact to BI model | Ready | Region lookup, Fabric deployment |
| BL-006 | P2 | Persist a governed rolling 7-day regional view | Ready | BL-002, BL-005 |
| BL-007 | P3 | Add release-over-release KPI regression check | Ready | Stable gold tables |

Detailed acceptance criteria are stored in [`backlog/`](backlog/) and are suitable for GitHub Issues. Repository issue links are added there when created.

## Prioritisation method

- **P1:** incorrect decision or invalid publication risk; release-blocking.
- **P2:** material decision-support or operational-governance improvement.
- **P3:** maintainability or analytical maturity after the core control is stable.

All items use the repository-wide [Definition of Done](requirements.md#definition-of-done).
