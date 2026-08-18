# BL-003 — Minimum-sample confidence state

> **Portfolio simulation.**

**Priority:** P2  
**State:** Ready  
**Business reason:** A region with one observed train should not receive the same visual confidence as a region with hundreds.

## Requirements

- define sample sufficiency separately for LIVE, 24 HOURS and HISTORICAL;
- show measured/observed coverage and a low-sample badge;
- do not hide results or silently change denominators;
- validate cut-offs on historical distributions before adoption.

## Acceptance criteria

- thresholds and rationale are documented;
- low-sample state is keyboard/screen-reader visible and does not overwrite `No data`/`No rail service`;
- tests cover boundary counts;
- stakeholder delivery distinguishes score from confidence.

**Dependency:** BL-001.  
**Definition of Done:** implementation, tests, method note and release evidence are complete.
