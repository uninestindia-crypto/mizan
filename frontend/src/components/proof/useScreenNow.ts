import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, api } from "../../lib/api";
import { COVERAGE_KEY, PROOF_KEY } from "../../lib/proof";
import { STATUS_KEY } from "../../lib/shariahStatus";

// "Screen this stock now": ask the engine to read the company's latest filing, then watch it work.
// POST   /api/v2/shariah/filings/fetch          {symbol}  ->  202 {job_id}   (429 when one is already running)
// GET    /api/v2/shariah/filings/jobs/{job_id}  ->  {status: running|done|failed|cancelled, done, total, message,
//                                                   failures: [{symbol, reason}]}
// DELETE /api/v2/shariah/filings/jobs/{job_id}  stops it

export const POLL_MS = 1500;
const BASE = "/api/v2/shariah/filings";

export type ScreenPhase = "idle" | "starting" | "running" | "done" | "failed" | "cancelled" | "busy";

interface JobStatus {
  status: "running" | "done" | "failed" | "cancelled";
  done: number;
  total: number;
  message: string;
  failures: { symbol: string; reason: string }[];
}

const STATES: readonly string[] = ["running", "done", "failed", "cancelled"];

const asRecord = (v: unknown): Record<string, unknown> =>
  typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};

function parseFailure(raw: unknown): { symbol: string; reason: string }[] {
  const row = asRecord(raw);
  return typeof row.reason === "string" ? [{ symbol: String(row.symbol ?? ""), reason: row.reason }] : [];
}

function parseJob(raw: unknown): JobStatus {
  const j = asRecord(raw);
  const failures = Array.isArray(j.failures) ? j.failures : [];
  return {
    status: STATES.includes(String(j.status)) ? (j.status as JobStatus["status"]) : "failed",
    done: typeof j.done === "number" ? j.done : 0,
    total: typeof j.total === "number" ? j.total : 0,
    message: typeof j.message === "string" ? j.message : "",
    failures: failures.flatMap(parseFailure),
  };
}

export interface ScreenNow {
  phase: ScreenPhase;
  /** A plain sentence about where things stand, or null. */
  message: string | null;
  done: number;
  total: number;
  /** Why this stock could not be read, when it could not. */
  reason: string | null;
  cancelling: boolean;
  start: () => void;
  cancel: () => void;
  reset: () => void;
}

type Trouble = { phase: "failed" | "busy"; message: string };

const COULD_NOT_START = "QuantOS could not start reading the filing. Check your internet connection and try again.";
const BUSY = "Another filing is already being read. Wait for it to finish, then try again.";
const LOST_TOUCH = "QuantOS lost touch with the screening before it finished. Try again.";

const START_FAILED: Trouble = { phase: "failed", message: COULD_NOT_START };
const IS_BUSY: Trouble = { phase: "busy", message: BUSY };

function troubleFrom(error: unknown): Trouble {
  return error instanceof ApiError && error.status === 429 ? IS_BUSY : START_FAILED;
}

export function useScreenNow(symbol: string): ScreenNow {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [trouble, setTrouble] = useState<Trouble | null>(null);
  const starter = useMutation({
    mutationFn: () => api<{ job_id?: string }>(`${BASE}/fetch`, "POST", { symbol }),
    onSuccess: (reply) => (reply?.job_id ? setJobId(reply.job_id) : setTrouble(START_FAILED)),
    onError: (error) => setTrouble(troubleFrom(error)),
  });
  const job = useQuery({
    queryKey: ["shariah-job", jobId],
    queryFn: async () => parseJob(await api<unknown>(`${BASE}/jobs/${encodeURIComponent(jobId ?? "")}`)),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? POLL_MS : false),
    retry: false,
  });
  const stopper = useMutation({
    mutationFn: () => api<unknown>(`${BASE}/jobs/${encodeURIComponent(jobId ?? "")}`, "DELETE"),
    onSettled: () => void job.refetch(),
  });
  const status = job.data?.status;
  useEffect(() => {
    if (status !== "done") return;
    const upper = symbol.toUpperCase();
    void qc.invalidateQueries({ queryKey: [...PROOF_KEY, upper] });
    void qc.invalidateQueries({ queryKey: STATUS_KEY });
    void qc.invalidateQueries({ queryKey: COVERAGE_KEY });
  }, [status, qc, symbol]);
  return describe({ trouble, jobId, status, job, starting: starter.isPending, cancelling: stopper.isPending }, symbol, {
    start: () => {
      setTrouble(null);
      setJobId(null);
      starter.mutate();
    },
    cancel: () => stopper.mutate(),
    reset: () => {
      setTrouble(null);
      setJobId(null);
    },
  });
}

interface Snapshot {
  trouble: Trouble | null;
  jobId: string | null;
  status: JobStatus["status"] | undefined;
  job: { data?: JobStatus; isError: boolean };
  starting: boolean;
  cancelling: boolean;
}

function phaseOf(s: Snapshot): ScreenPhase {
  if (s.trouble) return s.trouble.phase;
  if (s.jobId === null) return s.starting ? "starting" : "idle";
  if (s.job.isError) return "failed";
  return s.status ?? "starting";
}

function describe(s: Snapshot, symbol: string, actions: Pick<ScreenNow, "start" | "cancel" | "reset">): ScreenNow {
  const phase = phaseOf(s);
  const data = s.job.data;
  const mine = data?.failures.find((f) => f.symbol.toUpperCase() === symbol.toUpperCase()) ?? data?.failures[0];
  const failed = phase === "failed" && !s.trouble;
  const message = s.trouble?.message ?? (failed && !data ? LOST_TOUCH : (data?.message || null));
  return {
    phase,
    message,
    done: data?.done ?? 0,
    total: data?.total ?? 0,
    reason: mine?.reason ?? null,
    cancelling: s.cancelling,
    ...actions,
  };
}
