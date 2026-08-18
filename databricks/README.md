# Databricks Free Edition handoff

The repository code has been executed locally and in Linux CI. This notebook is the prepared hosted entry point; Databricks execution is not claimed.

1. Sign in to Databricks Free Edition and create/open a workspace.
2. Add `https://github.com/Sintagmatarches/applied-ai-lab` as a Git folder.
3. Create or select a Unity Catalog Volume and set the notebook `source_cache` and `lakehouse` widgets to two directories below it.
4. Open `databricks/finland_rail_lakehouse.py` and attach a serverless runtime.
5. Set an initial short completed date range and run all cells.
6. Inspect the Delta control/fact/mart directories and the emitted run id before creating a scheduled Job.

Free Edition is quota-limited and serverless-only. Start with one date. Do not present the workspace run as production until scheduled execution, retained data and failure notification are verified under the owner's account.
