import { DASH, inr, inrCompact, int, num, pct } from "../../lib/format";
import type { DataStatus, FactCounts, FactStatus } from "../../lib/fundamentalsTypes";

// How the fundamentals screens say things. Plain words, no judgement: a figure is shown as the engine sent it, and
// nothing is coloured as good or bad.

/** Figures that are changes over time, which read better with a plus or minus in front. */
const CHANGES = new Set([
  "revenue_growth_quarter",
  "profit_growth_quarter",
  "revenue_growth_ttm",
  "profit_growth_ttm",
  "revenue_change_3y",
  "profit_change_3y",
]);

export interface ValueSource {
  key?: string;
  unit: string;
  value: number | null;
  extra?: Record<string, unknown>;
}

function quarters(value: number, extra: Record<string, unknown> | undefined): string {
  const of = typeof extra?.out_of === "number" ? ` of ${extra.out_of}` : "";
  return `${int(value)}${of} quarters`;
}

/** A figure with its unit, the way a person reads it: ₹6.20 Cr, 12.3%, 0.45 times, 6 of 8 quarters. */
export function figureText(figure: ValueSource): string {
  const { unit, value } = figure;
  if (value === null) return DASH;
  if (unit === "INR") return inrCompact(value);
  if (unit === "INR per share") return inr(value, 2);
  if (unit === "percent") return pct(value / 100, 1, CHANGES.has(figure.key ?? ""));
  if (unit === "times") return `${num(value, 2)} times`;
  if (unit === "quarters") return quarters(value, figure.extra);
  return num(value, 2);
}

/** The same figure with the whole rupee amount, for a small note beside it. */
export function exactRupees(value: number | null): string | null {
  return value === null ? null : inr(value, 0);
}

const FACT_WORDS: Record<FactStatus, string> = {
  OK: "Inside the rule of thumb",
  WATCH: "Outside the rule of thumb",
  INFO: "A fact, no rule of thumb",
  NOT_AVAILABLE: "Not available",
};

export function factWords(status: FactStatus): string {
  return FACT_WORDS[status];
}

const DATA_WORDS: Record<DataStatus, string> = {
  VERIFIED_FILING: "From the company's filings",
  STALE: "Old data",
  NOT_AVAILABLE: "No filing data",
};

export function dataWords(status: DataStatus): string {
  return DATA_WORDS[status];
}

const COUNT_WORDS: [FactStatus, (n: number) => string][] = [
  ["OK", (n) => `${n} inside the rule of thumb`],
  ["WATCH", (n) => `${n} outside it`],
  ["INFO", (n) => `${n} ${n === 1 ? "fact" : "facts"}`],
  ["NOT_AVAILABLE", (n) => `${n} not available`],
];

/** "3 inside the rule of thumb, 2 outside it, 4 facts". Kinds with none are left out. */
export function countsText(counts: FactCounts): string {
  const parts = COUNT_WORDS.filter(([status]) => counts[status] > 0).map(([status, say]) => say(counts[status]));
  return parts.length > 0 ? parts.join(", ") : "No facts yet";
}

export function basisWords(basis: "consolidated" | "standalone" | null): string | null {
  if (basis === null) return null;
  return basis === "consolidated" ? "Consolidated" : "Standalone";
}

/** Why a quarter that was read is left out of the figures, in words a person can read. */
const EXCLUDED_WORDS: Record<string, string> = {
  TIE_OUT_FAILED: "Failed its own check",
  READ_PARTIAL: "Only partly read",
  FORMAT_NOT_READ: "Layout not read",
  NOT_A_QUARTER: "Not a quarter",
};

export function excludedWords(status: string): string {
  return EXCLUDED_WORDS[status] ?? "Left out";
}
