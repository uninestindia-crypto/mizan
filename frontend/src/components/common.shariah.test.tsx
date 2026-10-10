import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { routeApi } from "./agents/testHarness";
import { SymbolSearch } from "./common";
import { forgetHiddenChoices } from "./mode/hiddenChoice";
import { COMPLIANT_ROW, NON_COMPLIANT_ROW, renderPage, statuses, statusFor, statusUrl } from "./mode/modeKit";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const FOUND = [
  { symbol: "TCS", name: "Tata Consultancy", is_etf: false },
  { symbol: "TATAMOTORS", name: "Tata Motors", is_etf: false },
];

function engine(shariah: boolean) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    "GET /api/v2/market/search?q=tata": FOUND,
    [statusUrl("TATAMOTORS", "TCS")]: statuses({ TCS: COMPLIANT_ROW, TATAMOTORS: NON_COMPLIANT_ROW }),
  });
}

async function typeTata() {
  const box = await screen.findByRole("combobox");
  fireEvent.change(box, { target: { value: "tata" } });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
});
afterEach(cleanup);

describe("stock search suggestions", () => {
  it("offer only compliant stocks in Shariah mode, with their labels, and a way to see the rest", async () => {
    engine(true);
    renderPage(<SymbolSearch onPick={() => undefined} />);
    await typeTata();
    expect(await screen.findByText(/Showing only Shariah-compliant stocks\. 1 hidden\./)).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option", { name: /TCS/ })).toHaveTextContent("Compliant");
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(screen.getByRole("option", { name: /TATAMOTORS/ })).toHaveTextContent("Not compliant");
  });

  it("offer every stock, unlabelled, in Institutional mode", async () => {
    engine(false);
    renderPage(<SymbolSearch onPick={() => undefined} />);
    await typeTata();
    expect(await screen.findAllByRole("option")).toHaveLength(2);
    expect(screen.queryByText(/Showing only Shariah-compliant/)).toBeNull();
  });

  it("still picks the stock that was clicked", async () => {
    engine(true);
    const pick = vi.fn();
    renderPage(<SymbolSearch onPick={pick} />);
    await typeTata();
    fireEvent.mouseDown(await screen.findByRole("option", { name: /TCS/ }));
    expect(pick).toHaveBeenCalledWith("TCS");
  });
});
