import assert from "node:assert/strict";
import test from "node:test";

import { normalizeLiveService } from "../lib/rail-live.ts";

test("normalizes a direct recent service without inventing an estimate", () => {
  const service = normalizeLiveService(
    {
      departureDate: "2026-08-09",
      trainNumber: 9841,
      trainType: "HL",
      commuterLineID: "Z",
      trainCategory: "Commuter",
      timeTableRows: [
        {
          stationShortCode: "LH",
          type: "DEPARTURE",
          commercialStop: true,
          trainStopping: true,
          scheduledTime: "2026-08-09T09:00:00Z",
        },
        {
          stationShortCode: "HKI",
          type: "ARRIVAL",
          commercialStop: true,
          trainStopping: true,
          scheduledTime: "2026-08-09T09:50:00Z",
          liveEstimateTime: "2026-08-09T09:57:00Z",
          differenceInMinutes: 7,
        },
      ],
    },
    "LH",
    "HKI",
  );

  assert.equal(service?.service, "Z");
  assert.equal(service?.direction, "Lahti → Helsinki");
  assert.equal(service?.status, "estimated");
  assert.equal(service?.arrivalDelayMinutes, 7);
});

test("marks a cancelled segment even when the whole-train flag is false", () => {
  const service = normalizeLiveService(
    {
      departureDate: "2026-08-09",
      trainNumber: 1,
      trainType: "IC",
      cancelled: false,
      timeTableRows: [
        {
          stationShortCode: "HKI",
          type: "DEPARTURE",
          commercialStop: true,
          trainStopping: true,
          scheduledTime: "2026-08-09T09:00:00Z",
        },
        {
          stationShortCode: "LH",
          type: "ARRIVAL",
          commercialStop: true,
          trainStopping: true,
          scheduledTime: "2026-08-09T09:50:00Z",
          cancelled: true,
        },
      ],
    },
    "HKI",
    "LH",
  );

  assert.equal(service?.status, "cancelled");
});

test("live API combines both directions and identifies the source", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const url = String(input);
    const fromLahti = url.includes("/LH/HKI");
    return Response.json([
      {
        departureDate: "2026-08-09",
        trainNumber: fromLahti ? 9841 : 9842,
        trainType: "HL",
        commuterLineID: "Z",
        trainCategory: "Commuter",
        timeTableRows: fromLahti
          ? [
              {
                stationShortCode: "LH",
                type: "DEPARTURE",
                commercialStop: true,
                trainStopping: true,
                scheduledTime: "2026-08-09T09:00:00Z",
              },
              {
                stationShortCode: "HKI",
                type: "ARRIVAL",
                commercialStop: true,
                trainStopping: true,
                scheduledTime: "2026-08-09T09:50:00Z",
              },
            ]
          : [
              {
                stationShortCode: "HKI",
                type: "DEPARTURE",
                commercialStop: true,
                trainStopping: true,
                scheduledTime: "2026-08-09T10:00:00Z",
              },
              {
                stationShortCode: "LH",
                type: "ARRIVAL",
                commercialStop: true,
                trainStopping: true,
                scheduledTime: "2026-08-09T10:50:00Z",
              },
            ],
      },
    ]);
  };

  try {
    const { GET } = await import("../app/api/rail/live/route.ts");
    const response = await GET();
    const body = (await response.json()) as {
      source: string;
      services: Array<{ direction: string }>;
    };
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "public, max-age=60, s-maxage=300");
    assert.equal(body.source, "Fintraffic / Digitraffic");
    assert.deepEqual(
      body.services.map((service) => service.direction),
      ["Lahti → Helsinki", "Helsinki → Lahti"],
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
