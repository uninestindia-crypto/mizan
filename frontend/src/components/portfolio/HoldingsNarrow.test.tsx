import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Portfolio from "../../pages/Portfolio";
import { api } from "../../lib/api";
import { forgetHiddenChoices } from "../mode/hiddenChoice";
import { engine, renderAt } from "./portfolioKit";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const PHONE = { matches: true, addEventListener: () => undefined, removeEventListener: () => undefined };

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
  localStorage.clear();
  vi.stubGlobal("matchMedia", () => PHONE);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const headings = (table: HTMLElement) => within(table).getAllByRole("columnheader").map((h) => h.textContent);

describe("holdings on a phone", () => {
  it("lists stocks with only Stock, Value and Gain, and puts the shares and price under the name", async () => {
    engine();
    renderAt(<Portfolio />);
    const table = await screen.findByRole("table", { name: "Holdings by stock" });
    expect(headings(table)).toEqual(["Stock", "Value and gain"]);
    expect(within(table).getByText("15 shares at 100.00")).toBeInTheDocument();
    expect(within(table).getByText("In 2 accounts")).toBeInTheDocument();
  });

  it("lists lots with the day, the shares and the account under the name", async () => {
    engine();
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("radio", { name: "By lot" }));
    const table = await screen.findByRole("table", { name: "Holdings by lot" });
    expect(headings(table)).toEqual(["Stock", "Value and gain"]);
    expect(within(table).getByText("Bought 3 Feb 2026 · Asha's Zerodha")).toBeInTheDocument();
    expect(within(table).getByText("5 shares at 100.00")).toBeInTheDocument();
  });

  it("keeps the buttons that change or remove a purchase", async () => {
    engine();
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("radio", { name: "By lot" }));
    const table = await screen.findByRole("table", { name: "Holdings by lot" });
    expect(within(table).getByRole("button", { name: /^Edit TCS bought 3 Feb 2026/ })).toBeInTheDocument();
    expect(within(table).getByRole("button", { name: /^Remove TCS bought 3 Feb 2026/ })).toBeInTheDocument();
  });

  it("still opens a stock to show which account holds how many shares", async () => {
    engine();
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("button", { name: "Show which accounts hold TCS" }));
    const places = within(screen.getByRole("list", { name: "Accounts holding TCS" }));
    expect(places.getByText("My account")).toBeInTheDocument();
  });
});
