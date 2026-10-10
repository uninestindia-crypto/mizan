import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../lib/api";
import { callsTo, deferred, routeApi } from "../agents/testHarness";
import { forgetHiddenChoices } from "./hiddenChoice";
import {
  COMPLIANT_ROW,
  NON_COMPLIANT_ROW,
  NOT_SCREENED_ROW,
  QUESTIONABLE_ROW,
  renderPage,
  statuses,
  statusFor,
  statusUrl,
} from "./modeKit";
import { ModeFilterNote } from "./ModeFilterNote";
import { useModeFilter } from "./useModeFilter";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

function List({ symbols, scope = "test" }: { symbols: string[]; scope?: string }) {
  const filter = useModeFilter(symbols, scope);
  return (
    <>
      <ModeFilterNote filter={filter} />
      <ul aria-label="stocks">
        {filter.visible.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </>
  );
}

const statusCalls = () =>
  vi.mocked(api).mock.calls.map(([path]) => String(path)).filter((path) => path.includes("/shariah/status"));
const names = () => screen.queryAllByRole("listitem").map((li) => li.textContent);
const MIXED = { AAA: COMPLIANT_ROW, BBB: NON_COMPLIANT_ROW, CCC: NOT_SCREENED_ROW, DDD: QUESTIONABLE_ROW };

function engine(shariah: boolean, status: unknown = statuses(MIXED), symbols = ["AAA", "BBB", "CCC", "DDD"]) {
  routeApi({ "GET /api/v2/status": statusFor(shariah), [statusUrl(...symbols)]: status });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
});
afterEach(cleanup);

describe("in Shariah mode", () => {
  it("shows only the compliant stocks, and says how many are hidden and why", async () => {
    engine(true);
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} />);
    expect(await screen.findByText(/Showing only Shariah-compliant stocks\. 3 hidden\./)).toBeInTheDocument();
    expect(names()).toEqual(["AAA"]);
    expect(screen.getByText("Not compliant, questionable or not screened yet.")).toBeInTheDocument();
  });

  it("shows every stock when asked, with the right count, and hides them again on request", async () => {
    engine(true);
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Show them" }));
    expect(names()).toEqual(["AAA", "BBB", "CCC", "DDD"]);
    expect(screen.getByText(/Showing every stock, including 3 that are not confirmed as Shariah/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hide them again" }));
    expect(names()).toEqual(["AAA"]);
  });

  it("keeps the choice for the session, even when the list is shown again", async () => {
    engine(true);
    const first = renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Show them" }));
    first.unmount();
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} />);
    await screen.findByRole("button", { name: "Hide them again" });
    expect(names()).toEqual(["AAA", "BBB", "CCC", "DDD"]);
  });

  it("keeps each list's choice separate", async () => {
    engine(true);
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} scope="one" />);
    fireEvent.click(await screen.findByRole("button", { name: "Show them" }));
    cleanup();
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} scope="two" />);
    expect(await screen.findByRole("button", { name: "Show them" })).toBeInTheDocument();
    expect(names()).toEqual(["AAA"]);
  });

  it("shows the whole list, not an empty one, while the results are on their way", async () => {
    const slow = deferred<unknown>();
    engine(true, slow.promise);
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} />);
    expect(await screen.findByText("Checking Shariah status...")).toBeInTheDocument();
    expect(names()).toEqual(["AAA", "BBB", "CCC", "DDD"]);
    slow.resolve(statuses(MIXED));
    await waitFor(() => expect(names()).toEqual(["AAA"]));
    expect(screen.queryByText("Checking Shariah status...")).toBeNull();
  });

  it("says so, and names the next clicks, when hiding would leave nothing", async () => {
    engine(true, statuses({ BBB: NON_COMPLIANT_ROW, CCC: NOT_SCREENED_ROW }), ["BBB", "CCC"]);
    renderPage(<List symbols={["BBB", "CCC"]} />);
    expect(await screen.findByText(/All 2 stocks are hidden, because none of them is Shariah/)).toBeInTheDocument();
    expect(names()).toEqual([]);
    expect(screen.getByRole("link", { name: "Find Shariah-compliant stocks" })).toHaveAttribute("href", "/shariah");
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    expect(names()).toEqual(["BBB", "CCC"]);
  });

  it("says nothing when every stock is compliant", async () => {
    engine(true, statuses({ AAA: COMPLIANT_ROW }), ["AAA"]);
    renderPage(<List symbols={["AAA"]} />);
    await waitFor(() => expect(callsTo("GET", statusUrl("AAA").slice(4))).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText("Checking Shariah status...")).toBeNull());
    expect(screen.queryByTestId("mode-filter-note")).toBeNull();
    expect(names()).toEqual(["AAA"]);
  });

  it("never treats a stock the engine does not mention as compliant", async () => {
    engine(true, statuses({ AAA: COMPLIANT_ROW }), ["AAA", "ZZZ"]);
    renderPage(<List symbols={["AAA", "ZZZ"]} />);
    expect(await screen.findByText(/1 hidden/)).toBeInTheDocument();
    expect(names()).toEqual(["AAA"]);
  });

  const CASES_1 = [
    ["is missing from the engine", () => { throw new ApiError("HTTP_404", "Not Found", 404); }],
    ["cannot be reached", () => { throw new ApiError("ENGINE_OFFLINE", "offline", 0); }],
    ["fails", () => { throw new ApiError("HTTP_500", "broken", 500); }],
  ] as const;

  it.each(CASES_1)("counts every stock as not screened, and says so, when the status call %s", async (_why, answer) => {
    routeApi({ "GET /api/v2/status": statusFor(true), [statusUrl("AAA", "BBB")]: answer });
    renderPage(<List symbols={["AAA", "BBB"]} />);
    expect(await screen.findByText(/Shariah status is not available right now\./)).toBeInTheDocument();
    expect(names()).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    expect(names()).toEqual(["AAA", "BBB"]);
  });

  it("asks in batches of at most 200 stocks", async () => {
    const symbols = Array.from({ length: 450 }, (_, i) => `S${String(i).padStart(3, "0")}`);
    routeApi({
      "GET /api/v2/status": statusFor(true),
      ...Object.fromEntries([0, 200, 400].map((from) => [statusUrl(...symbols.slice(from, from + 200)), statuses({})])),
    });
    renderPage(<List symbols={symbols} />);
    await waitFor(() => expect(statusCalls()).toHaveLength(3));
    expect(statusCalls().map((url) => url.split("=")[1]?.split(",").length)).toEqual([200, 200, 50]);
  });

  it("reads a stock's symbol from an item, in any case", async () => {
    routeApi({ "GET /api/v2/status": statusFor(true), [statusUrl("AAA")]: statuses({ AAA: COMPLIANT_ROW }) });
    function Items() {
      const filter = useModeFilter([{ symbol: "aaa", name: "Alpha" }], "items");
      return <p>{filter.visible.map((i) => i.name)}</p>;
    }
    renderPage(<Items />);
    await waitFor(() => expect(callsTo("GET", statusUrl("AAA").slice(4))).toHaveLength(1));
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });
});

describe("in Institutional mode", () => {
  it("filters nothing, shows no note and never asks for a Shariah result", async () => {
    engine(false);
    renderPage(<List symbols={["AAA", "BBB", "CCC", "DDD"]} />);
    await screen.findByRole("list", { name: "stocks" });
    await waitFor(() => expect(callsTo("GET", "/api/v2/status")).toHaveLength(1));
    expect(names()).toEqual(["AAA", "BBB", "CCC", "DDD"]);
    expect(screen.queryByText(/hidden/)).toBeNull();
    expect(statusCalls()).toHaveLength(0);
  });
});
