import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { renderWithQuery } from "./renderWithQuery";
import { bankAudit, fullAudit, olderAudit } from "./shariahFixtures";
import { StockResultCard } from "./StockResultCard";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

function show(ticker = "TCS.NS", onClose = vi.fn()) {
  renderWithQuery(<StockResultCard ticker={ticker} onClose={onClose} />);
  return onClose;
}

describe("StockResultCard", () => {
  it("shows the verdict with its data status right beside it, and the panel closed", async () => {
    vi.mocked(api).mockResolvedValue(fullAudit());
    show();
    const verdict = await screen.findByRole("group", { name: "Verdict" });
    expect(screen.getByRole("heading", { name: "TCS, Tata Consultancy Services Limited" })).toBeInTheDocument();
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/v2/shariah/stocks/TCS.NS/audit");
    expect(within(verdict).getByText("Compliant")).toBeInTheDocument();
    expect(within(verdict).getByText("Illustrative sample, not audited")).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "How this verdict was reached" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("names the share while the result loads, and says it is loading", async () => {
    vi.mocked(api).mockImplementation(() => new Promise(() => {}));
    show();
    expect(screen.getByRole("heading", { name: "Screening result for TCS" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading the screening result");
  });

  it("shows both standards, and when they disagree says why in the screener's own words", async () => {
    const why = "The two standards divide by different totals.";
    vi.mocked(api).mockResolvedValue(fullAudit({ divergence_noted: true, divergence_explanation: why }));
    show();
    expect(await screen.findByText(why)).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "Verdict" })).getAllByText("Passed")).toHaveLength(2);
  });

  it("shows a failed verdict with its status", async () => {
    vi.mocked(api).mockResolvedValue(bankAudit());
    show("HDFCBANK.NS");
    const verdict = await screen.findByRole("group", { name: "Verdict" });
    expect(within(verdict).getByText("Non-Compliant")).toBeInTheDocument();
    expect(within(verdict).getAllByText("Failed")).toHaveLength(2);
  });

  it("says Not verified when an older response has no data status", async () => {
    vi.mocked(api).mockResolvedValue(olderAudit());
    show();
    const verdict = await screen.findByRole("group", { name: "Verdict" });
    expect(within(verdict).getByText("Compliant")).toBeInTheDocument();
    expect(within(verdict).getByText("Not verified")).toBeInTheDocument();
  });

  it("tells a person what to click when the result cannot be loaded", async () => {
    vi.mocked(api).mockImplementation(() => Promise.reject(new Error("offline")));
    show();
    expect(await screen.findByText(/Click Close, then click the company again/)).toBeInTheDocument();
  });

  it("closes with one click", async () => {
    vi.mocked(api).mockResolvedValue(fullAudit());
    const onClose = show();
    await screen.findByRole("group", { name: "Verdict" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });
});
