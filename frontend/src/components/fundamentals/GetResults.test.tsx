import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../lib/api";
import { callsTo } from "../agents/testHarness";
import { renderPage } from "../mode/modeKit";
import { engine, refuses, url } from "./fundamentalsKit";
import { COMPANY_FRESH, COMPANY_NONE } from "./fundamentalsFixtures";
import { FundamentalsSection } from "./FundamentalsSection";
import { GetResults } from "./GetResults";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const FETCH = "POST /api/v2/fundamentals/fetch";
const JOB = "GET /api/v2/fundamentals/jobs/job1";
const STOP = "DELETE /api/v2/fundamentals/jobs/job1";
const BUSY = "QuantOS is already reading a company's results. Wait for it to finish, then try again.";
const base = { symbol: "AAA", saved: 0, failures: [] };
const running = { ...base, status: "running", done: 3, total: 16, message: "Reading AAA: filing 3 of 16." };
const done = { ...base, status: "done", done: 16, total: 16, saved: 16, message: "Read 16 of 16 filings for AAA." };

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

function ready(more: Record<string, unknown>) {
  engine({ [FETCH]: { job_id: "job1" }, ...more });
}

const press = () => fireEvent.click(screen.getByRole("button", { name: "Get the latest results" }));
const later = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));
const asked = () => callsTo("GET", "/api/v2/fundamentals/jobs/job1").length;

beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Get the latest results", () => {
  it("starts one reading for this company and shows progress that is read aloud", async () => {
    ready({ [JOB]: jobs(running) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    expect(await screen.findByText("Reading the company's results: filing 3 of 16")).toBeInTheDocument();
    expect(callsTo("POST", "/api/v2/fundamentals/fetch")).toEqual([{ symbol: "AAA" }]);
    expect(screen.getByRole("progressbar", { name: "Reading the company's results" })).toBeInTheDocument();
    const live = screen.getByText("Reading AAA: filing 3 of 16.").closest("[aria-live]");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByRole("button", { name: "Get the latest results" })).toBeNull();
  });

  it("asks how it is going every 1.5 seconds and stops asking when it is done", async () => {
    ready({ [JOB]: jobs(running, running, done) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    await screen.findByText(/Reading the company's results/);
    await waitFor(() => expect(asked()).toBe(1));
    await later(1400);
    expect(asked()).toBe(1);
    await later(200);
    await waitFor(() => expect(asked()).toBe(2));
    await later(1500);
    expect(await screen.findByText("Finished. The results on this page have been refreshed.")).toBeInTheDocument();
    await later(5000);
    expect(asked()).toBe(3);
  });

  it("says in plain words why a reading failed, and lets the person try again", async () => {
    const failures = [{ symbol: "AAA", reason: "NSE refused the request." }];
    const failed = { ...base, status: "failed", done: 0, total: 0, message: "NSE did not answer.", failures };
    ready({ [JOB]: jobs(failed) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    expect(await screen.findByText("The results could not be read.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "What went wrong" })).toHaveTextContent("AAA: NSE refused the request.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/fundamentals/fetch")).toHaveLength(2));
  });

  it("does not say the same sentence twice when the reason and the message are the same", async () => {
    const same = "NSE lists no quarterly results filing for this company that QuantOS can read.";
    const failures = [{ symbol: "AAA", reason: same }];
    ready({ [JOB]: jobs({ ...base, status: "failed", done: 0, total: 0, message: same, failures }) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    expect(await screen.findByText(same)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "What went wrong" })).toBeNull();
  });

  it("shows the engine's own sentence when another company is being read (busy)", async () => {
    ready({ [FETCH]: refuses("TOO_BUSY", BUSY, 429) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    expect(await screen.findByText(BUSY)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows the engine's own sentence when the symbol is not a company symbol", async () => {
    const sentence = "That does not look like an NSE stock symbol.";
    ready({ [FETCH]: refuses("INVALID_SYMBOL", sentence, 422) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    expect(await screen.findByText(sentence)).toBeInTheDocument();
  });

  it("can be stopped, and says what was kept", async () => {
    const kept = "Stopped. Filings already read are kept.";
    const cancelled = { ...base, status: "cancelled", done: 3, total: 16, saved: 3, message: kept };
    ready({ [JOB]: jobs(running, cancelled), [STOP]: { cancelled: true } });
    renderPage(<GetResults symbol="AAA" />);
    press();
    fireEvent.click(await screen.findByRole("button", { name: "Stop reading" }));
    expect(await screen.findByText(kept, { selector: "p.font-medium" })).toBeInTheDocument();
    expect(callsTo("DELETE", "/api/v2/fundamentals/jobs/job1")).toHaveLength(1);
  });

  it("says it lost touch when it cannot ask how the reading is going", async () => {
    ready({ [JOB]: jobs(new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0)) });
    renderPage(<GetResults symbol="AAA" />);
    press();
    expect(await screen.findByText("The QuantOS engine is not responding.")).toBeInTheDocument();
    expect(screen.getByText("The results could not be read.")).toBeInTheDocument();
  });
});

describe("refreshing the section", () => {
  it("shows the new results on the page once the reading is done", async () => {
    let read = false;
    ready({
      [url("AAA")]: () => (read ? COMPANY_FRESH : COMPANY_NONE),
      [JOB]: () => {
        read = true;
        return done;
      },
    });
    renderPage(<FundamentalsSection symbol="AAA" />);
    await screen.findByText(COMPANY_NONE.data_notice);
    press();
    await screen.findByText(COMPANY_FRESH.scorecard.header);
    expect(screen.queryByText(COMPANY_NONE.data_notice)).toBeNull();
  });
});
