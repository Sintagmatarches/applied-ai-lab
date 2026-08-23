# BL-004 — Data-freshness SLA alert and runbook

> **Portfolio simulation.**

**Priority:** P2  
**State:** Repository implementation complete; tenant acceptance pending
**Business reason:** Users need to distinguish a quiet railway from a stale pipeline.

## Requirements

- agree separate live API and historical pipeline freshness targets;
- persist last successful source and gold publication timestamps;
- surface Fresh / Warning / Stale status in BI and monitoring views;
- route alert ownership and recovery steps through a runbook.

## Acceptance criteria

- simulated stale timestamps trigger warning and stale states in tests;
- no alert resolves until a complete validated partition is published;
- Power BI and Fabric specifications use one freshness contract;
- alert recipients and escalation timing are documented.

**Dependencies:** BL-002 and a Fabric tenant deployment.  
**Definition of Done:** agreed SLA, automated check, runbook drill and observable dashboard state.

The shared freshness contract, persisted publication timestamp, executable GitHub workflow, UI state and recovery runbook are complete. This item remains open until an authenticated Fabric alert destination, drill and observable tenant dashboard are evidenced.
