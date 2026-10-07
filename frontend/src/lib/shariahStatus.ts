import { useQueries } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { ApiError, api } from "./api";
import { useAppMode } from "./mode";

// One cheap call answers "what is the Shariah result for these stocks?" for badges and filters.
// GET /api/v2/shariah/status?symbols=TCS,INFY  ->  { statuses: { TCS: { verdict, data_status, short, as_of } } }
// The engine may not have this yet. A missing or failing answer is "not screened" for every stock, never "compliant".

export const VERDICTS = ["COMPLIANT", "NON_COMPLIANT", "QUESTIONABLE", "NOT_SCREENED"] as const;
export type Verdict = (typeof VERDICTS)[number];

export const DATA_STATUSES = ["VERIFIED_FILING", "STALE", "UNVERIFIED_SAMPLE", "NOT_SCREENED"] as const;
export type DataStatus = (typeof DATA_STATUSES)[number];

export interface ShariahStatus {
  verdict: Verdict;
  data_status: DataStatus;
  /** One plain reason, under 90 characters. */
  short: string;
  /** The date of the figures the result rests on (the filing's period end), or null. */
  as_of: string | null;
}

export const UNAVAILABLE_NOTE = "Shariah status is not available right now.";
export const MAX_SYMBOLS_PER_CALL = 200;
const FIVE_MINUTES = 5 * 60_000;
const RETRY_AFTER_FAILURE = 15_000;

export const STATUS_KEY = ["shariah-status"] as const;

export const NOT_AVAILABLE: ShariahStatus = {
  verdict: "NOT_SCREENED",
  data_status: "NOT_SCREENED",
  short: UNAVAILABLE_NOTE,
  as_of: null,
};

const NOT_YET: ShariahStatus = {
  verdict: "NOT_SCREENED",
  data_status: "NOT_SCREENED",
  short: "Not screened yet.",
  as_of: null,
};

function oneOf<T extends string>(list: readonly T[], value: unknown, fallback: T): T {
  return typeof value === "string" && (list as readonly string[]).includes(value) ? (value as T) : fallback;
}

/**
 * Whatever the engine sent, made safe. A result stands only with a data status this app knows; anything else is "not
 * screened", never a pass.
 */
export function parseStatus(raw: unknown): ShariahStatus {
  if (typeof raw !== "object" || raw === null) return NOT_YET;
  const row = raw as Record<string, unknown>;
  const verdict = oneOf(VERDICTS, row.verdict, "NOT_SCREENED");
  const dataStatus = oneOf(DATA_STATUSES, row.data_status, "NOT_SCREENED");
  const backed = verdict !== "NOT_SCREENED" && dataStatus !== "NOT_SCREENED";
  return {
    verdict: backed ? verdict : "NOT_SCREENED",
    data_status: backed ? dataStatus : "NOT_SCREENED",
    short: typeof row.short === "string" && row.short.trim() ? row.short : NOT_YET.short,
    as_of: typeof row.as_of === "string" ? row.as_of : null,
  };
}

/** Upper-cased, trimmed, without repeats, in a fixed order so the same list always asks the same question. */
export function normalizeSymbols(symbols: readonly string[]): string[] {
  const clean = symbols.map((s) => s.trim().toUpperCase()).filter(Boolean);
  return [...new Set(clean)].sort();
}

export function chunk<T>(list: readonly T[], size: number): T[][] {
  const parts: T[][] = [];
  for (let at = 0; at < list.length; at += size) parts.push(list.slice(at, at + size));
  return parts;
}

interface ChunkResult {
  unavailable: boolean;
  statuses: Record<string, ShariahStatus>;
}

const GONE: ChunkResult = { unavailable: true, statuses: {} };

type StatusReply = { statuses?: Record<string, unknown> } | null;

function readChunk(symbols: string[], body: StatusReply): ChunkResult {
  const statuses: Record<string, ShariahStatus> = {};
  for (const symbol of symbols) statuses[symbol] = parseStatus(body?.statuses?.[symbol]);
  return { unavailable: false, statuses };
}

async function fetchChunk(symbols: string[]): Promise<ChunkResult> {
  const url = `/api/v2/shariah/status?symbols=${symbols.map(encodeURIComponent).join(",")}`;
  try {
    return readChunk(symbols, await api<StatusReply>(url));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return GONE;
    throw error;
  }
}

export type StatusState = "off" | "loading" | "ready" | "unavailable";

export interface ShariahStatuses {
  /** Off when the screen is not in Shariah mode (and did not ask), loading while an answer is on its way. */
  state: StatusState;
  /** Every stock that has an answer so far. While loading, some stocks may be missing. */
  statuses: Record<string, ShariahStatus>;
  /** The result for one stock, or null while it has none yet. */
  statusOf: (symbol: string) => ShariahStatus | null;
  /** A plain sentence when the answer could not be had, else null. */
  note: string | null;
}

export interface StatusOptions {
  /** Ask even when the app is in Institutional mode (a screen that always shows the result). */
  always?: boolean;
}

type Settled = { data?: ChunkResult; isError: boolean };

/** A failed answer is asked for again after a short wait. */
function askAgainIfFailed(query: { state: { status: string } }): number | false {
  return query.state.status === "error" ? RETRY_AFTER_FAILURE : false;
}

function statusQuery(part: string[], enabled: boolean) {
  return {
    queryKey: [...STATUS_KEY, part.join(",")],
    queryFn: () => fetchChunk(part),
    enabled,
    staleTime: FIVE_MINUTES,
    retry: false,
    refetchInterval: askAgainIfFailed,
  };
}

export function useShariahStatuses(symbols: readonly string[], options: StatusOptions = {}): ShariahStatuses {
  const { isShariah } = useAppMode();
  const on = isShariah || Boolean(options.always);
  const listKey = normalizeSymbols(symbols).join(",");
  const parts = useMemo(() => chunk(listKey ? listKey.split(",") : [], MAX_SYMBOLS_PER_CALL), [listKey]);
  const join = useCallback((results: Settled[]) => combine(on, parts, results), [on, parts]);
  return useQueries({ queries: parts.map((part) => statusQuery(part, on)), combine: join });
}

function combine(on: boolean, parts: string[][], results: Settled[]): ShariahStatuses {
  const statuses: Record<string, ShariahStatus> = {};
  if (!on) return { state: "off", statuses, statusOf: () => null, note: null };
  let waiting = false;
  let failed = false;
  parts.forEach((part, at) => {
    const result = results[at];
    if (result?.data && !result.data.unavailable) Object.assign(statuses, result.data.statuses);
    else if (result?.data?.unavailable || result?.isError) {
      failed = true;
      for (const symbol of part) statuses[symbol] = NOT_AVAILABLE;
    } else waiting = true;
  });
  const state: StatusState = waiting ? "loading" : failed ? "unavailable" : "ready";
  const statusOf = (symbol: string) => statuses[symbol.trim().toUpperCase()] ?? null;
  return { state, statuses, statusOf, note: state === "unavailable" ? UNAVAILABLE_NOTE : null };
}
