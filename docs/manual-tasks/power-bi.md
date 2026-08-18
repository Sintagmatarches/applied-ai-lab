# Power BI native completion tasks

These are the only Power BI steps that cannot be completed or honestly verified from the repository environment.

1. In a supported Power BI Desktop version, connect to the deployed Fabric Gold tables using the chosen Direct Lake mode and implement [`power-bi/semantic-model.md`](../../power-bi/semantic-model.md).
2. Add [`power-bi/measures.dax`](../../power-bi/measures.dax), build the seven pages in [`power-bi/report-spec.md`](../../power-bi/report-spec.md), then reconcile the six fixed evidence points before styling.
3. Save as a Power BI Project (`.pbip`) from Desktop developer mode and commit the generated, validated project files; do not hand-create the structure.
4. Review accessibility, phone layouts, cross-filter interactions, export behaviour and performance in Desktop/Service.
5. Publish to an approved workspace/app and choose access deliberately. Do not use `Publish to web` unless the tenant owner explicitly accepts unrestricted public access to the report and underlying data.

Completion evidence to attach: Desktop version, reconciliation screenshot/table, Performance Analyzer export, accessibility checklist, workspace/app URL and the generated PBIP commit.
