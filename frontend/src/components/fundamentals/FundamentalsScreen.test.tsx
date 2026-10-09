import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";
import Fundamentals from "../../pages/Fundamentals";
import { api } from "../../lib/api";
import { int } from "../../lib/format";
import { callsTo } from "../agents/testHarness";
import { engine as portfolioEngine, renderAt } from "../portfolio/portfolioKit";
import { ADVICE, GOOD_BAD_COLOURS, refuses } from "./fundamentalsKit";
import { SCREEN_ALL, SCREEN_ROE, SCREEN_STALE } from "./fundamentalsFixtures";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const SCREEN = "GET /api/v2/fundamentals/screen";
const ROE_LABEL = "Profit as a share of the owners' money (approximate), at least";
const DEBT_LABEL = "Borrowings compared with the owners' money, at most";
const SAID = "These are filters you chose, not a recommendation.";

beforeEach(() => {
  vi.mocked(api).mockReset();
  localStorage.clear();
});
afterEach(cleanup);

function show(answers: Record<string, unknown>, path = "/fundamentals") {
  portfolioEngine(answers);
  return renderAt(<Fundamentals />, path);
}

const choose = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const run = () => fireEvent.click(screen.getByRole("button", { name: "Show companies" }));
const symbolsListed = () =>
  within(screen.getByRole("list", { name: "Companies that meet your filters" }))
    .getAllByRole("link")
    .map((link) => link.textContent);

describe("the Fundamentals screen, before anything is chosen", () => {
  it("has a heading, says it shows facts and does not rank, and starts on the filters", () => {
    show({});
    expect(screen.getByRole("heading", { level: 1, name: "Fundamentals" })).toBeInTheDocument();
    expect(screen.getByText(/It does not rank companies or tell you what to do\./)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Filter companies" })).toBeChecked();
  });

  it("asks the engine nothing until the button is pressed", () => {
    show({});
    expect(callsTo("GET", "/api/v2/fundamentals/screen")).toHaveLength(0);
    expect(screen.queryByRole("list", { name: "Companies that meet your filters" })).toBeNull();
  });

  it("leaves every filter empty, and says an empty box leaves the filter out", () => {
    show({});
    expect(screen.getByLabelText(ROE_LABEL)).toHaveValue("");
    expect(screen.getByText(/Leave a box empty to leave that filter out/)).toBeInTheDocument();
  });
});

describe("choosing filters", () => {
  it("asks for only the filters that were filled in, with the sort and the order that were chosen", async () => {
    const path = "/api/v2/fundamentals/screen?min_roe_pct=12&sort=roe_pct&order=desc&limit=25";
    show({ [`GET ${path}`]: SCREEN_ROE });
    choose(ROE_LABEL, "12");
    choose("Sort by", "roe_pct");
    choose("Order", "desc");
    run();
    await screen.findByText(SAID);
    expect(callsTo("GET", path)).toHaveLength(1);
  });

  it("asks with the engine's own defaults when nothing was chosen", async () => {
    show({ [`${SCREEN}?sort=symbol&order=asc&limit=25`]: SCREEN_ALL });
    run();
    expect(await screen.findByText("No filters were chosen, so every company is listed.")).toBeInTheDocument();
  });

  it("keeps a letter out of a number box", () => {
    show({});
    choose(DEBT_LABEL, "1x.5");
    expect(screen.getByLabelText(DEBT_LABEL)).toHaveValue("1.5");
  });

  it("empties the boxes when the filters are cleared", () => {
    show({});
    choose(ROE_LABEL, "12");
    fireEvent.click(screen.getByRole("button", { name: "Clear the filters" }));
    expect(screen.getByLabelText(ROE_LABEL)).toHaveValue("");
  });

  it("offers each sort the engine understands, and both orders", () => {
    show({});
    expect(within(screen.getByLabelText("Sort by")).getAllByRole("option")).toHaveLength(10);
    expect(within(screen.getByLabelText("Order")).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Lowest first",
      "Highest first",
    ]);
  });
});

describe("the results", () => {
  async function ranRoe() {
    show({ [`${SCREEN}?min_roe_pct=12&sort=symbol&order=asc&limit=25`]: SCREEN_ROE });
    choose(ROE_LABEL, "12");
    run();
    await screen.findByText(SAID);
  }

  it("says in the engine's words that these are filters the person chose, not a recommendation", async () => {
    await ranRoe();
    expect(screen.getByText(SAID)).toBeInTheDocument();
  });

  it("counts what was considered, what was left out for missing data, and what the filters left out", async () => {
    await ranRoe();
    const counts = screen.getByText("Companies considered").closest("dl")!;
    expect(within(counts).getByText(int(SCREEN_ROE.considered))).toBeInTheDocument();
    const count = (label: string) => within(counts).getByText(label).nextSibling;
    expect(count("Left out for missing data")).toHaveTextContent(String(SCREEN_ROE.excluded_missing_data));
    expect(count("Left out by your filters")).toHaveTextContent(String(SCREEN_ROE.excluded_by_filters));
    expect(count("Match your filters")).toHaveTextContent(String(SCREEN_ROE.matched));
  });

  it("lists the filters that were applied in the engine's words, and how the list is sorted", async () => {
    await ranRoe();
    const applied = within(screen.getByRole("list", { name: "Filters you chose" }));
    expect(applied.getByText(SCREEN_ROE.filters_applied[0]!.plain)).toBeInTheDocument();
    const sorted = /Sorted by: Profit as a share of the owners' money \(approximate\)\. Order: highest first\./;
    expect(screen.getByText(sorted)).toBeInTheDocument();
  });

  it("lists the companies in the order the engine sent them, and does not reorder them", async () => {
    await ranRoe();
    expect(symbolsListed()).toEqual(SCREEN_ROE.results.map((r) => r.symbol));
  });

  it("shows each company's own figures, its latest quarter and its facts against rules of thumb", async () => {
    await ranRoe();
    const first = SCREEN_ROE.results[0]!;
    const card = screen.getByRole("link", { name: first.symbol }).closest("li")!;
    expect(within(card).getByText(/Latest quarter ended/)).toBeInTheDocument();
    expect(within(card).getByText(/inside the rule of thumb/)).toBeInTheDocument();
    expect(within(card).getAllByRole("definition")).toHaveLength(9);
  });

  it("says which date the filings and prices are from", async () => {
    await ranRoe();
    expect(screen.getByText(/Newest filing: quarter ended 31 Dec 2024/)).toBeInTheDocument();
    expect(screen.getByText(/Prices: 28 Feb 2025/)).toBeInTheDocument();
    expect(screen.getByText(/Filings gathered: 1 Feb 2025/)).toBeInTheDocument();
  });
});

describe("old data in the results", () => {
  async function ranOld() {
    show({ [`${SCREEN}?max_debt_to_equity=0.5&sort=pe&order=asc&limit=25`]: SCREEN_STALE });
    choose(DEBT_LABEL, "0.5");
    choose("Sort by", "pe");
    run();
    await screen.findByText(SAID);
  }

  it("counts the companies with old data and says so in words", async () => {
    await ranOld();
    const n = SCREEN_STALE.stale_in_results;
    expect(n).toBeGreaterThan(0);
    expect(screen.getByRole("status")).toHaveTextContent(`${n} compan`);
    expect(screen.getByRole("status")).toHaveTextContent("filing data that is old");
  });

  it("labels each of those companies as old", async () => {
    await ranOld();
    expect(screen.getAllByText("Old data").length).toBeGreaterThanOrEqual(SCREEN_STALE.stale_in_results);
  });
});

describe("when the engine refuses", () => {
  it("shows its plain sentence and keeps what was typed", async () => {
    const sentence = "Type a few letters of an industry group, for example bank.";
    show({ [`${SCREEN}?sector=b&sort=symbol&order=asc&limit=25`]: refuses("BAD_REQUEST", sentence, 422) });
    choose("Industry group contains", "b");
    run();
    expect((await screen.findAllByText(sentence)).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Industry group contains")).toHaveValue("b");
  });
});

describe("what the screen never says or colours", () => {
  const WITHOUT_STATEMENT = (text: string | null) => (text ?? "").replace(SAID, "");

  it("uses no advice words in the filter results", async () => {
    show({ [`${SCREEN}?min_roe_pct=12&sort=symbol&order=asc&limit=25`]: SCREEN_ROE });
    choose(ROE_LABEL, "12");
    run();
    await screen.findByText(SAID);
    expect(WITHOUT_STATEMENT(document.body.textContent)).not.toMatch(ADVICE);
  });

  test.each([["filter", SCREEN_ROE]])("colours nothing as good or bad (%s)", async (_name, answer) => {
    show({ [`${SCREEN}?min_roe_pct=12&sort=symbol&order=asc&limit=25`]: answer });
    choose(ROE_LABEL, "12");
    run();
    await screen.findByText(SAID);
    const list = screen.getByRole("list", { name: "Companies that meet your filters" });
    expect(list.innerHTML).not.toMatch(GOOD_BAD_COLOURS);
  });
});
