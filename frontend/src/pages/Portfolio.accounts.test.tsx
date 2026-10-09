import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, deferred } from "../components/agents/testHarness";
import { forgetHiddenChoices } from "../components/mode/hiddenChoice";
import {
  ACCOUNT_LINES,
  ASHA_ONLY,
  EVERYTHING,
  NOTHING_AT_ALL,
  engine,
  renderAt,
} from "../components/portfolio/portfolioKit";
import { ApiError, api } from "../lib/api";
import Portfolio from "./Portfolio";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const where = () => screen.getByTestId("where").textContent;
const showing = () => screen.getByTestId("portfolio-scope");
const choose = async (name: string) => fireEvent.click(await screen.findByRole("radio", { name: new RegExp(name) }));

describe("choosing an account", () => {
  it("shows every account together at first, with a line that says so", async () => {
    engine();
    renderAt(<Portfolio />);
    expect((await screen.findByTestId("portfolio-scope")).textContent).toBe("Showing: All accounts · 3 accounts");
    expect(screen.getByRole("radio", { name: /All accounts/ })).toBeChecked();
  });

  it("shows one account alone when its button is pressed, and puts it in the address", async () => {
    engine();
    renderAt(<Portfolio />);
    await choose("Asha's Zerodha");
    await screen.findByText("Asha · Demat account · Zerodha", { exact: false });
    expect(showing().textContent).toContain("Asha's Zerodha");
    expect(where()).toBe("/portfolio?account=2");
    expect(callsTo("GET", "/api/v2/portfolio?account=2")).toHaveLength(1);
  });

  it("shows one account alone when its card is pressed", async () => {
    engine();
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("button", { name: "Show only Asha's Zerodha" }));
    await screen.findByText(/Asha · Demat account · Zerodha/);
    expect(where()).toBe("/portfolio?account=2");
  });

  it("opens straight on the account named in the address, without asking for everything first", async () => {
    engine();
    renderAt(<Portfolio />, "/portfolio?account=2");
    await screen.findByRole("table", { name: "Holdings by stock" });
    expect(callsTo("GET", "/api/v2/portfolio")).toHaveLength(0);
    expect(screen.getByRole("radio", { name: /Asha's Zerodha/ })).toBeChecked();
  });

  it("brings back all accounts when that button is pressed", async () => {
    engine();
    renderAt(<Portfolio />, "/portfolio?account=2");
    await choose("All accounts");
    await screen.findByRole("list", { name: "Your accounts" });
    expect(where()).toBe("/portfolio?account=all");
  });
});

describe("remembering the choice", () => {
  it("opens on the account chosen last time and puts it in the address", async () => {
    localStorage.setItem("quantos.portfolio.account", "2");
    engine();
    renderAt(<Portfolio />);
    await screen.findByRole("table", { name: "Holdings by stock" });
    expect(where()).toBe("/portfolio?account=2");
    expect(callsTo("GET", "/api/v2/portfolio")).toHaveLength(0);
  });

  it("keeps the choice for the next visit", async () => {
    engine();
    renderAt(<Portfolio />);
    await choose("Asha's Zerodha");
    await screen.findByRole("table", { name: "Holdings by stock" });
    expect(localStorage.getItem("quantos.portfolio.account")).toBe("2");
  });

  it("lets the address win over the remembered choice", async () => {
    localStorage.setItem("quantos.portfolio.account", "2");
    engine();
    renderAt(<Portfolio />, "/portfolio?account=all");
    await screen.findByRole("list", { name: "Your accounts" });
    expect(where()).toBe("/portfolio?account=all");
  });

  it("works when the browser will not keep anything", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    engine();
    renderAt(<Portfolio />);
    await choose("Asha's Zerodha");
    await screen.findByText(/Asha · Demat account · Zerodha/);
    expect(where()).toBe("/portfolio?account=2");
  });
});

describe("an account that is gone", () => {
  const gone = () => {
    throw new ApiError("ACCOUNT_NOT_FOUND", "That account does not exist.", 404);
  };

  it("says so in the server's words and offers all accounts", async () => {
    engine({ "GET /api/v2/portfolio?account=99": gone });
    renderAt(<Portfolio />, "/portfolio?account=99");
    expect(await screen.findByText("That account does not exist.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all accounts" }));
    await screen.findByRole("list", { name: "Your accounts" });
    expect(where()).toBe("/portfolio?account=all");
  });
});

describe("empty accounts", () => {
  it("says an account with nothing in it has nothing in it, and offers to add the first holding", async () => {
    engine();
    renderAt(<Portfolio />, "/portfolio?account=3");
    expect(await screen.findByText("No holdings in this account yet. Add your first one.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add your first holding" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Papa's HUF/ })).toBeChecked();
  });

  it("keeps the account cards when no account holds anything yet", async () => {
    engine({ "GET /api/v2/portfolio": NOTHING_AT_ALL });
    renderAt(<Portfolio />);
    expect(await screen.findByText("Track what you own")).toBeInTheDocument();
    const cards = within(screen.getByRole("list", { name: "Your accounts" }));
    expect(cards.getAllByText("No holdings yet")).toHaveLength(3);
  });
});

describe("one account only", () => {
  const ONE = { ...EVERYTHING, accounts: [ACCOUNT_LINES[0]] };

  it("shows no switcher, no cards and no account words, so nobody sees clutter", async () => {
    engine({ "GET /api/v2/portfolio": ONE });
    renderAt(<Portfolio />);
    await screen.findByRole("table", { name: "Holdings by stock" });
    expect(screen.queryByRole("radiogroup", { name: "Choose an account" })).toBeNull();
    expect(screen.queryByRole("list", { name: "Your accounts" })).toBeNull();
    expect(screen.queryByTestId("portfolio-scope")).toBeNull();
    expect(screen.getByRole("button", { name: "Manage accounts" })).toBeInTheDocument();
  });

  it("leaves the Account column out of the lots", async () => {
    engine({ "GET /api/v2/portfolio": ONE });
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("radio", { name: "By lot" }));
    const lots = within(await screen.findByRole("table", { name: "Holdings by lot" }));
    expect(lots.queryByRole("columnheader", { name: "Account" })).toBeNull();
  });
});

describe("the totals follow the account in view", () => {
  it("shows that account's value, not everything's", async () => {
    engine();
    renderAt(<Portfolio />, "/portfolio?account=2");
    await screen.findByRole("table", { name: "Holdings by stock" });
    const value = screen.getByText("Current value").parentElement!;
    expect(within(value).getByText("₹1,800")).toBeInTheDocument();
    expect(within(value).getByText("Invested ₹1,500")).toBeInTheDocument();
  });
});

describe("while another account loads", () => {
  it("keeps the switcher and the account on screen, so a keyboard user keeps their place", async () => {
    const later = deferred<unknown>();
    engine({ "GET /api/v2/portfolio?account=2": () => later.promise });
    renderAt(<Portfolio />);
    await screen.findByRole("list", { name: "Your accounts" });
    const radio = screen.getByRole("radio", { name: /Asha's Zerodha/ });
    radio.focus();
    fireEvent.click(radio);
    await vi.waitFor(() => expect(callsTo("GET", "/api/v2/portfolio?account=2")).toHaveLength(1));
    expect(screen.getByRole("radio", { name: /Asha's Zerodha/ })).toBe(radio);
    expect(radio).toHaveFocus();
    expect(screen.getByRole("table", { name: "Holdings by stock" })).toBeInTheDocument();
    later.resolve(ASHA_ONLY);
    await screen.findByText("Asha · Demat account · Zerodha", { exact: false });
  });
});
