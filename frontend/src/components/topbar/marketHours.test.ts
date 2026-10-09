import { describe, expect, it } from "vitest";
import { indiaClock, type MarketPhase, marketStatus } from "./marketHours";

// India time is UTC + 5:30 all year. Wednesday 7 October 2026 is a trading weekday; 10 and 11 October are a weekend.

describe("India time", () => {
  const ROWS_1 = [
    ["2026-10-07T03:45:00Z", "2026-10-07", 3, 9 * 60 + 15],
    ["2026-10-07T18:29:00Z", "2026-10-07", 3, 23 * 60 + 59],
    ["2026-10-07T18:30:00Z", "2026-10-08", 4, 0],
    ["2026-10-09T19:00:00Z", "2026-10-10", 6, 30],
  ];

  it.each(ROWS_1)("%s is %s (weekday %i, minute %i of the day) in India", (utc, date, weekday, minutes) => {
    expect(indiaClock(new Date(utc))).toEqual({ date, weekday, minutes });
  });
});

describe("the market, with no holiday list", () => {
  const CASES: [string, string, MarketPhase, string][] = [
    ["2026-10-07T03:29:00Z", "08:59 on a weekday", "before", "Market closed"],
    ["2026-10-07T03:30:00Z", "09:00 on a weekday", "pre-open", "Pre-open"],
    ["2026-10-07T03:44:00Z", "09:14 on a weekday", "pre-open", "Pre-open"],
    ["2026-10-07T03:45:00Z", "09:15 on a weekday", "hours", "Market hours"],
    ["2026-10-07T09:59:00Z", "15:29 on a weekday", "hours", "Market hours"],
    ["2026-10-07T10:00:00Z", "15:30 on a weekday", "after", "Market closed"],
    ["2026-10-07T18:29:00Z", "23:59 on a weekday", "after", "Market closed"],
    ["2026-10-05T04:30:00Z", "10:00 on a Monday", "hours", "Market hours"],
    ["2026-10-10T05:30:00Z", "11:00 on a Saturday", "weekend", "Market closed"],
    ["2026-10-11T05:30:00Z", "11:00 on a Sunday", "weekend", "Market closed"],
    ["2026-10-09T19:00:00Z", "00:30 Saturday in India, still Friday in UTC", "weekend", "Market closed"],
    ["2026-10-07T18:30:00Z", "00:00 Thursday in India, still Wednesday in UTC", "before", "Market closed"],
  ];

  it.each(CASES)("at %s (%s) the phase is %s and it says %s", (utc, _when, phase, label) => {
    const status = marketStatus(new Date(utc));
    expect([status.phase, status.label]).toEqual([phase, label]);
  });

  it("never says the market is open, because it cannot rule out a holiday", () => {
    expect(marketStatus(new Date("2026-10-07T05:00:00Z")).label).not.toMatch(/open/i);
  });

  it("explains that holidays are not visible when it says Market hours", () => {
    expect(marketStatus(new Date("2026-10-07T05:00:00Z")).detail).toMatch(/cannot see exchange holidays/);
  });
});

describe("the market, with the exchange's holiday list", () => {
  const holidays = new Set(["2026-10-07"]);

  it("says Market closed on a holiday that falls inside trading hours", () => {
    const status = marketStatus(new Date("2026-10-07T05:00:00Z"), holidays);
    expect([status.phase, status.label]).toEqual(["holiday", "Market closed"]);
    expect(status.detail).toBe("Today is a market holiday.");
  });

  it("says Market open on an ordinary weekday inside trading hours", () => {
    const status = marketStatus(new Date("2026-10-08T05:00:00Z"), holidays);
    expect([status.phase, status.label]).toEqual(["hours", "Market open"]);
  });

  it("still calls a weekend a weekend", () => {
    expect(marketStatus(new Date("2026-10-10T05:00:00Z"), holidays).phase).toBe("weekend");
  });
});
