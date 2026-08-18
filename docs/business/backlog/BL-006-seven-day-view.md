# BL-006 — Governed rolling 7-day regional view

> **Portfolio simulation.**

**Priority:** P2  
**State:** Ready  
**Business reason:** A 7-day view separates one-off live disruption from an emerging persistent issue.

## Requirements

- use persisted validated partitions, not a browser fan-out across seven daily APIs;
- recompute every snapshot from a documented watermark and late-arriving-data window;
- label retrieval time and coverage gaps;
- reuse the threshold and score contract from BL-001.

## Acceptance criteria

- all seven expected dates pass BL-002 before publication;
- reruns are idempotent and late-arriving corrections replace affected partitions;
- totals reconcile to the component days;
- API and UI show an unavailable/partial state rather than silently shortening the window.

**Dependencies:** BL-002 and BL-005.  
**Definition of Done:** incremental gold build, reconciliation tests, API/UI mode and runbook.
