# Delivery traceability

> **Portfolio simulation.** The business roles and request are simulated; paths and automated test evidence refer to real repository artifacts.

This matrix is completed as implementation lands. A row is not evidence of completion unless its referenced test exists and passes.

| Requirement | Backlog / request | Implementation | Automated evidence | Delivery evidence |
| --- | --- | --- | --- | --- |
| BR-01 regional operating picture | Existing system | `lib/rail-monitoring.ts`, `regional-monitor.tsx` | `tests/rail-monitoring.test.ts` | `docs/rail/methodology.md` |
| BR-02 selectable threshold | [BL-001 / issue #4](https://github.com/Sintagmatarches/applied-ai-lab/issues/4) / CR-001 | `lib/rail-monitoring.ts`, `regional-monitor.tsx`, `rail/build_regional_history.py` | threshold-policy test in `tests/rail-monitoring.test.ts` | CR-001, release note |
| BR-03 fixed serious definition | BL-001 / CR-001 | threshold maps plus fixed `severeDelays` | threshold-policy test in `tests/rail-monitoring.test.ts` | KPI contract |
| BR-04 exception drill-down | BL-001 / CR-001 | threshold-specific station/route rankings | threshold-policy test in `tests/rail-monitoring.test.ts` | Data dictionary |
| BR-05 current vs completed evidence | Existing system | `lib/rail-monitoring.ts`, API route | `tests/rail-monitoring.test.ts` | `docs/rail/methodology.md` |
| BR-06 honest live failure | Existing system | API route, regional monitor | live API failure test | Architecture/monitoring docs |
| BR-07 partition quality gate | [BL-002 / issue #5](https://github.com/Sintagmatarches/applied-ai-lab/issues/5) / INC-001 | `rail/pipeline.py`, Fabric notebooks 01/02 | three partition-gate tests in `rail/tests/test_pipeline.py` | `docs/incidents/INC-001-empty-daily-partition.md` |
| BR-08 reproducible history | Existing system | `rail/pipeline.py` | `rail/tests/test_pipeline.py` | README, rail docs |
| BR-09 governed BI delivery | [#7](https://github.com/Sintagmatarches/applied-ai-lab/issues/7), [#8](https://github.com/Sintagmatarches/applied-ai-lab/issues/8), [#9](https://github.com/Sintagmatarches/applied-ai-lab/issues/9) | Fabric/Power BI specifications | Local syntax/tests where available; tenant validation manual | Power BI/Fabric/manual-task docs |
| DE-01 executable incremental Lakehouse | [issue #11](https://github.com/Sintagmatarches/applied-ai-lab/issues/11) | `rail/lakehouse/`, contracts, Delta control/fact/mart tables | `rail/lakehouse/tests/`, real execution and KPI reconciliation artifacts | data-platform report, lineage and runbook |

Native Power BI/Fabric deployment evidence remains explicitly manual because this repository has no tenant credentials or Power BI Desktop session.
