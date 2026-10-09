import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { renderWithQuery } from "./renderWithQuery";
import { ZakatTab } from "./ZakatTab";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("ZakatTab", () => {
  it("asks for the portfolio value and the method, and shows the calculation", async () => {
    vi.mocked(api).mockResolvedValue({
      method: "active",
      rate_pct: 2.5,
      zakatable_base: 500000,
      portfolio_value: 500000,
      nisab_threshold: 53550,
      is_obligatory: true,
      zakat_due: 12500,
      method_notes: "Rule notes.",
    });
    renderWithQuery(<ZakatTab />);
    expect(screen.getByText("No assessment calculated yet")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Long-term Investor/ }));
    fireEvent.click(screen.getByRole("button", { name: "Calculate Zakat Due" }));
    await waitFor(() => expect(screen.getByText("Total Zakat Due")).toBeInTheDocument());
    expect(vi.mocked(api)).toHaveBeenCalledWith("/api/v2/shariah/zakat/calculate", "POST", {
      portfolio_value: 500000,
      calculation_method: "INVESTOR_NET_WORKING_CAPITAL",
    });
    expect(screen.getByText("Yes (Above Nisab)")).toBeInTheDocument();
  });
});
