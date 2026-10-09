import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";
import Portfolio from "../../pages/Portfolio";
import { api } from "../../lib/api";
import { callsTo } from "../agents/testHarness";
import { COMPANY_NONE, PORTFOLIO_ALL, PORTFOLIO_EMPTY, PORTFOLIO_STALE } from "../fundamentals/fundamentalsFixtures";
import { ADVICE, GOOD_BAD_COLOURS, refuses } from "../fundamentals/fundamentalsKit";
import { forgetHiddenChoices } from "../mode/hiddenChoice";
import { engine, renderAt } from "./portfolioKit";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const ALL = "GET /api/v2/portfolio/fundamentals?account=all";
const ASHA = "GET /api/v2/portfolio/fundamentals?account=2";

beforeEach(() => {
  vi.mocked(api).mockReset();
  forgetHiddenChoices();
  localStorage.clear();
});
afterEach(cleanup);

async function openTab(answers: Record<string, unknown>, path = "/portfolio") {
  engine({ "GET /api/v2/fundamentals/QQQ": COMPANY_NONE, ...answers });
  const view = renderAt(<Portfolio />, path);
  fireEvent.click(await screen.findByRole("tab", { name: "Fundamentals" }));
  await screen.findByText(PORTFOLIO_ALL.weights_note);
  return view;
}

describe("the Fundamentals tab of the Portfolio", () => {
  it("sits beside Holdings, and the engine's sentences are shown as sent", async () => {
    engine({ [ALL]: PORTFOLIO_ALL });
    renderAt(<Portfolio />);
    expect(await screen.findByRole("tab", { name: "Holdings" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Fundamentals" }));
    expect(await screen.findByText(PORTFOLIO_ALL.statement)).toBeInTheDocument();
    expect(screen.getByText(PORTFOLIO_ALL.weights_note)).toBeInTheDocument();
  });

  it("follows the account in view", async () => {
    await openTab({ [ASHA]: PORTFOLIO_STALE }, "/portfolio?account=2");
    expect(callsTo("GET", "/api/v2/portfolio/fundamentals?account=2")).toHaveLength(1);
    expect(callsTo("GET", "/api/v2/portfolio/fundamentals?account=all")).toHaveLength(0);
  });

  it("shows how many holdings, the weight of the five biggest and the P/E of the lot", async () => {
    await openTab({ [ALL]: PORTFOLIO_ALL });
    const summary = screen.getByText("Holdings", { selector: "div" }).closest("section")!;
    expect(within(summary).getByText("4")).toBeInTheDocument();
    expect(within(summary).getByText("95.0%")).toBeInTheDocument();
    expect(within(summary).getByText("21.64 times")).toBeInTheDocument();
    expect(within(summary).getByText("From 2 of 4 holdings, 84.2% of the weight")).toBeInTheDocument();
  });

  it("explains how the P/E of the lot is worked out, in the engine's words", async () => {
    await openTab({ [ALL]: PORTFOLIO_ALL });
    expect(screen.getByText(PORTFOLIO_ALL.weighted_average_pe.note)).toBeInTheDocument();
  });

  it("shows the weight in each industry group", async () => {
    await openTab({ [ALL]: PORTFOLIO_ALL });
    const groups = within(screen.getByRole("list", { name: "Weight by industry group" }));
    expect(groups.getByText("Information Technology")).toBeInTheDocument();
    expect(groups.getByText("80.0%")).toBeInTheDocument();
    expect(groups.getByText("Metals & Mining")).toBeInTheDocument();
  });

  it("shows each holding's headline figures and the date of its latest quarter", async () => {
    await openTab({ [ALL]: PORTFOLIO_ALL });
    const card = screen.getByRole("link", { name: "AAA" }).closest("li")!;
    expect(within(card).getByText(/Latest quarter ended 31 Dec 2024/)).toBeInTheDocument();
    expect(within(card).getByText("25.5%")).toBeInTheDocument();
    expect(within(card).getByText("0.10 times")).toBeInTheDocument();
    expect(within(card).getByText("78.43 times")).toBeInTheDocument();
    expect(within(card).getByText(/8 inside the rule of thumb, 6 facts/)).toBeInTheDocument();
  });

  it("lists holdings with no filing data, each with the engine's reason", async () => {
    await openTab({ [ALL]: PORTFOLIO_ALL });
    const list = within(screen.getByRole("list", { name: "Holdings with no filing data" }));
    expect(list.getByRole("link", { name: "QQQ" })).toHaveAttribute("href", "/stock/QQQ");
    expect(await list.findByText(COMPANY_NONE.data_notice)).toBeInTheDocument();
  });

  it("says which holdings have no price, so no weight", async () => {
    await openTab({ [ALL]: PORTFOLIO_ALL });
    expect(screen.getByText("No price in the market data, so no weight:")).toBeInTheDocument();
  });

  it("counts and labels holdings whose filing data is old", async () => {
    await openTab({ [ASHA]: PORTFOLIO_STALE }, "/portfolio?account=2");
    expect(await screen.findByText("3 of 4")).toBeInTheDocument();
    expect(screen.getAllByText("Old data")).toHaveLength(3);
  });

  it("shows the engine's own sentence when it cannot answer", async () => {
    const sentence = "Market data is not connected yet. Open Settings, then Market data.";
    engine({ [ALL]: refuses("INDEX_NOT_READY", sentence, 409) });
    renderAt(<Portfolio />);
    fireEvent.click(await screen.findByRole("tab", { name: "Fundamentals" }));
    expect(await screen.findByText(sentence)).toBeInTheDocument();
  });

  it("moves between the tabs with the keyboard", async () => {
    engine({ [ALL]: PORTFOLIO_ALL });
    renderAt(<Portfolio />);
    const first = await screen.findByRole("tab", { name: "Holdings" });
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(await screen.findByText(PORTFOLIO_ALL.statement)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Fundamentals" })).toHaveFocus();
  });
});

const ANSWERS = [
  ["every account", ALL, PORTFOLIO_ALL],
  ["one account, old data", ASHA, PORTFOLIO_STALE],
] as const;

describe("what the tab never says or colours", () => {
  test.each(ANSWERS)("%s: no advice words", async (_name, key, answer) => {
    const path = key === ALL ? "/portfolio" : "/portfolio?account=2";
    await openTab({ [key]: answer }, path);
    expect(screen.getByRole("tabpanel").textContent).not.toMatch(ADVICE);
  });

  test.each(ANSWERS)("%s: nothing coloured as good or bad", async (_name, key, answer) => {
    const path = key === ALL ? "/portfolio" : "/portfolio?account=2";
    await openTab({ [key]: answer }, path);
    expect(screen.getByRole("tabpanel").innerHTML).not.toMatch(GOOD_BAD_COLOURS);
  });
});

describe("an account with nothing in it", () => {
  it("has no tabs to show, because the Portfolio says so instead", async () => {
    engine({ "GET /api/v2/portfolio/fundamentals?account=3": PORTFOLIO_EMPTY });
    renderAt(<Portfolio />, "/portfolio?account=3");
    expect(await screen.findByText("No holdings in this account yet. Add your first one.")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Fundamentals" })).toBeNull();
  });
});
