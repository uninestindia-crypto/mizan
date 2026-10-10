import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, api, errorMessage } from "../../lib/api";
import { FUNDAMENTALS_KEY } from "../../lib/fundamentalsQueries";
import type { FetchFailure, FetchJob, FetchState } from "../../lib/fundamentalsTypes";

// "Get the latest results": ask the engine to read a company's latest quarterly results from NSE, then watch it work.
// POST   /api/v2/fundamentals/fetch          {symbol}  ->  202 {job_id}   (429 when one is already running, 422 for a bad symbol)
// GET    /api/v2/fundamentals/jobs/{job_id}  ->  {status, symbol, done, total, saved, message, failures: [{symbol, reason}]}
// DELETE /api/v2/fundamentals/jobs/{job_id}  stops it; filings already read are kept

export const POLL_MS = 1500;
const BASE = "/api/v2/fundamentals";
const STATES: readonly string[] = ["running", "done", "failed", "cancelled"];

export type GetPhase = "idle" | "starting" | "running" | "done" | "failed" | "cancelled" | "refused";

const asRecord = (v: unknown): Record<string, unknown> =>
  typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};

const count = (v: unknown): number => (typeof v === "number" ? v : 0);

function parseFailure(raw: unknown): FetchFailure[] {
  const row = asRecord(raw);
  return typeof row.reason === "string" ? [{ symbol: String(row.symbol ?? ""), reason: row.reason }] : [];
}

/** Whatever the engine sent, made safe: an unknown state counts as failed, never as done. */
export function parseJob(raw: unknown): FetchJob {
  const job = asRecord(raw);
  const failures = Array.isArray(job.failures) ? job.failures : [];
  return {
    status: STATES.includes(String(job.status)) ? (job.status as FetchState) : "failed",
    symbol: String(job.symbol ?? ""),
    done: count(job.done),
    total: count(job.total),
    saved: count(job.saved),
    message: typeof job.message === "string" ? job.message : "",
    failures: failures.flatMap(parseFailure),
  };
}

export interface GetResults {
  phase: GetPhase;
  /** A plain sentence about where things stand, or null. */
  message: string | null;
  done: number;
  total: number;
  saved: number;
  failures: FetchFailure[];
  cancelling: boolean;
  start: () => void;
  cancel: () => void;
}

const LOST_TOUCH = "QuantOS lost touch with the reading before it finished. Try again.";

type Trouble = { phase: "failed" | "refused"; message: string };

const LOST: Trouble = { phase: "failed", message: LOST_TOUCH };

/** The engine's own sentence for "busy" (429) and "not a company symbol" (422); anything else is a plain failure. */
function troubleFrom(error: unknown): Trouble {
  const refused = error instanceof ApiError && (error.status === 429 || error.status === 422);
  return { phase: refused ? "refused" : "failed", message: errorMessage(error) };
}

function useJob(jobId: string | null) {
  return useQuery({
    queryKey: [...FUNDAMENTALS_KEY, "job", jobId] as const,
    queryFn: async () => parseJob(await api<unknown>(`${BASE}/jobs/${encodeURIComponent(jobId ?? "")}`)),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? POLL_MS : false),
    retry: false,
  });
}

export function useGetResults(symbol: string): GetResults {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [trouble, setTrouble] = useState<Trouble | null>(null);
  const starter = useMutation({
    mutationFn: () => api<{ job_id?: string }>(`${BASE}/fetch`, "POST", { symbol }),
    onSuccess: (reply) => {
      if (reply?.job_id) setJobId(reply.job_id);
      else setTrouble(LOST);
    },
    onError: (error) => setTrouble(troubleFrom(error)),
  });
  const job = useJob(jobId);
  const stopper = useMutation({
    mutationFn: () => api<unknown>(`${BASE}/jobs/${encodeURIComponent(jobId ?? "")}`, "DELETE"),
    onSettled: () => void job.refetch(),
  });
  const status = job.data?.status;
  useEffect(() => {
    // Done, or stopped part way: whatever was read is kept, so the screens show it.
    if (status !== "done" && status !== "cancelled") return;
    // Every fundamentals answer may have changed; the job itself has not, so it is not asked again.
    void qc.invalidateQueries({ queryKey: FUNDAMENTALS_KEY, predicate: (query) => query.queryKey[1] !== "job" });
  }, [status, qc]);
  const start = () => {
    setTrouble(null);
    setJobId(null);
    starter.mutate();
  };
  return describe({ trouble, jobId, job, starting: starter.isPending, cancelling: stopper.isPending }, start, () =>
    stopper.mutate(),
  );
}

interface Snapshot {
  trouble: Trouble | null;
  jobId: string | null;
  job: { data?: FetchJob; isError: boolean; error: unknown };
  starting: boolean;
  cancelling: boolean;
}

function phaseOf(s: Snapshot): GetPhase {
  if (s.trouble) return s.trouble.phase;
  if (s.jobId === null) return s.starting ? "starting" : "idle";
  if (s.job.isError) return "failed";
  return s.job.data?.status ?? "starting";
}

function wordsOf(s: Snapshot): string | null {
  if (s.trouble) return s.trouble.message;
  if (s.job.isError) return errorMessage(s.job.error) || LOST_TOUCH;
  return s.job.data?.message || null;
}

function describe(s: Snapshot, start: () => void, cancel: () => void): GetResults {
  const data = s.job.data;
  return {
    phase: phaseOf(s),
    message: wordsOf(s),
    done: data?.done ?? 0,
    total: data?.total ?? 0,
    saved: data?.saved ?? 0,
    failures: data?.failures ?? [],
    cancelling: s.cancelling,
    start,
    cancel,
  };
}
