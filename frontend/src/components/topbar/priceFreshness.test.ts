import { describe, expect, it } from "vitest";
import { freshness, type FreshnessKind, sessionsBehind, shortDate } from "./priceFreshness";

// Wednesday 7 October 2026, 10:30 in India: the prices expected are Tuesday's. After 20:00 India time, Wednesday's.
const WED_MORNING = new Date("2026-10-07T05:00:00Z");
const WED_19_59 = new Date("2026-10-07T14:29:00Z");
const WED_20_00 = new Date("2026-10-07T14:30:00Z");
const MON_MORNING = new Date("2026-10-05T04:30:00Z");
const SAT_NOON = new Date("2026-10-10T06:30:00Z");

describe("how many trading days of prices are missing", () => {
  const CASES: [string, Date, string, number][] = [
    ["Wednesday morning", WED_MORNING, "2026-10-06", 0],
    ["Wednesday morning", WED_MORNING, "2026-10-05", 1],
    ["Wednesday morning", WED_MORNING, "2026-10-02", 2],
    ["Wednesday at 19:59", WED_19_59, "2026-10-06", 0],
    ["Wednesday at 20:00", WED_20_00, "2026-10-06", 1],
    ["Wednesday at 20:00", WED_20_00, "2026-10-05", 2],
    ["Monday morning", MON_MORNING, "2026-10-02", 0],
    ["Monday morning", MON_MORNING, "2026-10-01", 1],
    ["Monday morning", MON_MORNING, "2026-09-30", 2],
    ["Saturday noon", SAT_NOON, "2026-10-09", 0],
    ["Saturday noon", SAT_NOON, "2026-10-08", 1],
    ["Wednesday morning, with prices from the future", WED_MORNING, "2026-10-09", 0],
  ];

  it.each(CASES)("%s, newest prices %s*: %i missing", (_when, now, latest, missing) => {
    expect(sessionsBehind(latest, now)).toBe(missing);
  });
});

describe("the prices chip", () => {
  const CASES: [string, Date, string | null | undefined, FreshnessKind, string][] = [
    ["up to date", WED_MORNING, "2026-10-06", "current", "Prices as of 6 Oct"],
    ["one day behind is still normal", WED_MORNING, "2026-10-05", "current", "Prices as of 5 Oct"],
    ["more than a trading day behind", WED_MORNING, "2026-10-02", "stale", "Out of date, 2 Oct"],
    ["a year behind shows the year", WED_MORNING, "2025-12-31", "stale", "Out of date, 31 Dec 2025"],
    ["no prices at all", WED_MORNING, null, "none", "No prices yet"],
    ["prices not reported", WED_MORNING, undefined, "none", "No prices yet"],
  ];

  it.each(CASES)("%s", (_name, now, latest, kind, label) => {
    const chip = freshness(latest, now);
    expect([chip.kind, chip.label]).toEqual([kind, label]);
  });

  it("tells a person with stale prices where to get newer ones", () => {
    expect(freshness("2026-10-02", WED_MORNING).detail).toMatch(/Settings, then Market data/);
  });

  it("tells a person with no prices where to get them", () => {
    expect(freshness(null, WED_MORNING).detail).toMatch(/Settings, then Market data/);
  });
});

describe("a short date", () => {
  const ROWS_1 = [
    ["2026-10-06", "6 Oct"],
    ["2026-01-01", "1 Jan"],
    ["2025-03-09", "9 Mar 2025"],
    ["not a date", "not a date"],
  ];

  it.each(ROWS_1)("%s reads %s", (iso, words) => {
    expect(shortDate(iso, WED_MORNING)).toBe(words);
  });
});
