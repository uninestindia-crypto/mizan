import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { toCompliance } from "../../lib/shariah";
import type { ShariahCompliance } from "../../lib/types";
import { renderWithQuery } from "./renderWithQuery";
import { fullAudit } from "./shariahFixtures";
import { ScreenerTab } from "./ScreenerTab";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

function row(over: Partial<ShariahCompliance>): ShariahCompliance {
  return {
    ticker: "TCS.NS",
    symbol: "TCS",
    company_name: "Tata Consultancy Services Limited",
    is_compliant: true,
    aaoifi_compliant: true,
    tasis_compliant: true,
    debt_ratio: 0.0058,
    cash_ratio: 0.0186,
    purification_ratio: 0.0058,
    aaoifi_status: "COMPLIANT",
    tasis_status: "COMPLIANT",
    compliance_status: "COMPLIANT",
    ...over,
  };
}

const ROWS = [
  row({ data_status: "UNVERIFIED_SAMPLE" }),
  row({
    ticker: "HDFCBANK.NS",
    symbol: "HDFCBANK",
    company_name: "HDFC Bank Limited",
    is_compliant: false,
    aaoifi_status: "NON_COMPLIANT",
    tasis_status: "NON_COMPLIANT",
    compliance_status: "NON_COMPLIANT",
  }),
];

function show(summary: ShariahCompliance[] = ROWS) {
  renderWithQuery(<ScreenerTab summary={summary} />);
}

describe("ScreenerTab", () => {
  it("shows each verdict with its data status in the same cell, and Not verified when the list does not say", () => {
    show();
    const tcs = screen.getByRole("row", { name: /TCS/ });
    expect(within(tcs).getByText("Compliant")).toBeInTheDocument();
    expect(within(tcs).getByText("Illustrative sample, not audited")).toBeInTheDocument();
    const bank = screen.getByRole("row", { name: /HDFCBANK/ });
    expect(within(bank).getByText("Non-Compliant")).toBeInTheDocument();
    expect(within(bank).getByText("Not verified")).toBeInTheDocument();
  });

  it("shows a stock that one standard passes and the other fails as Questionable, the word its badge uses", () => {
    const split = toCompliance({
      ticker: "WIPRO.NS",
      symbol: "WIPRO",
      company_name: "Wipro Limited",
      aaoifi_status: "COMPLIANT",
      tasis_status: "NON_COMPLIANT",
      aaoifi_debt_ratio: 0.1,
      aaoifi_cash_ratio: 0.1,
      purification_ratio: 0.002,
    });
    show([split]);
    const line = screen.getByRole("row", { name: /WIPRO/ });
    expect(within(line).getByText("Questionable")).toBeInTheDocument();
    expect(within(line).queryByText("Non-Compliant")).toBeNull();
    expect(within(line).getByText("Passed")).toBeInTheDocument(); // the AAOIFI column still says what AAOIFI said
    expect(within(line).getByText("Failed")).toBeInTheDocument(); // and the TASIS column what TASIS said
  });

  it("keeps a stock both standards fail as Non-Compliant, and filters it as such", () => {
    show([
      toCompliance({
        ticker: "HDFCBANK.NS",
        symbol: "HDFCBANK",
        company_name: "HDFC Bank Limited",
        aaoifi_status: "NON_COMPLIANT",
        tasis_status: "NON_COMPLIANT",
        aaoifi_debt_ratio: 0.88,
        aaoifi_cash_ratio: 0.1,
        purification_ratio: 0.2,
      }),
    ]);
    expect(within(screen.getByRole("row", { name: /HDFCBANK/ })).getByText("Non-Compliant")).toBeInTheDocument();
  });

  it("opens one stock's result with one click, then closes it and gives focus back to the same button", async () => {
    vi.mocked(api).mockResolvedValue(fullAudit());
    show();
    const opener = screen.getByRole("button", { name: "How it was decided for Tata Consultancy Services Limited" });
    fireEvent.click(opener);
    expect(await screen.findByRole("group", { name: "Verdict" })).toBeInTheDocument();
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/v2/shariah/stocks/TCS.NS/audit");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Verdict" })).toBeNull());
    expect(opener).toHaveFocus();
  });

  it("still filters by search and by compliance", () => {
    show();
    fireEvent.change(screen.getByLabelText("Search company or symbol"), { target: { value: "hdfc" } });
    expect(screen.queryByText("TCS")).toBeNull();
    expect(screen.getByText("HDFCBANK")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search company or symbol"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("radio", { name: "Compliant Only" }));
    expect(screen.queryByText("HDFCBANK")).toBeNull();
    expect(screen.getByText(/1 of 2 sample equities shown/)).toBeInTheDocument();
  });

  it("says plainly when nothing matches", () => {
    show();
    fireEvent.change(screen.getByLabelText("Search company or symbol"), { target: { value: "zzz" } });
    expect(screen.getByText("No matching equities")).toBeInTheDocument();
  });
});
