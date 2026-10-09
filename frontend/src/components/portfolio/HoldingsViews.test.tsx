import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";
import { forgetHiddenChoices } from "../mode/hiddenChoice";
import Portfolio from "../../pages/Portfolio";
import { api } from "../../lib/api";
import { ASHA_ONLY, engine, renderAt } from "./portfolioKit";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
  localStorage.clear();
});
afterEach(cleanup);

const byStock = async () => within(await screen.findByRole("table", { name: "Holdings by stock" }));
const byLot = async () => {
  fireEvent.click(await screen.findByRole("radio", { name: "By lot" }));
  return within(await screen.findByRole("table", { name: "Holdings by lot" }));
};

describe("holdings by stock", () => {
  it("lists one line for each stock across the accounts, with the shares added up", async () => {
    engine();
    renderAt(<Portfolio />);
    const stocks = await byStock();
    const tcs = within(stocks.getByRole("link", { name: "TCS" }).closest("tbody")!);
    expect(tcs.getByText("15")).toBeInTheDocument();
    expect(tcs.getByText("₹1,800")).toBeInTheDocument();
    expect(tcs.getByText("60.0%")).toBeInTheDocument();
    expect(stocks.getAllByRole("link", { name: "TCS" })).toHaveLength(1);
  });

  it("opens a stock to show which account holds how many shares, and closes it again", async () => {
    engine();
    renderAt(<Portfolio />);
    const open = await screen.findByRole("button", { name: "Show which accounts hold TCS" });
    expect(open).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(open);
    const places = within(screen.getByRole("list", { name: "Accounts holding TCS" }));
    expect(places.getByText("My account")).toBeInTheDocument();
    expect(places.getByText(/10 shares/)).toBeInTheDocument();
    expect(places.getByText("Asha's Zerodha")).toBeInTheDocument();
    expect(places.getByText(/5 shares/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hide which accounts hold TCS" }));
    expect(screen.queryByRole("list", { name: "Accounts holding TCS" })).toBeNull();
  });

  it("says which account a stock sits in when only one holds it", async () => {
    engine();
    renderAt(<Portfolio />);
    const stocks = await byStock();
    expect(stocks.getByText("In Asha's Zerodha")).toBeInTheDocument();
    expect(stocks.getByText("In 2 accounts")).toBeInTheDocument();
  });

  it("adds two purchases in one account into one line when the stock is opened", async () => {
    engine({ "GET /api/v2/portfolio?account=2": tcsBoughtTwiceByAsha() });
    renderAt(<Portfolio />, "/portfolio?account=2");
    fireEvent.click(await screen.findByRole("button", { name: "Show which accounts hold TCS" }));
    const places = within(screen.getByRole("list", { name: "Accounts holding TCS" }));
    expect(places.getAllByRole("listitem")).toHaveLength(1);
    expect(places.getByText(/12 shares/)).toBeInTheDocument();
  });
});

function tcsBoughtTwiceByAsha() {
  const asha = { account_id: 2, account_name: "Asha's Zerodha" };
  const [tcs, ...rest] = ASHA_ONLY.positions;
  const accounts = [{ ...asha, quantity: 5, value: 600 }, { ...asha, quantity: 7, value: 840 }];
  return { ...ASHA_ONLY, positions: [{ ...tcs, accounts }, ...rest] };
}

describe("holdings by lot", () => {
  it("lists every purchase with its account and the day it was bought", async () => {
    engine();
    renderAt(<Portfolio />);
    const lots = await byLot();
    expect(lots.getByRole("columnheader", { name: "Account" })).toBeInTheDocument();
    expect(lots.getAllByRole("link", { name: "TCS" })).toHaveLength(2);
    expect(lots.getAllByText("2 Jan 2026")).toHaveLength(2);
    expect(lots.getByText("3 Feb 2026")).toBeInTheDocument();
    expect(lots.getAllByText("Asha's Zerodha")).toHaveLength(2);
  });

  it("goes back to one line for each stock", async () => {
    engine();
    renderAt(<Portfolio />);
    await byLot();
    fireEvent.click(screen.getByRole("radio", { name: "By stock" }));
    expect(await screen.findByRole("table", { name: "Holdings by stock" })).toBeInTheDocument();
  });

  it("names the account and the day on the buttons that change or remove a purchase", async () => {
    engine();
    renderAt(<Portfolio />);
    const lots = await byLot();
    expect(lots.getByRole("button", { name: "Edit TCS bought 3 Feb 2026 in Asha's Zerodha" })).toBeInTheDocument();
    expect(lots.getByRole("button", { name: "Remove TCS bought 2 Jan 2026 in My account" })).toBeInTheDocument();
  });
});

describe("removing a purchase", () => {
  it("asks first, names the account, and removes only that purchase", async () => {
    engine({ "DELETE /api/v2/portfolio/holdings/1": { deleted: true } });
    renderAt(<Portfolio />);
    const lots = await byLot();
    fireEvent.click(lots.getByRole("button", { name: "Remove TCS bought 2 Jan 2026 in My account" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Remove TCS in My account?" }));
    fireEvent.click(dialog.getByRole("button", { name: "Remove" }));
    await vi.waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledWith("/api/v2/portfolio/holdings/1", "DELETE"));
  });
});

describe.each(["By stock", "By lot"])("Shariah mode, %s", (view) => {
  const open = async () => {
    engine({}, true);
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("radio", { name: view }));
    return within(await screen.findByRole("table", { name: `Holdings ${view.toLowerCase()}` }));
  };

  it("lists the compliant stocks, says how many are hidden and that the totals still count them", async () => {
    const table = await open();
    expect(table.getAllByRole("link", { name: "TCS" }).length).toBeGreaterThan(0);
    expect(table.queryByRole("link", { name: "INFY" })).toBeNull();
    expect(screen.getByText(/Showing only Shariah-compliant stocks\. 1 hidden\./)).toBeInTheDocument();
    expect(screen.getByText("The totals above still include them.")).toBeInTheDocument();
  });

  it("shows the hidden stock, labelled, on request", async () => {
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Show them" }));
    expect(await screen.findByRole("link", { name: /Not compliant/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "INFY" }).length).toBeGreaterThan(0);
  });
});

test("Institutional mode lists every holding with no label in either view", async () => {
  engine();
  renderAt(<Portfolio />);
  const stocks = await byStock();
  expect(stocks.getByRole("link", { name: "INFY" })).toBeInTheDocument();
  expect(screen.queryByText("Compliant")).toBeNull();
  const lots = await byLot();
  expect(lots.getByRole("link", { name: "INFY" })).toBeInTheDocument();
});
