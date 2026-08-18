# BL-007 — Release-over-release KPI regression check

> **Portfolio simulation.**

**Priority:** P3  
**State:** Ready  
**Business reason:** A schema or metric change can pass unit tests yet materially shift headline results.

## Requirements

- store a small approved fixture with expected KPI outputs;
- compare overall, route, station and threshold results during CI;
- require an explicit fixture update and release note for intentional definition changes;
- avoid treating normal new-source-data movement as a code regression.

## Acceptance criteria

- CI fails on an unapproved denominator or threshold change;
- diff output identifies affected KPI and dimension slice;
- fixture provenance and update procedure are documented;
- test contains no production secrets or large raw-data payload.

**Dependency:** stable gold schemas.  
**Definition of Done:** versioned fixture, deterministic test, review rule and documented update path.
