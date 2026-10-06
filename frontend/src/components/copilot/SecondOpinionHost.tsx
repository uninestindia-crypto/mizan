import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { readSecondOpinionRequest, SECOND_OPINION_EVENT, type SecondOpinionRequest } from "../../lib/copilot";
import { SecondOpinionDialog } from "./SecondOpinionDialog";
import { initialRun, type RunAction, runsReducer } from "./verifyState";

/**
 * Mounted once in the app layout. Listens for the "open a second opinion" request that the Copilot, the Agents screen
 * and the stock page send, shows the window, and keeps each stock's run so the window can be closed and reopened.
 */
export function SecondOpinionHost() {
  const [request, setRequest] = useState<SecondOpinionRequest | null>(null);
  const [runs, dispatch] = useReducer(runsReducer, {});
  const opener = useRef<HTMLElement | null>(null);
  const symbol = request?.symbol ?? null;

  useEffect(() => {
    const onRequest = (event: Event) => {
      const next = readSecondOpinionRequest(event);
      if (!next) return;
      const active = document.activeElement;
      opener.current = active instanceof HTMLElement ? active : null;
      setRequest(next);
    };
    window.addEventListener(SECOND_OPINION_EVENT, onRequest);
    return () => window.removeEventListener(SECOND_OPINION_EVENT, onRequest);
  }, []);

  const report = useCallback(
    (action: RunAction) => {
      if (symbol) dispatch({ symbol, action });
    },
    [symbol],
  );
  const close = useCallback(() => setRequest(null), []);
  const returnFocus = useCallback(() => {
    if (opener.current?.isConnected) opener.current.focus();
  }, []);

  if (!request) return null;
  return (
    <SecondOpinionDialog
      key={request.symbol}
      request={request}
      run={runs[request.symbol] ?? initialRun}
      report={report}
      onClose={close}
      onClosed={returnFocus}
    />
  );
}
