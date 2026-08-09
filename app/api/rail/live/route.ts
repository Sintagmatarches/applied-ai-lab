import {
  normalizeLiveService,
  type DigitrafficTrain,
} from "../../../../lib/rail-live";

const API_ROOT = "https://rata.digitraffic.fi/api/v1/live-trains/station";
const SOURCE_HEADER = "AppliedAILab/RailReliabilityMonitor 1.0";

async function fetchDirection(origin: "HKI" | "LH", destination: "HKI" | "LH") {
  const response = await fetch(
    `${API_ROOT}/${origin}/${destination}?include_nonstopping=false&limit=18`,
    {
      headers: {
        accept: "application/json",
        "accept-encoding": "gzip",
        "digitraffic-user": SOURCE_HEADER,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Digitraffic returned ${response.status}`);
  }
  const trains = (await response.json()) as DigitrafficTrain[];
  return trains
    .filter((train) =>
      train.trainCategory === "Long-distance" || train.trainCategory === "Commuter",
    )
    .map((train) => normalizeLiveService(train, origin, destination))
    .filter((service) => service !== null);
}

export async function GET(): Promise<Response> {
  try {
    const services = (
      await Promise.all([
        fetchDirection("LH", "HKI"),
        fetchDirection("HKI", "LH"),
      ])
    )
      .flat()
      .sort((left, right) =>
        left.scheduledDeparture.localeCompare(right.scheduledDeparture),
      );

    return Response.json(
      {
        retrievedAt: new Date().toISOString(),
        source: "Fintraffic / Digitraffic",
        sourceUrl: "https://www.digitraffic.fi/en/railway-traffic/",
        services,
      },
      {
        headers: {
          "cache-control": "public, max-age=60, s-maxage=300",
        },
      },
    );
  } catch (error) {
    console.error("Digitraffic live service request failed", error);
    return Response.json(
      {
        error: "Recent service data is temporarily unavailable from Digitraffic.",
      },
      {
        status: 502,
        headers: { "cache-control": "no-store" },
      },
    );
  }
}
