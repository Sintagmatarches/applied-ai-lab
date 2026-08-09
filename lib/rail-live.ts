export type DigitrafficTimeTableRow = {
  stationShortCode?: string;
  type?: "ARRIVAL" | "DEPARTURE";
  commercialStop?: boolean;
  trainStopping?: boolean;
  cancelled?: boolean;
  scheduledTime?: string;
  actualTime?: string;
  liveEstimateTime?: string;
  differenceInMinutes?: number;
};

export type DigitrafficTrain = {
  trainNumber?: number;
  departureDate?: string;
  trainType?: string;
  commuterLineID?: string;
  trainCategory?: string;
  cancelled?: boolean;
  timeTableRows?: DigitrafficTimeTableRow[];
};

export type LiveRailService = {
  key: string;
  direction: string;
  service: string;
  scheduledDeparture: string;
  expectedArrival: string | null;
  arrivalDelayMinutes: number | null;
  status: "scheduled" | "estimated" | "arrived" | "cancelled";
};

function commercialEvent(
  train: DigitrafficTrain,
  station: string,
  type: "ARRIVAL" | "DEPARTURE",
): DigitrafficTimeTableRow | undefined {
  return train.timeTableRows?.find(
    (row) =>
      row.stationShortCode === station &&
      row.type === type &&
      row.commercialStop === true &&
      row.trainStopping === true,
  );
}

export function normalizeLiveService(
  train: DigitrafficTrain,
  origin: "HKI" | "LH",
  destination: "HKI" | "LH",
): LiveRailService | null {
  const departure = commercialEvent(train, origin, "DEPARTURE");
  const arrival = commercialEvent(train, destination, "ARRIVAL");
  if (!departure?.scheduledTime || !arrival?.scheduledTime) return null;

  const cancelled = Boolean(train.cancelled || departure.cancelled || arrival.cancelled);
  const service = train.commuterLineID?.trim() || `${train.trainType ?? "Train"} ${train.trainNumber ?? ""}`.trim();
  const status: LiveRailService["status"] = cancelled
    ? "cancelled"
    : arrival.actualTime
      ? "arrived"
      : arrival.liveEstimateTime
        ? "estimated"
        : "scheduled";

  return {
    key: `${train.departureDate ?? ""}:${train.trainNumber ?? ""}:${origin}:${destination}`,
    direction: origin === "LH" ? "Lahti → Helsinki" : "Helsinki → Lahti",
    service,
    scheduledDeparture: departure.scheduledTime,
    expectedArrival: arrival.actualTime ?? arrival.liveEstimateTime ?? arrival.scheduledTime,
    arrivalDelayMinutes:
      typeof arrival.differenceInMinutes === "number"
        ? arrival.differenceInMinutes
        : null,
    status,
  };
}

