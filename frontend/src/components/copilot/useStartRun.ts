import { useCallback } from "react";
import { errorMessage } from "../../lib/api";
import { buildVerifyRequest, copilotApi, type SecondOpinionRequest } from "../../lib/copilot";
import type { RunAction } from "./verifyState";

export interface StartChoice {
  providers: string[];
  withPick: boolean;
}

export const COULD_NOT_START = "QuantOS could not start the check. Try again in a moment.";

type Report = (action: RunAction) => void;

async function startRun(request: SecondOpinionRequest, choice: StartChoice, report: Report): Promise<void> {
  report({ type: "starting" });
  try {
    const note = choice.withPick ? (request.pickNote ?? null) : null;
    const started = await copilotApi.startVerify(buildVerifyRequest(request.symbol, choice.providers, note));
    if (!started.job_id) throw new Error(COULD_NOT_START);
    report({ type: "started", jobId: started.job_id });
  } catch (error) {
    report({ type: "startFailed", message: errorMessage(error) });
  }
}

/**
 * Starts a run for the stock and reports what happens. The report goes to the caller's own state, so it still lands
 * if the window has been closed in the meantime.
 */
export function useStartRun(request: SecondOpinionRequest, report: Report): (choice: StartChoice) => Promise<void> {
  return useCallback((choice) => startRun(request, choice, report), [request, report]);
}
