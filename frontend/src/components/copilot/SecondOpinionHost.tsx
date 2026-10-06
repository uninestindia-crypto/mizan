import { type RefObject, useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  copilotApi,
  readSecondOpinionRequest,
  SECOND_OPINION_EVENT,
  type SecondOpinionRequest,
} from "../../lib/copilot";
import { clearReady, markReady } from "./readyRuns";
import { SecondOpinionDialog } from "./SecondOpinionDialog";
import { useVerifyPolling } from "./verifyPolling";
import { initialRun, jobToCancel, type RunAction, runsReducer, type Runs, shouldPoll } from "./verifyState";

type Report = (symbol: string, action: RunAction) => void;

/**
 * What the host knows between renders. The runs are reduced here as well as in React so that the next action,
 * which may arrive in the same instant, is judged against the latest state.
 */
interface Latest {
  runs: Runs;
  /** The stock whose window is open, if any. */
  open: string | null;
}

/** Asks for one running check's answers for as long as it runs, whether or not its window is open. */
function RunPoller({ symbol, jobId, report }: { symbol: string; jobId: string; report: Report }) {
  const forThisStock = useCallback((action: RunAction) => report(symbol, action), [report, symbol]);
  useVerifyPolling(true, jobId, forThisStock);
  return null;
}

/**
 * The runs, one per stock, and the one way to change them. Besides updating a run it stops a cancelled run on the
 * engine, and remembers a run that finished while its window was closed so the app can offer it back.
 */
function useRuns(latest: RefObject<Latest>): { runs: Runs; report: Report } {
  const [runs, dispatch] = useReducer(runsReducer, {});
  const report = useCallback<Report>(
    (symbol, action) => {
      const state = latest.current;
      const before = state.runs[symbol] ?? initialRun;
      const job = jobToCancel(before, action);
      if (job) void copilotApi.cancelVerify(job).catch(() => undefined);
      state.runs = runsReducer(state.runs, { symbol, action });
      dispatch({ symbol, action });
      const after = state.runs[symbol] ?? initialRun;
      if (action.type === "starting" || action.type === "reset") clearReady(symbol);
      const justEnded = shouldPoll(before) && (after.phase === "done" || after.phase === "failed");
      if (justEnded && state.open !== symbol) markReady(symbol, after.phase === "done" ? "done" : "failed");
    },
    [latest],
  );
  return { runs, report };
}

/** The window's request, set by the shared "open a second opinion" event and cleared when the window closes. */
function useRequest(latest: RefObject<Latest>) {
  const [request, setRequest] = useState<SecondOpinionRequest | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const onRequest = (event: Event) => {
      const next = readSecondOpinionRequest(event);
      if (!next) return;
      const active = document.activeElement;
      opener.current = active instanceof HTMLElement ? active : null;
      latest.current.open = next.symbol;
      clearReady(next.symbol);
      setRequest(next);
    };
    window.addEventListener(SECOND_OPINION_EVENT, onRequest);
    return () => {
      window.removeEventListener(SECOND_OPINION_EVENT, onRequest);
      clearReady();
    };
  }, [latest]);
  const close = useCallback(() => {
    latest.current.open = null;
    setRequest(null);
  }, [latest]);
  const returnFocus = useCallback(() => {
    if (opener.current?.isConnected) opener.current.focus();
  }, []);
  return { request, close, returnFocus };
}

/**
 * Mounted once in the app layout. Listens for the "open a second opinion" request that the Copilot, the Agents screen
 * and the stock page send, shows the window, and keeps each stock's run. Runs keep being checked while their window is
 * closed, so a finished one can be offered back, and a cancelled one is also stopped on the engine.
 */
export function SecondOpinionHost() {
  const latest = useRef<Latest>({ runs: {}, open: null });
  const { runs, report } = useRuns(latest);
  const { request, close, returnFocus } = useRequest(latest);
  const symbol = request?.symbol ?? null;
  const reportOpen = useCallback(
    (action: RunAction) => {
      if (symbol) report(symbol, action);
    },
    [report, symbol],
  );
  return (
    <>
      {Object.entries(runs).map(([stock, run]) =>
        shouldPoll(run) && run.jobId ? (
          <RunPoller key={`${stock}-${run.jobId}`} symbol={stock} jobId={run.jobId} report={report} />
        ) : null,
      )}
      {request && (
        <SecondOpinionDialog
          key={request.symbol}
          request={request}
          run={runs[request.symbol] ?? initialRun}
          report={reportOpen}
          onClose={close}
          onClosed={returnFocus}
        />
      )}
    </>
  );
}
