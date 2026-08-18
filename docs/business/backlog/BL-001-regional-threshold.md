# BL-001 — Regional delay-policy selector

> **Simulated stakeholder request / Portfolio simulation.**

**Priority:** P1  
**State:** Implemented in this delivery  
**Business reason:** The historical dashboard already supports 5/10/15/30-minute policies, while the regional monitor was fixed at 5 minutes. That makes live and historical conversations easy to misalign.

## Requirements

- expose 5, 10, 15 and 30 whole-minute choices;
- recompute delayed count/share, problem ranking and composite score from one snapshot;
- retain `>15` as the fixed serious-delay definition;
- label the active threshold next to every affected metric;
- preserve Åland as `No rail service` and zero-observation regions as `No data`.

## Acceptance criteria

- a 12-minute train is delayed at 5 and 10 minutes, but not at 15 or 30;
- changing threshold changes the score/status without a new Digitraffic request;
- serious-delay count is identical across threshold selections;
- historical snapshot and live API expose the same threshold contract;
- TypeScript and Python regional builders produce the required threshold fields.

## Definition of Done

Code, tests, metric documentation, traceability, changelog, cache bust and production deployment are complete.
