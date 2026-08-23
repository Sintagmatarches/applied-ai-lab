# User actions remaining

Code, automated tests, public web deployment and GitHub traceability are completed by Codex in this delivery. The following actions require the user's own licensed tools, credentials or professional judgement:

1. Sign in to Databricks Free Edition and complete the prepared [`databricks/README.md`](../../databricks/README.md) workspace/Volume/notebook steps if hosted evidence is desired; local and CI Spark/Delta evidence already exists.
2. Complete and evidence the native [Microsoft Fabric tasks](fabric.md) in an approved Fabric tenant if Fabric deployment is desired.
3. Complete and evidence the native [Power BI tasks](power-bi.md) in Power BI Desktop and the target tenant.
4. Review the finished Power BI report visually and approve tenant sharing; this requires human judgement and organisational permissions.
5. If a hosted private Tender AI runtime is wanted, authenticate to the user's Azure subscription, publish `Dockerfile.tender-ai` to a user-owned registry, supply that image and the private Ollama endpoint to `infra/azure-tender`, then run the reviewed Terraform plan. The public portfolio and local/container runtime do not depend on this optional deployment.

Do not mark Power BI/Fabric deployment complete in the portfolio until the listed native evidence exists.

For the regional-governance issues specifically, the only remaining acceptance evidence is:

- Issue #7: bind the shared freshness thresholds to a real Fabric alert destination, execute and record a stale→recovery runbook drill, and capture the observable dashboard state.
- Issue #8: load the governed region dimension/bridge/daily/7d facts in Direct Lake, record performance results, and explicitly approve the documented no-RLS decision in the tenant.
