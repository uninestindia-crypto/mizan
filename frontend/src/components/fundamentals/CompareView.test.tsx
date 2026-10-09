import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Fundamentals from "../../pages/Fundamentals";
import { api } from "../../lib/api";
import { callsTo } from "../agents/testHarness";
import { engine as portfolioEngine, renderAt } from "../portfolio/portfolioKit";
import { ADVICE, GOOD_BAD_COLOURS } from "./fundamentalsKit";
import { figureText } from "./format";
import { COMPARE_GAPS, COMPARE_MIXED, COMPARE_OK, COMPARE_ONE_BASIS } from "./fundamentalsFixtures";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const COMPARE = "/api/v2/fundamentals/compare?symbols=";
const SAID = "Facts from each company's own filings, side by side. This is not a ranking and not advice.";
const PHONE = { matches: true, addEventListener: () => undefined, removeEventListener: () => undefined };
const FOUND = [{ symbol: "AAA", name: "AAA Limited", is_etf: false }];

beforeEach(() => {
  vi.mocked(api).mockReset();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function show(symbols: string, answer?: unknown) {
  portfolioEngine(answer ? { [`GET ${COMPARE}${symbols}`]: answer, "GET /api/v2/market/search?q=aaa": FOUND } : {});
  return renderAt(<Fundamentals />, `/fundamentals?view=compare${symbols ? `&symbols=${symbols}` : ""}`);
}

const table = () => within(screen.getByRole("table", { name: "Companies side by side" }));
function where() {
  return screen.getByTestId("where").textContent;
}

describe("the compare view", () => {
  it("asks for two to four companies and asks the engine nothing yet", () => {
    show("");
    expect(screen.getByRole("radio", { name: "Compare side by side" })).toBeChecked();
    expect(screen.getByText(/Pick 2 to 4 companies\./)).toBeInTheDocument();
    expect(callsTo("GET", `${COMPARE}`)).toHaveLength(0);
  });

  it("waits for a second company before asking", () => {
    show("AAA");
    expect(screen.getByRole("list", { name: "Companies to compare" })).toHaveTextContent("AAA");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("puts the companies side by side with the engine's statement as sent", async () => {
    show("AAA,CCC", COMPARE_OK);
    expect(await screen.findByText(SAID)).toBeInTheDocument();
    expect(screen.getByText("Compared on a consolidated basis.")).toBeInTheDocument();
    const heads = table().getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads[1]).toContain("AAA");
    expect(heads[2]).toContain("CCC");
  });

  it("has a row for every figure the engine compared, with its plain label", async () => {
    show("AAA,CCC", COMPARE_OK);
    await screen.findByText(SAID);
    const labels = table().getAllByRole("rowheader").map((h) => h.textContent);
    expect(labels).toEqual(COMPARE_OK.rows.map((r) => r.label));
  });

  it("shows each company's own value", async () => {
    show("AAA,CCC", COMPARE_OK);
    await screen.findByText(SAID);
    const row = table().getByRole("rowheader", { name: "Price compared with earnings (P/E)" }).closest("tr")!;
    const pe = COMPARE_OK.rows.find((r) => r.key === "pe")!.values;
    expect(within(row).getAllByRole("cell").map((c) => c.textContent)).toEqual([
      expect.stringContaining(figureText({ unit: "times", value: pe.AAA!.value })),
      expect.stringContaining(figureText({ unit: "times", value: pe.CCC!.value })),
    ]);
  });

  it("says a figure is not available, with the reason, instead of leaving a gap", async () => {
    show("AAA,DDD", COMPARE_GAPS);
    await screen.findByText(SAID);
    const row = table().getByRole("rowheader", { name: "Sales over the last four quarters" }).closest("tr")!;
    expect(within(row).getByText("Not available.")).toBeInTheDocument();
    expect(within(row).getByText(/This needs four quarters in a row/, { exact: false })).toBeInTheDocument();
  });

  it("leaves out a company on a different basis, with the engine's reason, and says why in a note", async () => {
    show("AAA,CCC,FFF", COMPARE_MIXED);
    await screen.findByText(SAID);
    const left = within(screen.getByRole("list", { name: "Companies not in the lines" }));
    expect(left.getByText("FFF is not in the lines below.")).toBeInTheDocument();
    expect(left.getByText(COMPARE_MIXED.companies[2]!.reason!, { exact: false })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Notes" })).getByText(COMPARE_MIXED.notes[0]!)).toBeInTheDocument();
    expect(table().queryByText("FFF")).toBeNull();
  });

  it("shows no table when the companies cannot be put on one basis, and says so", async () => {
    show("AAA,FFF", COMPARE_ONE_BASIS);
    await screen.findByText(SAID);
    expect(screen.getByText(COMPARE_ONE_BASIS.notes[0]!)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("choosing the companies", () => {
  it("adds a company from the search and puts it in the address", async () => {
    show("", COMPARE_OK);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "aaa" } });
    fireEvent.mouseDown(await screen.findByRole("option", { name: /AAA/ }));
    expect(where()).toBe("/fundamentals?view=compare&symbols=AAA");
  });

  it("removes a company", async () => {
    show("AAA,CCC", COMPARE_OK);
    fireEvent.click(await screen.findByRole("button", { name: "Remove CCC" }));
    expect(where()).toBe("/fundamentals?view=compare&symbols=AAA");
  });

  it("stops at four companies and says that is the most", async () => {
    show("AAA,BBB,CCC,DDD", COMPARE_OK);
    expect(await screen.findByText("That is the most that can be compared at once.")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});

describe("on a phone", () => {
  it("shows each figure with the companies one under another, and no wide table", async () => {
    vi.stubGlobal("matchMedia", () => PHONE);
    show("AAA,CCC", COMPARE_OK);
    await screen.findByText(SAID);
    expect(screen.queryByRole("table")).toBeNull();
    const pe = within(screen.getByRole("region", { name: "Price compared with earnings (P/E)" }));
    expect(pe.getByText("AAA")).toBeInTheDocument();
    expect(pe.getByText("CCC")).toBeInTheDocument();
  });
});

describe("what the compare view never says or colours", () => {
  it("uses no advice words and no good-or-bad colours", async () => {
    show("AAA,CCC,FFF", COMPARE_MIXED);
    await screen.findByText(SAID);
    const text = (document.body.textContent ?? "").replace(SAID, "");
    expect(text).not.toMatch(ADVICE);
    expect(screen.getByRole("table").innerHTML).not.toMatch(GOOD_BAD_COLOURS);
  });
});
