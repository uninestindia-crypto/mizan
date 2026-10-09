// How old are the prices QuantOS holds? The newest day on disk is compared with the newest day that could be there.
// A day or two behind is normal (today's prices arrive in the evening), so only more than one missed trading day reads
// "Out of date". Exchange holidays are not known here, so a holiday can only make the message later, never earlier.

import { indiaClock } from "./marketHours";

/** Today's prices are counted as expected from this India time (8 pm) on a weekday. */
const PRICES_EXPECTED_FROM = 20 * 60;
const DAY_MS = 86_400_000;
const MAX_DAYS = 4000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export type FreshnessKind = "none" | "current" | "stale";

export interface Freshness {
  kind: FreshnessKind;
  label: string;
  detail: string;
}

function dayNumber(iso: string): number {
  return Math.floor(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / DAY_MS);
}

function isWeekday(day: number): boolean {
  const weekday = new Date(day * DAY_MS).getUTCDay();
  return weekday !== 0 && weekday !== 6;
}

/** The newest trading day whose prices should be here by now. */
export function expectedSession(now: Date): number {
  const clock = indiaClock(now);
  let day = dayNumber(clock.date);
  const todayCounts = isWeekday(day) && clock.minutes >= PRICES_EXPECTED_FROM;
  if (!todayCounts) day -= 1;
  for (let steps = 0; !isWeekday(day) && steps < 7; steps += 1) day -= 1;
  return day;
}

/** How many weekdays after `latest` up to the expected day have no prices. Zero when up to date or ahead. */
export function sessionsBehind(latest: string, now: Date): number {
  const from = dayNumber(latest);
  const to = expectedSession(now);
  let behind = 0;
  for (let day = from + 1; day <= to && day - from <= MAX_DAYS; day += 1) {
    if (isWeekday(day)) behind += 1;
  }
  return behind;
}

/** "6 Oct", with the year added when it is not this year. */
export function shortDate(iso: string, now: Date): string {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  const name = MONTHS[(month ?? 0) - 1];
  if (!year || !name || !day) return iso;
  const thisYear = Number(indiaClock(now).date.slice(0, 4));
  return year === thisYear ? `${day} ${name}` : `${day} ${name} ${year}`;
}

const NONE: Freshness = {
  kind: "none",
  label: "No prices yet",
  detail: "QuantOS has no market prices on this computer yet. Open Settings, then Market data, to get them.",
};

/** The prices chip. `latestSession` is the newest day with prices, as the engine reports it; missing means none. */
export function freshness(latestSession: string | null | undefined, now: Date): Freshness {
  if (!latestSession) return NONE;
  const when = shortDate(latestSession, now);
  if (sessionsBehind(latestSession, now) >= 2) {
    return {
      kind: "stale",
      label: `Out of date, ${when}`,
      detail: `The newest prices QuantOS has are from ${when}. Open Settings, then Market data, to get newer ones.`,
    };
  }
  return {
    kind: "current",
    label: `Prices as of ${when}`,
    detail: `QuantOS holds end-of-day prices up to ${when}. Prices for a day arrive after the market closes.`,
  };
}
