import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import { SECOND_OPINION_EVENT } from "../lib/copilot";
import type { OrdersFreshness, PaperQueuedOrder } from "../lib/types";
import { OrderTicket } from "./OrderTicket";

const CURRENT: OrdersFreshness = {
  state: "CURRENT",
  as_of: "2026-10-06",
  expected_session: "2026-10-07",
  sessions_missed: 0,
  message: "",
};
const QUEUED: PaperQueuedOrder[] = [
  { side: "BUY", symbol: "TCS", quantity: 10, reference_price: 3100 },
  { side: "SELL", symbol: "INFY", quantity: 5, reference_price: 1450 },
];

const PROPS = {
  orders: CURRENT,
  queued: QUEUED,
  bookName: "XS Monthly",
  bookCapital: 1000000,
  slippageBps: 5,
  bookId: "book1",
  placements: [],
};

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const routed = createElement(MemoryRouter, null, children);
  return createElement(QueryClientProvider, { client }, routed);
}

function renderTicket() {
  return render(<OrderTicket {...PROPS} />, { wrapper: Wrapper });
}

afterEach(cleanup);

function listen(): { detail: Array<{ symbol: string; pickNote: string }>; stop: () => void } {
  const detail: Array<{ symbol: string; pickNote: string }> = [];
  const listener = (event: Event) => detail.push((event as CustomEvent).detail);
  window.addEventListener(SECOND_OPINION_EVENT, listener);
  return { detail, stop: () => window.removeEventListener(SECOND_OPINION_EVENT, listener) };
}

describe("OrderTicket second opinions", () => {
  it("offers a second opinion on every stock the book has queued", () => {
    renderTicket();
    expect(screen.getByRole("button", { name: "Get a second opinion on TCS" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get a second opinion on INFY" })).toBeInTheDocument();
  });

  it("says a queued buy is to be bought by this book's rule", () => {
    const heard = listen();
    renderTicket();
    fireEvent.click(screen.getByRole("button", { name: "Get a second opinion on TCS" }));
    heard.stop();
    expect(heard.detail[0]?.symbol).toBe("TCS");
    expect(heard.detail[0]?.pickNote).toContain('TCS is queued to be bought by the paper book "XS Monthly"');
  });

  it("says a queued sell is to be sold", () => {
    const heard = listen();
    renderTicket();
    fireEvent.click(screen.getByRole("button", { name: "Get a second opinion on INFY" }));
    heard.stop();
    expect(heard.detail[0]?.pickNote).toContain("INFY is queued to be sold by the paper book");
  });
});
