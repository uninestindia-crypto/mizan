import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";
import { api } from "../../lib/api";
import { date } from "../../lib/format";
import { renderPage } from "../mode/modeKit";
import { ADVICE, GOOD_BAD_COLOURS, engine, refuses, url } from "./fundamentalsKit";
import {
  COMPANY_BANK,
  COMPANY_EXCLUDED,
  COMPANY_FRESH,
  COMPANY_NONE,
  COMPANY_STALE,
  COMPANY_TCS,
} from "./fundamentalsFixtures";
import { FundamentalsSection } from "./FundamentalsSection";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

function show(answer: unknown) {
  engine({ [url("AAA")]: answer });
  return renderPage(<FundamentalsSection symbol="AAA" />);
}

async function metricCard(label: string): Promise<HTMLElement> {
  return (await screen.findByRole("heading", { level: 4, name: label })).closest("li")!;
}

const FACTS = COMPANY_FRESH.scorecard.facts.map((f) => [f.key, f.sentence]);
const METRICS = Object.values(COMPANY_FRESH.metrics).map((m) => [m.key, m.label]);

describe("a company with fresh filings", () => {
  it("has its heading, and the engine's statement as sent", async () => {
    show(COMPANY_FRESH);
    expect(await screen.findByRole("heading", { name: "Results from the company's own filings" })).toBeInTheDocument();
    expect(await screen.findByText(COMPANY_FRESH.statement)).toBeInTheDocument();
    expect(await screen.findByText(COMPANY_FRESH.data_notice)).toBeInTheDocument();
  });

  it("puts the engine's header line above the facts, with how many of each kind", async () => {
    show(COMPANY_FRESH);
    expect(await screen.findByText(COMPANY_FRESH.scorecard.header)).toBeInTheDocument();
    expect(screen.getByText("8 inside the rule of thumb, 6 facts")).toBeInTheDocument();
  });

  test.each(FACTS)("shows the fact %s as sent", async (_key, sentence) => {
    show(COMPANY_FRESH);
    expect(await screen.findByText(String(sentence))).toBeInTheDocument();
  });

  test.each(METRICS)("shows the figure %s with its plain label", async (_key, label) => {
    show(COMPANY_FRESH);
    expect(await screen.findByRole("heading", { level: 4, name: String(label) })).toBeInTheDocument();
  });

  it("says in words whether a fact is inside its rule of thumb, with the rule", async () => {
    show(COMPANY_FRESH);
    const fact = (await screen.findByText(/^Profit in 8 of the last 8 quarters\./)).closest("li")!;
    expect(within(fact).getByText("Inside the rule of thumb")).toBeInTheDocument();
    expect(within(fact).getByText("Rule of thumb: profit in at least 6 of the last 8 quarters.")).toBeInTheDocument();
  });

  it("shows each figure's formula in words and the numbers it was worked out from, with the filing link", async () => {
    show(COMPANY_FRESH);
    const card = await metricCard("Profit over the last four quarters");
    const metric = COMPANY_FRESH.metrics.ttm_net_profit!;
    expect(within(card).getByText(metric.formula)).toBeInTheDocument();
    const input = metric.inputs[0]!;
    expect(within(card).getAllByText(input.tag)[0]).toBeInTheDocument();
    const link = within(card).getAllByRole("link", { name: /Open the filing/ })[0]!;
    expect(link).toHaveAttribute("href", input.filing_url);
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the price the price ratios used, with its date", async () => {
    show(COMPANY_FRESH);
    const card = await metricCard("Price compared with earnings (P/E)");
    expect(within(card).getByText("78.43 times")).toBeInTheDocument();
    expect(within(card).getAllByText(/Close of 28 Feb 2025/)).not.toHaveLength(0);
    expect(within(card).getByText(/from QuantOS's own end-of-day prices/)).toBeInTheDocument();
  });

  it("says what the figures do not cover", async () => {
    show(COMPANY_FRESH);
    expect(await screen.findByText(COMPANY_FRESH.not_covered[0]!)).toBeInTheDocument();
  });
});

describe("old data", () => {
  it("is labelled as old, with the engine's sentence", async () => {
    show(COMPANY_STALE);
    const notice = (await screen.findByText("Old data", { selector: "div" })).closest("[role=status]")!;
    expect(within(notice as HTMLElement).getByText(COMPANY_STALE.data_notice)).toBeInTheDocument();
  });

  it("still shows the figures, and the data-age fact says it is outside its rule", async () => {
    show(COMPANY_STALE);
    const fact = (await screen.findByText(/more than 18 months ago/, { selector: "span" })).closest("li")!;
    expect(within(fact).getByText("Outside the rule of thumb")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 4, name: "Profit over the last four quarters" })).toBeInTheDocument();
  });
});

describe("a company with nothing held, or a layout QuantOS does not read", () => {
  it("says why there are no figures, as sent, and offers to get the results", async () => {
    show(COMPANY_NONE);
    expect(await screen.findByText(COMPANY_NONE.data_notice)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get the latest results" })).toBeInTheDocument();
    expect(screen.queryByText("Facts against rules of thumb")).toBeNull();
  });

  it("says a bank's layout is not read, in the engine's words", async () => {
    show(COMPANY_BANK);
    expect(await screen.findAllByText(COMPANY_BANK.data_notice)).not.toHaveLength(0);
    expect(screen.queryByText("Facts against rules of thumb")).toBeNull();
  });
});

describe("a quarter that failed its own check", () => {
  it("is shown with its reason and as left out of every figure", async () => {
    show(COMPANY_EXCLUDED);
    const left = (await screen.findByRole("heading", { name: "Quarters left out" })).closest("section")!;
    expect(within(left).getByText(`Quarter ended ${date("2023-09-30")}:`, { exact: false })).toBeInTheDocument();
    expect(within(left).getByText(/Failed its own check\./)).toBeInTheDocument();
    expect(within(left).getByText(/Total income less expenses did not equal profit before tax\./)).toBeInTheDocument();
    expect(within(left).getByText(/none of the figures above uses them/)).toBeInTheDocument();
  });

  it("does not also list that quarter as one with no filing", async () => {
    show(COMPANY_EXCLUDED);
    await screen.findByRole("heading", { name: "Quarters left out" });
    expect(screen.queryByText(/No filing is held for/)).toBeNull();
  });

  it("says a figure it cannot work out is not available, with the reason", async () => {
    show(COMPANY_EXCLUDED);
    const unavailable = COMPANY_EXCLUDED.metrics.profit_growth_ttm!;
    const card = (await screen.findByRole("heading", { level: 4, name: unavailable.label })).closest("li")!;
    expect(within(card).getByText("Not available.")).toBeInTheDocument();
    expect(within(card).getByText(unavailable.reason!, { exact: false })).toBeInTheDocument();
  });
});

describe("real filings", () => {
  it("shows what two real quarters allow and says what is not available", async () => {
    show(COMPANY_TCS);
    expect(await screen.findByText(COMPANY_TCS.scorecard.header)).toBeInTheDocument();
    expect(screen.getAllByText("Not available.").length).toBeGreaterThan(0);
    const link = screen.getAllByRole("link", { name: /Open the filing/ })[0];
    expect(link).toHaveAttribute("href", expect.stringContaining("nsearchives.nseindia.com"));
  });
});

describe("when the engine cannot answer", () => {
  it("shows its plain sentence", async () => {
    show(refuses("BAD_REQUEST", "Use letters and numbers only for the stock symbol, for example TCS.", 422));
    expect(await screen.findByText(/Use letters and numbers only for the stock symbol/)).toBeInTheDocument();
  });
});

const ALL = [
  ["fresh", COMPANY_FRESH],
  ["old", COMPANY_STALE],
  ["none", COMPANY_NONE],
  ["failed quarter", COMPANY_EXCLUDED],
  ["real filings", COMPANY_TCS],
  ["bank", COMPANY_BANK],
] as const;

describe("what the section never says or colours", () => {
  test.each(ALL)("%s: no advice words", async (_name, answer) => {
    const view = show(answer);
    await screen.findByRole("heading", { name: "Results from the company's own filings" });
    await screen.findByText(answer.statement);
    expect(view.container.textContent).not.toMatch(ADVICE);
  });

  test.each(ALL)("%s: nothing coloured as good or bad", async (_name, answer) => {
    const view = show(answer);
    await screen.findByText(answer.statement);
    expect(view.container.innerHTML).not.toMatch(GOOD_BAD_COLOURS);
  });
});
