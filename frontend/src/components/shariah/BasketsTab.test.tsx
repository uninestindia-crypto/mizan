import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SECOND_OPINION_EVENT } from "../../lib/copilot";
import { basketPickNote } from "../../lib/picks";
import type { ShariahBasket, ShariahBasketConstituent } from "../../lib/types";
import { BasketsTab } from "./BasketsTab";
import { basket } from "./shariahFixtures";

afterEach(cleanup);

function stock(symbol: string, weight: number, price: number | null, status: string): ShariahBasketConstituent {
  return {
    ticker: `${symbol}.NS`,
    symbol,
    company_name: `${symbol} Limited`,
    weight,
    current_price: price,
    price_status: status,
  };
}

/** What the engine used to send: typed return and risk numbers and a price on every stock. */
function olderBasket(): ShariahBasket {
  const typed = {
    expected_cagr: 0.148,
    expected_sharpe: 1.12,
    cagr: 0.148,
    sharpe_ratio: 1.12,
    annualized_volatility: 0.128,
    max_drawdown: -0.145,
    beta: 0.93,
    dividend_yield: 0.0275,
    weighted_purification_ratio: 0.0069,
  };
  return {
    ...basket({ performance: undefined, history_status: undefined, history_message: undefined }),
    ...typed,
    constituents: [
      { ticker: "TCS.NS", symbol: "TCS", company_name: "Tata Consultancy", weight: 0.25, current_price: 4210.5 },
    ],
  } as ShariahBasket;
}

describe("BasketsTab, no assumed numbers", () => {
  it("says the basket is not back-tested instead of showing return or risk figures", () => {
    render(<BasketsTab baskets={[basket()]} />);
    expect(screen.getByText("Not computed yet.")).toBeInTheDocument();
    expect(screen.getByText(/has not back-tested this basket, so no return or risk figure is shown\./)).toBeVisible();
  });

  it.each(["assumed", "cagr", "sharpe", "drawdown", "volatility", "beta"])("never mentions %s", (word) => {
    const { container } = render(<BasketsTab baskets={[basket()]} />);
    expect((container.textContent ?? "").toLowerCase()).not.toContain(word);
  });

  it("shows the same honest state for an older response that still carries typed numbers", () => {
    render(<BasketsTab baskets={[olderBasket()]} />);
    expect(screen.getByText("Not computed yet.")).toBeInTheDocument();
  });

  it.each(["14.8", "1.12", "12.8", "14.5", "0.93", "2.75", "4,210", "0.69"])(
    "does not show the old typed number %s",
    (typed) => {
      const { container } = render(<BasketsTab baskets={[olderBasket()]} />);
      expect(container.textContent ?? "").not.toContain(typed);
    },
  );

  it("says no rebalances have been recorded", () => {
    render(<BasketsTab baskets={[basket()]} />);
    expect(screen.getByText("No rebalances have been recorded yet.")).toBeInTheDocument();
  });

  it("says it even when the response has no history fields at all", () => {
    render(<BasketsTab baskets={[olderBasket()]} />);
    expect(screen.getByText("No rebalances have been recorded yet.")).toBeInTheDocument();
  });
});

describe("BasketsTab, prices and data status", () => {
  it("shows a price only with its status words", () => {
    const sample = basket({
      constituents: [
        stock("TCS", 0.5, 4210.5, "SAMPLE"),
        stock("INFY", 0.3, null, "SAMPLE"),
        stock("WIPRO", 0.2, null, "NOT_AVAILABLE"),
      ],
    });
    render(<BasketsTab baskets={[sample]} />);
    expect(screen.getByText("₹4,210.50 · Sample price")).toBeInTheDocument();
    expect(screen.getByText("Sample price")).toBeInTheDocument();
    expect(screen.getByText("No price")).toBeInTheDocument();
  });

  it("never shows a number whose status it does not know", () => {
    render(<BasketsTab baskets={[olderBasket()]} />);
    expect(screen.getByText("No price")).toBeInTheDocument();
    expect(screen.queryByText(/4,210/)).toBeNull();
  });

  it("puts each stock's screening result and its data status side by side", () => {
    const screened = {
      aaoifi_status: "COMPLIANT",
      tasis_status: "QUESTIONABLE",
      data_status: "UNVERIFIED_SAMPLE",
    } as const;
    const tcs = { ...stock("TCS", 0.5, null, "SAMPLE"), ...screened };
    render(<BasketsTab baskets={[basket({ constituents: [tcs] })]} />);
    const row = screen.getByText("TCS").closest("li") as HTMLElement;
    expect(within(row).getByText("Questionable")).toBeInTheDocument();
    expect(within(row).getByText("Illustrative sample, not audited")).toBeInTheDocument();
  });

  it("says a stock has no screening result, and Not verified, when the engine sends none", () => {
    render(<BasketsTab baskets={[basket({ constituents: [stock("TCS", 0.5, null, "SAMPLE")] })]} />);
    const row = screen.getByText("TCS").closest("li") as HTMLElement;
    expect(within(row).getByText("No screening result")).toBeInTheDocument();
    expect(within(row).getByText("Not verified")).toBeInTheDocument();
  });
});

describe("BasketsTab, wording and second opinion", () => {
  it("calls the sheet an order-sheet export and says QuantOS places no orders", () => {
    render(<BasketsTab baskets={[basket()]} />);
    expect(screen.getByText("Order-sheet export")).toBeInTheDocument();
    const promise = "QuantOS does not place orders. It prepares a sheet you can use at your broker.";
    expect(screen.getByText(promise)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Order sheet unavailable" })).toBeDisabled();
  });

  it.each(["1-Click", "Pre-audited", "Shipped", "100% Shariah"])("does not use the words %s", (banned) => {
    const { container } = render(<BasketsTab baskets={[basket()]} />);
    expect(container.textContent ?? "").not.toContain(banned);
  });

  it("opens a second opinion on a stock the basket lists, with the pick note", () => {
    const heard: unknown[] = [];
    const listener = (event: Event) => heard.push((event as CustomEvent).detail);
    window.addEventListener(SECOND_OPINION_EVENT, listener);
    render(<BasketsTab baskets={[basket()]} />);
    const row = screen.getByText("TCS").closest("li") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Get a second opinion on TCS" }));
    window.removeEventListener(SECOND_OPINION_EVENT, listener);
    expect(heard).toEqual([{ symbol: "TCS", pickNote: basketPickNote("Halal Tech Giants", "TCS") }]);
  });

  it("gives every listed stock its own second-opinion button", () => {
    render(<BasketsTab baskets={[basket()]} />);
    expect(screen.getAllByRole("button", { name: /Get a second opinion on/ })).toHaveLength(2);
  });
});
