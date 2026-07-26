# Applied AI Lab

Applied AI Lab is a standalone website for practical machine-learning tools.
It uses the European Songbook only as a visual-system reference; it does not
share the Songbook's content, data, routes, or runtime.

## Current state

- The Olist historical analytics project is represented as complete.
- The delivery-delay prediction model is explicitly marked as in development.
- The prediction form is disabled until a validated model API exists.
- No placeholder probability or invented performance metric is produced.
- Future project sections are available as stable, clearly marked `Planned`
  routes.

## Routes

- `/` — lab overview and operating principles
- `/olist-delivery-delay-predictor` — first active project
- `/housing-value-forecast` — planned
- `/credit-risk-assessment` — planned
- `/document-processing` — planned
- `/image-recognition` — planned

## Future model integration

The presentation and project navigation live in `app/lab-shell.tsx`. When the
Olist model is ready, connect a versioned inference endpoint to the existing
form, replace only validated input fields, and render a response containing the
probability, risk band, model version, and explanatory factors. The shared lab
shell and other project routes do not need to be rebuilt.

## Local commands

```text
npm install
npm run dev
npm test
```

Production assets are generated with content hashes. Stable social and favicon
assets use explicit versioned names or query strings for cache busting.
