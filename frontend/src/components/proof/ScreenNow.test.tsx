import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../lib/api";
import { callsTo, routeApi } from "../agents/testHarness";
import { renderPage, statusFor } from "../mode/modeKit";
import { rawProof } from "./proofFixtures";
import { PROOF_URL } from "./proofKit";
import { ScreenNow } from "./ScreenNow";
import { StockProofPanel } from "./StockProofPanel";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const FETCH = "POST /api/v2/shariah/filings/fetch";
const JOB = "GET /api/v2/shariah/filings/jobs/job1";
const STOP = "DELETE /api/v2/shariah/filings/jobs/job1";
const running = { status: "running", done: 0, total: 1, message: "Reading the filing from NSE.", failures: [] };
const done = { status: "done", done: 1, total: 1, message: "Finished.", failures: [] };

/** Answers the job call from a list, one answer per call, the last one repeating. */
function jobs(...answers: unknown[]) {
  let at = 0;
  return () => {
    const answer = answers[Math.min(at, answers.length - 1)];
    at += 1;
    if (answer instanceof Error) throw answer;
    return answer;
  };
}

function engine(extra: Record<string, unknown>) {
  routeApi({ "GET /api/v2/status": statusFor(true), [FETCH]: { job_id: "job1" }, ...extra });
}

const press = () => fireEvent.click(screen.getByRole("button", { name: "Screen this stock now" }));
const later = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Screen this stock now", () => {
  it("starts one fetch for this stock and shows progress that is read aloud", async () => {
    engine({ [JOB]: jobs(running) });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    expect(await screen.findByText("Reading the company's filing: 0 of 1")).toBeInTheDocument();
    expect(callsTo("POST", "/api/v2/shariah/filings/fetch")).toEqual([{ symbol: "TCS" }]);
    expect(screen.getByRole("progressbar", { name: "Reading the company's filing" })).toBeInTheDocument();
    const live = screen.getByText("Reading the filing from NSE.").closest("[aria-live]");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByRole("button", { name: "Screen this stock now" })).toBeNull();
  });

  it("asks how it is going every 1.5 seconds, and stops when it is done", async () => {
    engine({ [JOB]: jobs(running, running, done) });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    await screen.findByText(/Reading the company's filing/);
    const asked = () => callsTo("GET", "/api/v2/shariah/filings/jobs/job1").length;
    await waitFor(() => expect(asked()).toBe(1));
    await later(1400);
    expect(asked()).toBe(1);
    await later(200);
    await waitFor(() => expect(asked()).toBe(2));
    await later(1500);
    expect(await screen.findByText("Finished. The screening has been updated.")).toBeInTheDocument();
    await later(5000);
    expect(asked()).toBe(3);
  });

  it("shows the new result in the proof once the filing has been read", async () => {
    let screened = false;
    engine({
      [PROOF_URL]: () => rawProof(screened ? "compliant" : "not_screened"),
      [JOB]: () => {
        screened = true;
        return done;
      },
    });
    renderPage(<StockProofPanel symbol="TCS" />);
    await screen.findByText(/is not screened yet/);
    press();
    const verdict = () => within(screen.getByRole("group", { name: "Verdict" }));
    await waitFor(() => expect(verdict().getByText("Compliant")).toBeInTheDocument());
    expect(screen.queryByText(/is not screened yet/)).toBeNull();
  });

  it("says why a filing could not be read, and lets the person try again", async () => {
    const failures = [{ symbol: "TCS", reason: "NSE refused the request." }];
    const failed = { status: "failed", done: 0, total: 1, message: "NSE did not answer.", failures };
    engine({ [JOB]: jobs(failed) });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    expect(await screen.findByText("The filing could not be read.")).toBeInTheDocument();
    expect(screen.getByText("NSE did not answer.")).toBeInTheDocument();
    expect(screen.getByText("NSE refused the request.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/shariah/filings/fetch")).toHaveLength(2));
  });

  it("says another filing is being read when the engine is busy", async () => {
    engine({
      [FETCH]: () => {
        throw new ApiError("HTTP_429", "Too Many Requests", 429);
      },
    });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    const busy = /Another filing is already being read\. Wait for it to finish, then try again\./;
    expect(await screen.findByText(busy)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("says it could not start, in plain words, when the engine refuses", async () => {
    engine({
      [FETCH]: () => {
        throw new ApiError("ENGINE_OFFLINE", "offline", 0);
      },
    });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    const words = /QuantOS could not start reading the filing\. Check your internet connection and try again\./;
    expect(await screen.findByText(words)).toBeInTheDocument();
  });

  it("can be stopped, and says nothing was changed", async () => {
    const cancelled = { status: "cancelled", done: 0, total: 1, message: "", failures: [] };
    engine({ [JOB]: jobs(running, cancelled), [STOP]: {} });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(await screen.findByText("Stopped. Nothing was changed.")).toBeInTheDocument();
    expect(callsTo("DELETE", "/api/v2/shariah/filings/jobs/job1")).toHaveLength(1);
  });

  it("says it lost touch when it cannot ask how the job is going", async () => {
    engine({ [JOB]: jobs(new ApiError("ENGINE_OFFLINE", "offline", 0)) });
    renderPage(<ScreenNow symbol="TCS" />);
    press();
    expect(await screen.findByText(/QuantOS lost touch with the screening before it finished\./)).toBeInTheDocument();
  });
});
