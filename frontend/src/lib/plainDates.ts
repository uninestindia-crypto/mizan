import { date } from "./format";

// Agents write dates the way the data is stored. A person reads "23 Mar 2021".

const ISO_DATE = /(?<![\w/-])(\d{4})-(\d{2})-(\d{2})(?![\dT-])/g;

function realDate(year: number, month: number, day: number): boolean {
  const when = new Date(Date.UTC(year, month - 1, day));
  return when.getUTCFullYear() === year && when.getUTCMonth() === month - 1 && when.getUTCDate() === day;
}

/** "2021-03-23" read as "23 Mar 2021". Anything that is not a real calendar date is left exactly as written. */
export function friendlyDates(text: string): string {
  return text.replace(ISO_DATE, (found, year: string, month: string, day: string) =>
    realDate(Number(year), Number(month), Number(day)) ? date(found) : found,
  );
}
