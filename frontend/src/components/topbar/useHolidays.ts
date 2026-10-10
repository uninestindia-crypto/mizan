import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../../lib/api";
import { indiaClock } from "./marketHours";

// The exchange's trading holidays, for the market chip. The chip may say "Market open" only when this list is known
// for the year it is looking at; a list for another year says nothing about today, so the chip then keeps saying
// "Market hours". Everything here fails towards "not known".

/** What GET /api/v2/market/holidays says: each holiday with its name, and the years the list covers. */
export interface HolidayList {
  years: number[];
  holidays: { date: string; name: string }[];
}

/** Each holiday's ISO date and its name. */
export type HolidayNames = ReadonlyMap<string, string>;

const SIX_HOURS = 6 * 60 * 60_000;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function isHoliday(day: unknown): boolean {
  if (typeof day !== "object" || day === null) return false;
  const { date, name } = day as Partial<HolidayList["holidays"][number]>;
  return typeof date === "string" && ISO_DATE.test(date) && typeof name === "string" && name !== "";
}

function wellFormed(list: unknown): list is HolidayList {
  if (typeof list !== "object" || list === null) return false;
  const { years, holidays } = list as Partial<HolidayList>;
  const yearsOk = Array.isArray(years) && years.every((year) => Number.isInteger(year));
  return yearsOk && Array.isArray(holidays) && holidays.every(isHoliday);
}

/** The year it is in India at `now`: the holiday list is for a calendar year there. */
export function indiaYear(now: Date): number {
  return Number(indiaClock(now).date.slice(0, 4));
}

/**
 * The holidays to use in `year`, or undefined when the list is missing, damaged, or does not cover that year. A date
 * outside a covered year is never taken for a trading day, so an uncovered year is "not known".
 */
export function holidaysIn(list: unknown, year: number): HolidayNames | undefined {
  if (!wellFormed(list) || !list.years.includes(year)) return undefined;
  return new Map(list.holidays.map((day) => [day.date, day.name]));
}

/** The engine's holiday list. Asked once in a while; a failure is quiet and simply leaves the holidays unknown. */
export function useHolidayList() {
  return useQuery({
    queryKey: ["market", "holidays"],
    queryFn: () => api<HolidayList>("/api/v2/market/holidays"),
    staleTime: SIX_HOURS,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/** The holidays for the year it is now in India, or undefined while they are unknown. Only a new year changes it. */
export function useHolidays(now: Date): HolidayNames | undefined {
  const list = useHolidayList().data;
  const year = indiaYear(now);
  return useMemo(() => holidaysIn(list, year), [list, year]);
}
