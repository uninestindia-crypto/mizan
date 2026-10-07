import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import { SECOND_OPINION_EVENT } from "../lib/copilot";
import type { PaperPosition } from "../lib/types";
import { PaperPositionsCard } from "./PaperPositions";

const BASE = {
  quantity: 10,
  average_price: 3000,
  last_close: 3100,
  market_value: 31000,
  unrealized_pnl: 1000,
  weight: 0.4,
};
const POSITIONS: PaperPosition[] = [
  { ...BASE, symbol: "TCS" },
  { ...BASE, symbol: "INFY", quantity: 5, unrealized_pnl: -250, weight: 0.1 },
];

afterEach(cleanup);

function heard(): { detail: unknown[]; stop: () => void } {
  const detail: unknown[] = [];
  const listener = (event: Event) => detail.push((event as CustomEvent).detail);
  window.addEventListener(SECOND_OPINION_EVENT, listener);
  return { detail, stop: () => window.removeEventListener(SECOND_OPINION_EVENT, listener) };
}

describe("PaperPositionsCard", () => {
  it("says so when the book holds nothing", () => {
    render(<PaperPositionsCard positions={[]} bookName="XS Monthly" />, { wrapper: MemoryRouter });
    expect(screen.getByText("It holds no shares yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /second opinion/i })).toBeNull();
  });

  it("lists each held stock with a second-opinion button", () => {
    render(<PaperPositionsCard positions={POSITIONS} bookName="XS Monthly" />, { wrapper: MemoryRouter });
    expect(screen.getByRole("link", { name: "TCS" })).toHaveAttribute("href", "/stock/TCS");
    expect(screen.getAllByRole("button", { name: /Get a second opinion on/ })).toHaveLength(2);
  });

  it("asks for a second opinion on that stock and says it is held by this book's rule", () => {
    const listening = heard();
    render(<PaperPositionsCard positions={POSITIONS} bookName="XS Monthly" />, { wrapper: MemoryRouter });
    fireEvent.click(screen.getByRole("button", { name: "Get a second opinion on INFY" }));
    listening.stop();
    expect(listening.detail).toHaveLength(1);
    const { symbol, pickNote } = listening.detail[0] as { symbol: string; pickNote: string };
    expect(symbol).toBe("INFY");
    expect(pickNote).toContain('INFY is currently held by the paper book "XS Monthly"');
    expect(pickNote).toContain("not evidence the stock will do well");
  });
});
