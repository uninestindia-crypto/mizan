import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { callsTo, serve } from "../update/updateKit";
import { HOLIDAYS_2026 } from "./topbarKit";
import { holidaysIn, indiaYear, useHolidayList, useHolidays } from "./useHolidays";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const ROUTE = "GET /api/v2/market/holidays";
const WED = new Date("2026-10-07T05:00:00Z");

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("which year it is for the holiday list", () => {
  it("is the year in India, which turns over five and a half hours before UTC does", () => {
    expect(indiaYear(new Date("2026-12-31T18:29:00Z"))).toBe(2026);
    expect(indiaYear(new Date("2026-12-31T18:30:00Z"))).toBe(2027);
  });
});

describe("the holidays to trust", () => {
  it("are each date with its name when the list covers the year", () => {
    const holidays = holidaysIn(HOLIDAYS_2026, 2026);
    expect(holidays?.get("2026-10-20")).toBe("Dussehra");
    expect(holidays?.has("2026-10-07")).toBe(false);
    expect(holidays?.size).toBe(2);
  });

  it("are not known when the list is for another year, because it says nothing about today", () => {
    expect(holidaysIn(HOLIDAYS_2026, 2027)).toBeUndefined();
    expect(holidaysIn(HOLIDAYS_2026, 2025)).toBeUndefined();
  });

  it("are not known when the engine had no years to give", () => {
    expect(holidaysIn({ years: [], holidays: [] }, 2026)).toBeUndefined();
  });

  const DAMAGED: [string, unknown][] = [
    ["nothing at all", undefined],
    ["null", null],
    ["a word", "holidays"],
    ["no holidays", { years: [2026] }],
    ["no years", { holidays: [] }],
    ["years that are not numbers", { years: ["2026"], holidays: [] }],
    ["a date that is not a date", { years: [2026], holidays: [{ date: "20 Oct", name: "Dussehra" }] }],
    ["a holiday with no name", { years: [2026], holidays: [{ date: "2026-10-20", name: "" }] }],
    ["a holiday that is not an object", { years: [2026], holidays: ["2026-10-20"] }],
  ];

  it.each(DAMAGED)("are not known from a list with %s", (_what, list) => {
    expect(holidaysIn(list, 2026)).toBeUndefined();
  });
});

describe("the holidays on the screen", () => {
  it("are asked of the engine and arrive when the list covers this year", async () => {
    serve({ [ROUTE]: HOLIDAYS_2026 });
    const { result } = renderHook(() => useHolidays(WED), { wrapper });
    expect(result.current).toBeUndefined();
    await waitFor(() => expect(result.current?.get("2026-10-20")).toBe("Dussehra"));
    expect(callsTo("GET", "/api/v2/market/holidays")).toHaveLength(1);
  });

  // Both the list and what the screen makes of it, so a test can wait for the list to arrive before saying it was not used.
  const both = (now: Date) => ({ list: useHolidayList(), holidays: useHolidays(now) });

  it("stay unknown when the list is for last year only", async () => {
    serve({ [ROUTE]: { years: [2025], holidays: [{ date: "2025-10-02", name: "Mahatma Gandhi Jayanti" }] } });
    const { result } = renderHook(() => both(WED), { wrapper });
    await waitFor(() => expect(result.current.list.data?.years).toEqual([2025]));
    expect(result.current.holidays).toBeUndefined();
  });

  it("stay unknown, quietly, when the engine cannot answer", async () => {
    serve({});
    const { result } = renderHook(() => both(WED), { wrapper });
    await waitFor(() => expect(result.current.list.isError).toBe(true));
    expect(result.current.holidays).toBeUndefined();
  });

  it("are not asked for again each time the clock moves on", async () => {
    serve({ [ROUTE]: HOLIDAYS_2026 });
    const { result, rerender } = renderHook(({ now }) => useHolidays(now), { wrapper, initialProps: { now: WED } });
    await waitFor(() => expect(result.current).toBeDefined());
    const first = result.current;
    rerender({ now: new Date(WED.getTime() + 30_000) });
    expect(result.current).toBe(first);
    expect(callsTo("GET", "/api/v2/market/holidays")).toHaveLength(1);
  });

  it("are dropped when the year turns to one the list does not cover", async () => {
    serve({ [ROUTE]: HOLIDAYS_2026 });
    const { result, rerender } = renderHook(({ now }) => useHolidays(now), { wrapper, initialProps: { now: WED } });
    await waitFor(() => expect(result.current).toBeDefined());
    rerender({ now: new Date("2026-12-31T18:30:00Z") }); // 1 January 2027 in India
    expect(result.current).toBeUndefined();
  });
});
