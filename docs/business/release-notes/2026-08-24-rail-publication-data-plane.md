# Rail publication data plane — 24 August 2026

The seven-day Finland Rail monitor no longer depends on a website rebuild for daily data. The governed workflow now builds and gates the real bounded Spark/Delta window, creates a content-addressed immutable snapshot, and advances a stable manifest on the dedicated `rail-publications` branch in one Git commit.

Production validates the manifest, snapshot SHA-256, policy/schema versions, complete seven-date coverage, timestamp ordering, KPI reconciliation and the official 19-region domain before serving remote data. Network, HTTP, JSON, digest or contract failure activates the bundled last-known-good snapshot with explicit provenance and a forced stale state.

The change adds Helsinki completed-date handling with DST/month/year regression coverage, bounded publication retention, isolated write permissions, short runtime caching and tests for remote success plus every fail-closed fallback class. Daily data churn does not touch `main`, and no paid service or new secret is required.
