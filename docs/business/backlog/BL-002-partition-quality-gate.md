# BL-002 — Reject incomplete Digitraffic daily partitions

> **Portfolio simulation.** The associated incident is simulated; the preventive control is real repository code.

**Priority:** P1  
**State:** Implemented in this delivery  
**Business reason:** HTTP 200 plus valid JSON is insufficient evidence that a daily source partition is complete enough to publish.

## Requirements

- reject non-array and empty train payloads;
- reject a daily payload with no passenger trains;
- reject records whose `departureDate` does not match the requested partition;
- perform validation before atomic cache/bronze publication;
- revalidate historical cache reads so corrupted old partitions do not bypass the gate;
- only record a Fabric partition as `complete` after all checks pass.

## Acceptance criteria

- automated tests cover one valid partition and each rejection path;
- a rejected response does not replace an existing good cache file;
- downstream Fabric transformation verifies every requested date has one complete, non-empty audit record;
- the incident runbook explains detection, containment, root cause and recovery.

## Definition of Done

Python tests pass, Fabric notebook logic mirrors the local contract, and the quality rule is documented in the incident and traceability matrix.
