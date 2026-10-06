// One second-opinion run, as a plain reducer: set up, starting, running, done or failed.
// The dialog reads it; nothing here touches the screen or the network.

import type { VerifyPoll, VerifyProgress, VerifyResult } from "../../lib/copilot";

export type RunPhase = "setup" | "starting" | "running" | "done" | "failed";

export interface RunState {
  phase: RunPhase;
  jobId: string | null;
  progress: VerifyProgress | null;
  result: VerifyResult | null;
  /** A plain sentence about what went wrong, shown on the set-up or failed view. */
  error: string | null;
  /** True after the person stopped waiting. The set-up view says so once. */
  stopped: boolean;
}

export const initialRun: RunState = {
  phase: "setup",
  jobId: null,
  progress: null,
  result: null,
  error: null,
  stopped: false,
};

export const RUN_FAILED = "The models could not finish this check. Try it again in a minute.";

export type RunAction =
  | { type: "starting" }
  | { type: "started"; jobId: string }
  | { type: "startFailed"; message: string }
  | { type: "polled"; jobId: string; poll: VerifyPoll }
  | { type: "pollFailed"; jobId: string; message: string }
  | { type: "stopped" }
  | { type: "reset" };

function applyPoll(state: RunState, poll: VerifyPoll): RunState {
  if (poll.status === "done") {
    if (!poll.result) return { ...state, phase: "failed", error: RUN_FAILED };
    return { ...state, phase: "done", progress: poll.progress ?? state.progress, result: poll.result, error: null };
  }
  if (poll.status === "failed") return { ...state, phase: "failed", error: poll.error?.trim() || RUN_FAILED };
  return { ...state, progress: poll.progress ?? state.progress };
}

/** An answer counts only while the run it belongs to is still the one being waited on. */
function isCurrent(state: RunState, jobId: string): boolean {
  return state.phase === "running" && state.jobId === jobId;
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case "starting":
      return state.phase === "setup" ? { ...initialRun, phase: "starting" } : state;
    case "started":
      return state.phase === "starting" ? { ...state, phase: "running", jobId: action.jobId } : state;
    case "startFailed":
      return state.phase === "starting" ? { ...initialRun, error: action.message } : state;
    case "polled":
      return isCurrent(state, action.jobId) ? applyPoll(state, action.poll) : state;
    case "pollFailed":
      return isCurrent(state, action.jobId) ? { ...state, phase: "failed", error: action.message } : state;
    case "stopped":
      return state.phase === "starting" || state.phase === "running" ? { ...initialRun, stopped: true } : state;
    case "reset":
      return initialRun;
  }
}

/** Runs kept per stock, so closing the dialog and opening it again for the same stock shows the same run. */
export type Runs = Record<string, RunState>;

export interface RunsAction {
  symbol: string;
  action: RunAction;
}

export function runsReducer(runs: Runs, { symbol, action }: RunsAction): Runs {
  const current = runs[symbol] ?? initialRun;
  const next = runReducer(current, action);
  return next === current ? runs : { ...runs, [symbol]: next };
}

/** Polling goes on only while a run is waiting on its answers. */
export function shouldPoll(state: RunState): boolean {
  return state.phase === "running" && state.jobId !== null;
}

export function progressLabel(progress: VerifyProgress | null): string {
  if (!progress || progress.total <= 0) return "Starting the models";
  return `${progress.done} of ${progress.total} answers in`;
}

export function progressFraction(progress: VerifyProgress | null): number {
  return progress && progress.total > 0 ? progress.done / progress.total : 0;
}
