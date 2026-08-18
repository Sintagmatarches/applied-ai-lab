# BL-005 — Region dimension and regional snapshot fact

> **Portfolio simulation.**

**Priority:** P2  
**State:** Ready  
**Business reason:** The application has a region-first operating view, while the prepared BI model is journey/station-first.

## Requirements

- create `Dim Region`, `Bridge Station Region` and a periodic `Fact Region Snapshot` at region × retrieval time × mode grain;
- retain Statistics Finland region code/year lineage;
- expose observed, measured, threshold counts, serious delays and cancellations as additive fields;
- prevent station-to-region many-to-many ambiguity.

## Acceptance criteria

- model diagram declares grain and relationship cardinality;
- all 19 regions appear, Åland has service flag false and no reliability score;
- regional totals reconcile to the API snapshot definition (including cross-region observation semantics);
- Direct Lake performance and RLS implications are tested in a real workspace.

**Dependency:** region lookup and Fabric deployment.  
**Definition of Done:** gold tables, semantic model, reconciliation test, performance check and report page.
