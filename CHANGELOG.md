# Changelog

This changelog records real repository releases. Business roles labelled as simulated are portfolio exercises, not historical client work.

## 2026-08-18

### Added

- Regional delay-policy selector for 5, 10, 15 and 30 minutes, with threshold-specific delay shares, scores, statuses and problem rankings.
- Daily Digitraffic partition completeness validation before trusted cache/Bronze publication and on local cache read.
- Simulated business requirements, prioritised issue-ready backlog, CR-001 change request, INC-001 incident, stakeholder delivery memo and traceability matrix.
- Power BI semantic-model/report specifications and executive/data-quality DAX measures.
- Fabric activity, watermark, idempotency, quality-gate, promotion and recovery specification.
- Explicit Power BI/Fabric/user manual completion tasks.

### Changed

- Regional Disruption Score now uses the actively selected policy threshold for its delayed-share component; serious delay remains fixed above 15 minutes.
- Historical regional artifact rebuilt from the same 365 source partitions with no coverage/population change.
- Public assets and monitoring requests cache-busted for the release.
- Build/runtime tooling updated to patched Vinext/Cloudflare/RSC/Wrangler versions after dependency audit; no package overrides were introduced.

### Preserved

- Legacy five-minute API fields, target population, missing-timing treatment, cancellation definitions, Åland `No rail service` state and all prior historical evidence.
