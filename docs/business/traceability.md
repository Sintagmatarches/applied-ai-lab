# Delivery traceability

> **Portfolio simulation.** The business roles and request are simulated; paths and automated test evidence refer to real repository artifacts.

This matrix is completed as implementation lands. A row is not evidence of completion unless its referenced test exists and passes.

| Requirement | Backlog / request | Implementation | Automated evidence | Delivery evidence |
| --- | --- | --- | --- | --- |
| BR-01 regional operating picture | Existing system | `lib/rail-monitoring.ts`, `regional-monitor.tsx` | `tests/rail-monitoring.test.ts` | `docs/rail/methodology.md` |
| BR-02 selectable threshold | BL-001 / CR-001 | Pending implementation | Pending | CR-001, release note |
| BR-03 fixed serious definition | BL-001 / CR-001 | Pending implementation | Pending | KPI contract |
| BR-04 exception drill-down | BL-001 / CR-001 | Pending implementation | Pending | Data dictionary |
| BR-05 current vs completed evidence | Existing system | `lib/rail-monitoring.ts`, API route | `tests/rail-monitoring.test.ts` | `docs/rail/methodology.md` |
| BR-06 honest live failure | Existing system | API route, regional monitor | live API failure test | Architecture/monitoring docs |
| BR-07 partition quality gate | BL-002 / INC-001 | Pending implementation | Pending | Incident record |
| BR-08 reproducible history | Existing system | `rail/pipeline.py` | `rail/tests/test_pipeline.py` | README, rail docs |
| BR-09 governed BI delivery | BL-004–BL-006 | Fabric/Power BI specifications | Local syntax/tests where available; tenant validation manual | Power BI/Fabric/manual-task docs |

The final delivery updates every “Pending implementation” cell to an exact file and test reference; unresolved tenant work remains explicitly manual.
