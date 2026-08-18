# Microsoft Fabric native completion tasks

These steps require a licensed Fabric tenant, capacity and workspace permissions unavailable to the repository environment.

1. Create Development, Test and Production workspaces/capacities according to the organisation's governance and create/attach `lh_finland_rail`.
2. Import the two notebook sources, mark the documented parameters as a Fabric parameter cell and validate default Lakehouse binding.
3. Build `pl_finland_rail_daily` exactly from [`fabric/pipeline-spec.md`](../../fabric/pipeline-spec.md), including failure paths, rolling three-day correction window, notifications and watermark-after-Gold rule.
4. Run a one-day smoke load, a closed multi-day backfill, an idempotent rerun and the INC-001 empty-partition drill in Development/Test. Capture audit and reconciliation evidence.
5. Configure Git integration/deployment pipelines, target-stage Lakehouse binding rules and approval gates; then deploy to Production only after Test evidence passes.
6. Connect the Direct Lake semantic model, schedule/trigger downstream refresh as applicable and assign operational alert ownership.

Completion evidence to attach: workspace/item IDs (without secrets), pipeline run history, quality-gate failure screenshot/log, Gold reconciliation results, deployment history and named operational owner.
