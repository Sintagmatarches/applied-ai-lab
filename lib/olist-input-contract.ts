export const BRAZILIAN_STATE_CODES = [
  "AC",
  "AL",
  "AP",
  "AM",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MT",
  "MS",
  "MG",
  "PA",
  "PB",
  "PR",
  "PE",
  "PI",
  "RJ",
  "RN",
  "RS",
  "RO",
  "RR",
  "SC",
  "SP",
  "SE",
  "TO",
] as const;

export const OLIST_PAYMENT_TYPES = [
  "credit_card",
  "boleto",
  "voucher",
  "debit_card",
] as const;

export type BrazilianStateCode = (typeof BRAZILIAN_STATE_CODES)[number];
export type OlistPaymentType = (typeof OLIST_PAYMENT_TYPES)[number];

const brazilianStateCodeSet = new Set<string>(BRAZILIAN_STATE_CODES);
const olistPaymentTypeSet = new Set<string>(OLIST_PAYMENT_TYPES);

const isoTimestampWithTimezone =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|([+-])(\d{2}):(\d{2}))$/;

export function isBrazilianStateCode(
  value: string,
): value is BrazilianStateCode {
  return brazilianStateCodeSet.has(value);
}

export function isOlistPaymentType(value: string): value is OlistPaymentType {
  return olistPaymentTypeSet.has(value);
}

export function parseIsoTimestampWithTimezone(value: string): number | null {
  const match = isoTimestampWithTimezone.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6] ?? "0");
  const offsetHour = Number(match[10] ?? "0");
  const offsetMinute = Number(match[11] ?? "0");

  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    offsetHour > 14 ||
    offsetMinute > 59 ||
    (offsetHour === 14 && offsetMinute !== 0)
  ) {
    return null;
  }

  const calendarDate = new Date(Date.UTC(year, month - 1, day));
  if (
    calendarDate.getUTCFullYear() !== year ||
    calendarDate.getUTCMonth() !== month - 1 ||
    calendarDate.getUTCDate() !== day
  ) {
    return null;
  }

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}
