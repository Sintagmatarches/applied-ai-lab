# Prioritised analytics backlog

> **Portfolio simulation.** These are issue-ready work items for the simulated Network Operations Analytics team. “Implemented” means the repository contains verifiable code/tests after this delivery; it does not imply use by a real organisation.

| ID | Priority | Work item | State | Depends on |
| --- | --- | --- | --- | --- |
| BL-001 | P1 | [Regional delay-policy selector (5/10/15/30)](https://github.com/Sintagmatarches/applied-ai-lab/issues/4) | Implemented; issue closed with commit evidence | Existing regional monitor |
| BL-002 | P1 | [Reject incomplete Digitraffic daily partitions](https://github.com/Sintagmatarches/applied-ai-lab/issues/5) | Implemented; issue closed with commit evidence | Historical ingestion |
| BL-003 | P2 | [Add minimum-sample confidence state to region status](https://github.com/Sintagmatarches/applied-ai-lab/issues/6) | Implemented; repository acceptance complete | BL-001 |
| BL-004 | P2 | [Add data-freshness SLA alerting and runbook](https://github.com/Sintagmatarches/applied-ai-lab/issues/7) | Repository implementation complete; Fabric alert/drill pending | BL-002, Fabric deployment |
| BL-005 | P2 | [Add region dimension and regional snapshot fact to BI model](https://github.com/Sintagmatarches/applied-ai-lab/issues/8) | Repository model complete; Direct Lake/RLS tenant evidence pending | Region lookup, Fabric deployment |
| BL-006 | P2 | [Persist a governed rolling 7-day regional view](https://github.com/Sintagmatarches/applied-ai-lab/issues/9) | Implemented; repository acceptance complete | BL-002, BL-005 |
| BL-007 | P3 | [Add release-over-release KPI regression check](https://github.com/Sintagmatarches/applied-ai-lab/issues/10) | Implemented; issue closed with fixture evidence | Stable gold tables |

Detailed acceptance criteria are stored in [`backlog/`](backlog/) and mirrored in the linked GitHub Issues. Issues #4 and #5 were created from the specs and then honestly closed with the real implementation commits; no backdated issue history is claimed.

## Prioritisation method

- **P1:** incorrect decision or invalid publication risk; release-blocking.
- **P2:** material decision-support or operational-governance improvement.
- **P3:** maintainability or analytical maturity after the core control is stable.

All items use the repository-wide [Definition of Done](requirements.md#definition-of-done).
