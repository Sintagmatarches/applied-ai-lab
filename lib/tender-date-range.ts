export type TenderDateRange = {
  publishedFrom: string;
  publishedTo: string;
};

export const DEFAULT_TENDER_WINDOW_DAYS = 90;

function assertValidDate(value: Date) {
  if (Number.isNaN(value.valueOf())) {
    throw new TypeError("Tender date range requires a valid current date");
  }
}

function isoUtcDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

export function createTenderDateRange(
  currentDate: Date,
  windowDays = DEFAULT_TENDER_WINDOW_DAYS,
): TenderDateRange {
  assertValidDate(currentDate);
  if (!Number.isInteger(windowDays) || windowDays < 0) {
    throw new RangeError("Tender date window must be a non-negative integer");
  }

  const publishedTo = new Date(Date.UTC(
    currentDate.getUTCFullYear(),
    currentDate.getUTCMonth(),
    currentDate.getUTCDate(),
  ));
  const publishedFrom = new Date(publishedTo);
  publishedFrom.setUTCDate(publishedFrom.getUTCDate() - windowDays);

  return {
    publishedFrom: isoUtcDate(publishedFrom),
    publishedTo: isoUtcDate(publishedTo),
  };
}
