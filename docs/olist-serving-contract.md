# Olist serving release contract

`GET /api/olist/model` reports the bundled model version, feature contract,
prediction domain, limitations and SHA-256 of UTF-8 `JSON.stringify` of the runtime
artifact. This encoding is explicit: it is not the hash of the formatted JSON file.
No history rows or coefficients are returned by the metadata endpoint. The source
artifact remains public in GitHub.

Prediction requests may supply `schema_version: 1`; omitted versions retain the
existing v1 contract. Other versions fail with 422 before scoring. Predictions
include `schema_version: 1` and the actual model version. Both routes use `no-store`.
Built-Worker integration tests compare metadata against the committed artifact
and scores against independently generated Python fixtures.

To release: freeze the development-selected artifact, run Python/TypeScript parity,
build, run the Worker integration tests, deploy the saved Sites version, and compare
the live metadata digest to the tested artifact. To roll back, redeploy the prior
saved Sites version; preprocessing, history, model weights and API ship together.
Do not roll back only coefficients. Model selection must never revisit the final
benchmark to choose another model.

This is a historical 2016–2018 scorer, not a current e-commerce service. The input
domain deliberately rejects present-day dates. Live calibration/drift alerts or
canary claims would lack a real labelled production cohort. A real deployment would
record model version, aggregate feature/missingness statistics and delayed labels,
then monitor ranking and calibration on a prospectively defined cohort. That is a
future deployment design, not functionality demonstrated by this release.
