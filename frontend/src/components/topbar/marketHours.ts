// Is the Indian stock market open right now? NSE trades Monday to Friday, 9:15 am to 3:30 pm India time. India has no
// daylight saving, so India time is always UTC plus 5:30. The exchange's holiday list is not sent to the app, so
// without it a weekday inside trading hours is called "Market hours", never "Market open": QuantOS does not claim the
// market is trading on a day it cannot rule out as a holiday.

const INDIA_OFFSET_MS = 330 * 60_000;
const PRE_OPEN = 9 * 60;
const OPEN = 9 * 60 + 15;
const CLOSE = 15 * 60 + 30;

export interface IndiaClock {
  /** The calendar date in India, "2026-10-06". */
  date: string;
  /** 0 is Sunday, 6 is Saturday. */
  weekday: number;
  /** Minutes since midnight in India. */
  minutes: number;
}

export function indiaClock(now: Date): IndiaClock {
  const shifted = new Date(now.getTime() + INDIA_OFFSET_MS);
  return {
    date: shifted.toISOString().slice(0, 10),
    weekday: shifted.getUTCDay(),
    minutes: shifted.getUTCHours() * 60 + shifted.getUTCMinutes(),
  };
}

export type MarketPhase = "weekend" | "holiday" | "before" | "pre-open" | "hours" | "after";
export type ChipTone = "ok" | "neutral" | "warn" | "brand";

export interface MarketStatus {
  phase: MarketPhase;
  label: string;
  detail: string;
  tone: ChipTone;
}

const TIMES = "NSE trades Monday to Friday, 9:15 am to 3:30 pm India time.";
const NO_HOLIDAYS = "QuantOS cannot see exchange holidays, so on a holiday the market stays shut.";

const STATUS: Record<MarketPhase, Omit<MarketStatus, "phase">> = {
  weekend: { label: "Market closed", detail: `It is the weekend. ${TIMES}`, tone: "neutral" },
  holiday: { label: "Market closed", detail: "Today is a market holiday.", tone: "neutral" },
  before: { label: "Market closed", detail: "NSE opens today at 9:15 am India time.", tone: "neutral" },
  "pre-open": {
    label: "Pre-open",
    detail: "Orders are being collected before NSE opens at 9:15 am India time.",
    tone: "brand",
  },
  hours: {
    label: "Market hours",
    detail: `${TIMES} ${NO_HOLIDAYS}`,
    tone: "ok",
  },
  after: {
    label: "Market closed",
    detail: "NSE closed at 3:30 pm India time and opens again on the next trading day at 9:15 am.",
    tone: "neutral",
  },
};

const OPEN_WHEN_HOLIDAYS_KNOWN: Omit<MarketStatus, "phase"> = {
  label: "Market open",
  detail: "NSE is trading until 3:30 pm India time.",
  tone: "ok",
};

function phaseAt(clock: IndiaClock, holidays: ReadonlySet<string> | undefined): MarketPhase {
  if (clock.weekday === 0 || clock.weekday === 6) return "weekend";
  if (holidays?.has(clock.date)) return "holiday";
  if (clock.minutes < PRE_OPEN) return "before";
  if (clock.minutes < OPEN) return "pre-open";
  return clock.minutes < CLOSE ? "hours" : "after";
}

/**
 * The market's state at `now`. `holidays` is a set of ISO dates when the exchange's list is known; leave it out when it
 * is not, and a trading-hours weekday then reads "Market hours" rather than "Market open".
 */
export function marketStatus(now: Date, holidays?: ReadonlySet<string>): MarketStatus {
  const phase = phaseAt(indiaClock(now), holidays);
  const known = phase === "hours" && holidays !== undefined;
  return { phase, ...(known ? OPEN_WHEN_HOLIDAYS_KNOWN : STATUS[phase]) };
}
