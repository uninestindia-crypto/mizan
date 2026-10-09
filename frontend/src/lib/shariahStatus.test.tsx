import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, routeApi } from "../components/agents/testHarness";
import { COMPLIANT_ROW, renderPage, statusFor, statuses, statusUrl } from "../components/mode/modeKit";
import { ApiError, api } from "./api";
import { chunk, normalizeSymbols, parseStatus, useShariahStatuses } from "./shariahStatus";

vi.mock("./api", async (importOriginal) => {
  const real = await importOriginal<typeof import("./api")>();
  return { ...real, api: vi.fn() };
});

function Probe({ symbols, always = false }: { symbols: string[]; always?: boolean }) {
  const lookup = useShariahStatuses(symbols, { always });
  return (
    <output>
      {lookup.state}|{lookup.statusOf("aaa")?.verdict ?? "none"}|{lookup.note ?? "no note"}
    </output>
  );
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("parseStatus", () => {
  const CASES_1 = [
    ["nothing at all", null],
    ["a word", "COMPLIANT"],
    ["an unknown verdict", { verdict: "HALAL", data_status: "VERIFIED_FILING", short: "x", as_of: null }],
    ["a verdict with no data status", { verdict: "COMPLIANT", short: "x", as_of: null }],
    ["a verdict with an unknown data status", { verdict: "COMPLIANT", data_status: "GOLD", short: "x", as_of: null }],
    ["a result marked not screened", { verdict: "COMPLIANT", data_status: "NOT_SCREENED", short: "x", as_of: null }],
  ] as const;

  it.each(CASES_1)("reads %s as not screened, never as a pass", (_what, raw) => {
    expect(parseStatus(raw).verdict).toBe("NOT_SCREENED");
    expect(parseStatus(raw).data_status).toBe("NOT_SCREENED");
  });

  it("keeps a result that is backed by a known data status", () => {
    expect(parseStatus(COMPLIANT_ROW)).toEqual(COMPLIANT_ROW);
  });
});

describe("the list of stocks to ask about", () => {
  it("is upper case, without repeats and in a fixed order", () => {
    expect(normalizeSymbols([" tcs", "INFY", "tcs", ""])).toEqual(["INFY", "TCS"]);
  });

  it("is cut into batches", () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
  });
});

describe("useShariahStatuses", () => {
  it("asks once for a list, and not again for the same list on another screen", async () => {
    routeApi({ "GET /api/v2/status": statusFor(true), [statusUrl("AAA")]: statuses({ AAA: COMPLIANT_ROW }) });
    renderPage(
      <>
        <Probe symbols={["AAA"]} />
        <Probe symbols={["aaa"]} />
      </>,
    );
    await waitFor(() => expect(screen.getAllByText("ready|COMPLIANT|no note")).toHaveLength(2));
    expect(callsTo("GET", statusUrl("AAA").slice(4))).toHaveLength(1);
  });

  it("asks nothing in Institutional mode, unless a screen insists", async () => {
    routeApi({ "GET /api/v2/status": statusFor(false), [statusUrl("AAA")]: statuses({ AAA: COMPLIANT_ROW }) });
    renderPage(
      <>
        <Probe symbols={["AAA"]} />
        <Probe symbols={["AAA"]} always />
      </>,
    );
    await waitFor(() => expect(screen.getAllByText("ready|COMPLIANT|no note")).toHaveLength(1));
    expect(screen.getAllByText("off|none|no note")).toHaveLength(1);
  });

  it("treats a missing status call as not screened, with a note", async () => {
    routeApi({
      "GET /api/v2/status": statusFor(true),
      [statusUrl("AAA")]: () => {
        throw new ApiError("HTTP_404", "Not Found", 404);
      },
    });
    renderPage(<Probe symbols={["AAA"]} />);
    const words = "unavailable|NOT_SCREENED|Shariah status is not available right now.";
    expect(await screen.findByText(words)).toBeInTheDocument();
  });
});
