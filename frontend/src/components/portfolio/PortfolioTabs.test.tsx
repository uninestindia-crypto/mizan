import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EVERYTHING } from "./portfolioKit";
import { PortfolioTabs, type PortfolioTab, type TabContext } from "./PortfolioTabs";
import { PORTFOLIO_TABS } from "./tabRegistry";

afterEach(cleanup);

const CONTEXT = {
  data: EVERYTHING,
  choice: "all",
  showAccounts: true,
  onEdit: vi.fn(),
  onRemove: vi.fn(),
} as unknown as TabContext;

const tab = (id: string, label: string): PortfolioTab => ({ id, label, render: () => <p>{label} content</p> });

describe("the Portfolio tabs", () => {
  it("lists Holdings, then Fundamentals, then Risk", () => {
    expect(PORTFOLIO_TABS.map((t) => t.id)).toEqual(["holdings", "fundamentals", "risk"]);
  });

  it("shows a single tab's content with no row of tabs", () => {
    render(<PortfolioTabs tabs={[tab("holdings", "Holdings")]} context={CONTEXT} />);
    expect(screen.getByText("Holdings content")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).toBeNull();
  });

  it("shows a row of tabs when another is added to the list, and switches between them", () => {
    render(<PortfolioTabs tabs={[tab("holdings", "Holdings"), tab("later", "Fundamentals")]} context={CONTEXT} />);
    expect(screen.getByRole("tab", { name: "Holdings" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Holdings content");
    fireEvent.click(screen.getByRole("tab", { name: "Fundamentals" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Fundamentals content");
  });

  it("moves between tabs with the arrow keys", () => {
    render(<PortfolioTabs tabs={[tab("holdings", "Holdings"), tab("later", "Fundamentals")]} context={CONTEXT} />);
    fireEvent.keyDown(screen.getByRole("tab", { name: "Holdings" }), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Fundamentals" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Fundamentals content");
  });

  it("gives each tab what it needs to show the portfolio in view", () => {
    const seen = vi.fn(() => <p>seen</p>);
    render(<PortfolioTabs tabs={[{ id: "x", label: "X", render: seen }]} context={CONTEXT} />);
    expect(seen).toHaveBeenCalledWith(expect.objectContaining({ choice: "all", showAccounts: true }));
  });
});
