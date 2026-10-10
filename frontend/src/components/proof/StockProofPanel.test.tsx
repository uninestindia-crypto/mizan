import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../lib/api";
import { callsTo, deferred } from "../agents/testHarness";
import { renderPage } from "../mode/modeKit";
import { proofEngine, proofMissing, PROOF_URL } from "./proofKit";
import { rawProof, type Scenario } from "./proofFixtures";
import { StockProofPanel } from "./StockProofPanel";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const open = async (scenario: Scenario) => {
  proofEngine(true, scenario);
  const view = renderPage(<StockProofPanel symbol="TCS" />);
  await screen.findByRole("group", { name: "Verdict" });
  return view;
};
const heading = (name: string | RegExp) => screen.getByRole("heading", { name });
const section = (name: string | RegExp) => within(heading(name).closest("section") as HTMLElement);

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("a compliant stock", () => {
  it("opens with the verdict, the reason and the data it rests on, in that order", async () => {
    await open("compliant");
    const verdict = within(screen.getByRole("group", { name: "Verdict" }));
    expect(verdict.getByText("Compliant")).toBeInTheDocument();
    expect(verdict.getAllByText(/Screened from the company's own filing, 30 Sep/)).toHaveLength(2);
    expect(verdict.getByText(/passes/i)).toBeInTheDocument();
    expect(verdict.getByText(/Read by QuantOS from the company's own results filed on NSE/)).toBeInTheDocument();
  });

  it("answers in the order a person reads, ending with what would change it and what it leaves out", async () => {
    await open("compliant");
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names).toEqual([
      "Business activity",
      "The four tests",
      "Where this comes from",
      "What would change this",
      "What this does not cover",
    ]);
  });

  it("passes the business test and says what it was decided on", async () => {
    await open("compliant");
    const business = section("Business activity");
    expect(business.getByText("Passed")).toBeInTheDocument();
    expect(business.getByText("industry group only")).toBeInTheDocument();
    expect(business.getByText("Information Technology")).toBeInTheDocument();
    expect(business.getByText("The filing lists no business segments.")).toBeInTheDocument();
  });

  it("shows four tests for each standard, each with its figure, its limit and its result in words", async () => {
    await open("compliant");
    const aaoifi = within(screen.getByRole("region", { name: "AAOIFI tests" }) ?? document.body);
    expect(aaoifi.getAllByRole("heading", { level: 5 })).toHaveLength(4);
    expect(aaoifi.getByText("Debt compared with market value")).toBeInTheDocument();
    expect(aaoifi.getAllByText("Pass")).toHaveLength(4);
    expect(aaoifi.getAllByText("Limit")).toHaveLength(4);
    const tasis = within(screen.getByRole("region", { name: "TASIS tests" }));
    expect(tasis.getByText("Receivables compared with total assets")).toBeInTheDocument();
    expect(tasis.getAllByText("Pass")).toHaveLength(4);
  });

  it("draws a bar for each test, with the limit written in its name", async () => {
    await open("compliant");
    const bars = screen.getAllByRole("img");
    expect(bars).toHaveLength(8);
    expect(bars[0]).toHaveAccessibleName(/against a limit of 33%/);
  });

  it("says where the figures come from, with the filing's fingerprint and its own checks", async () => {
    await open("compliant");
    const source = section("Where this comes from");
    expect(source.getByText("Six months ended 30 Sep 2024")).toBeInTheDocument();
    expect(source.getByText(/Consolidated, not audited/)).toBeInTheDocument();
    expect(source.getByText("abababababab…")).toBeInTheDocument();
    expect(source.getByText("The filing adds up against itself.")).toBeInTheDocument();
    expect(source.getByText(/Passed:/)).toBeInTheDocument();
  });

  it("always shows what would change it and what it does not cover, in full, and says it is not a fatwa", async () => {
    await open("compliant");
    const raw = rawProof("compliant");
    const notCovered = section("What this does not cover");
    const lines = raw.not_covered as string[];
    expect(lines.length).toBeGreaterThan(3);
    expect(lines.filter((line) => notCovered.queryByText(line) === null)).toEqual([]);
    expect(notCovered.getByText("This is a screening aid, not a fatwa.")).toBeInTheDocument();
    expect(screen.getByText(/No scholar has reviewed these rules/)).toBeInTheDocument();
  });

  it("offers no screening button, because it already rests on a filing", async () => {
    await open("compliant");
    expect(screen.queryByRole("button", { name: "Screen this stock now" })).toBeNull();
  });

  it.each(["certified", "approved", "guaranteed", "halal"])("never says %s", async (word) => {
    await open("compliant");
    expect(document.body.textContent?.toLowerCase()).not.toContain(word);
  });

  it.each(["XBRL", "API", "JSON", "endpoint", "backend", "terminal", "command"])(
    "never uses the developer's word %s",
    async (word) => {
      await open("split");
      screen.getAllByRole("button", { name: /Show the figures/ }).forEach((button) => fireEvent.click(button));
      expect(document.body.textContent).not.toMatch(new RegExp(`\\b${word}\\b`, "i"));
    },
  );
});

describe("a stock that fails the business test", () => {
  it("says which rule, which word, where it was found, and lists the segments as plain text", async () => {
    await open("sector_segment");
    const verdict = within(screen.getByRole("group", { name: "Verdict" }));
    expect(verdict.getByText("Not compliant")).toBeInTheDocument();
    const business = section("Business activity");
    expect(business.getByText("Failed")).toBeInTheDocument();
    expect(business.getByText(/Rule: Tobacco\./)).toBeInTheDocument();
    expect(business.getByText(/matched the word “cigarette” in a business segment in its filing/)).toBeInTheDocument();
    expect(business.getByText("the filing's segments")).toBeInTheDocument();
    expect(business.getByText("Cigarettes")).toBeInTheDocument();
    expect(business.getByText("Foods")).toBeInTheDocument();
    expect(business.queryByRole("link")).toBeNull();
  });

  it("shows text from outside the app as text, never as markup", async () => {
    const raw = rawProof("sector_segment");
    const sector = raw.sector as Record<string, unknown>;
    const segments = ['<img src=x onerror="alert(1)">Cigarettes', "<a href='https://evil.example'>Foods</a>"];
    proofEngine(true, { ...raw, sector: { ...sector, segments } });
    renderPage(<StockProofPanel symbol="TCS" />);
    await screen.findByRole("group", { name: "Verdict" });
    const business = section("Business activity");
    expect(business.queryByRole("img")).toBeNull();
    expect(business.queryByRole("link")).toBeNull();
    expect(business.getByText('img src=x onerror="alert(1)" Cigarettes')).toBeInTheDocument();
  });

  it("says when the word was found in the company's name", async () => {
    await open("sector_name");
    expect(section("Business activity").getByText(/in the company's name\./)).toBeInTheDocument();
  });
});

describe("a stock that fails on its figures", () => {
  it("says not compliant, names the failing tests, and still passes its business", async () => {
    await open("ratio_fail");
    const verdict = within(screen.getByRole("group", { name: "Verdict" }));
    expect(verdict.getByText("Not compliant")).toBeInTheDocument();
    expect(verdict.getByText(/debt/i)).toBeInTheDocument();
    expect(section("Business activity").getByText("Passed")).toBeInTheDocument();
    const aaoifi = within(screen.getByRole("region", { name: "AAOIFI tests" }));
    expect(aaoifi.getAllByText("Fail")).toHaveLength(3);
    expect(aaoifi.getAllByText(/over the 33% limit/)).toHaveLength(3);
  });
});

describe("a stock where the two standards disagree", () => {
  it("is questionable, says why, and shows both readings of a figure the filing does not break down", async () => {
    await open("split");
    expect(within(screen.getByRole("group", { name: "Verdict" })).getByText("Questionable")).toBeInTheDocument();
    expect(screen.getByText(/The two standards disagree\./)).toBeInTheDocument();
    const tasis = within(screen.getByRole("region", { name: "TASIS tests" }));
    const cash = within(tasis.getByText("Cash and securities compared with total assets").closest("li") as HTMLElement);
    expect(cash.getByText("Lower reading")).toBeInTheDocument();
    expect(cash.getByText("Upper reading")).toBeInTheDocument();
    expect(cash.getByText("10.4%")).toBeInTheDocument();
    expect(cash.getByText("32.8%")).toBeInTheDocument();
    expect(cash.getByText("Borderline")).toBeInTheDocument();
    expect(cash.getByText(/so QuantOS shows a lower and an upper reading/)).toBeInTheDocument();
  });

  it("says in the contract's words that it cannot say which side of the limit the company is on", async () => {
    await open("depends");
    const tasis = within(screen.getByRole("region", { name: "TASIS tests" }));
    const cash = within(tasis.getByText("Cash and securities compared with total assets").closest("li") as HTMLElement);
    expect(cash.getByText("Depends")).toBeInTheDocument();
    expect(cash.getByText("10.4%")).toBeInTheDocument();
    expect(cash.getByText("54.0%")).toBeInTheDocument();
    expect(cash.getAllByText(/cannot say which side of the limit/)).toHaveLength(1);
  });
});

describe("a stock whose business could not be confirmed", () => {
  it("says so in its own words, caps the verdict at questionable, and says what was checked", async () => {
    await open("not_confirmed");
    expect(within(screen.getByRole("group", { name: "Verdict" })).getByText("Questionable")).toBeInTheDocument();
    const business = section("Business activity");
    expect(business.getByText("Business not confirmed")).toBeInTheDocument();
    expect(business.getByText(/QuantOS cannot tell what this company sells/)).toBeInTheDocument();
    expect(business.queryByText("Passed")).toBeNull();
    expect(business.queryByText("Failed")).toBeNull();
  });

  it("goes by the status, never by the older yes/no", async () => {
    const raw = rawProof("not_confirmed");
    proofEngine(true, { ...raw, sector: { ...(raw.sector as object), compliant: true } });
    renderPage(<StockProofPanel symbol="TCS" />);
    await screen.findByRole("group", { name: "Verdict" });
    expect(section("Business activity").getByText("Business not confirmed")).toBeInTheDocument();
  });
});

describe("a stock whose market value could not be worked out", () => {
  it("says it needs price history and draws no bar for those tests", async () => {
    await open("no_price");
    const aaoifi = within(screen.getByRole("region", { name: "AAOIFI tests" }));
    expect(aaoifi.getAllByText("Not computed").length).toBeGreaterThanOrEqual(4);
    expect(aaoifi.getAllByText(/Needs price history/)).toHaveLength(3);
    expect(aaoifi.getAllByRole("img")).toHaveLength(1);
  });
});

describe("the data behind a result", () => {
  it("says an old filing is old", async () => {
    await open("stale");
    const verdict = within(screen.getByRole("group", { name: "Verdict" }));
    expect(verdict.getAllByText(/Based on an old filing/).length).toBeGreaterThan(0);
    expect(verdict.getByText(/more than 18 months old/)).toBeInTheDocument();
  });

  it("shows a hand-entered sample as a sample: no filing box, no field names, a way to read the filing", async () => {
    await open("sample");
    expect(screen.getAllByText(/Illustrative sample, not from a filing/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Where this comes from" })).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: /Show the figures/ })[0]!);
    expect(screen.getAllByText("Hand-entered sample figure. No filing backs it.").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Source field/)).toBeNull();
    expect(screen.getByRole("button", { name: "Screen this stock now" })).toBeInTheDocument();
  });

  it("says when a filing disagrees with the older sample, and what differs", async () => {
    await open("sample_differs");
    expect(screen.getByText("Different from QuantOS's older sample")).toBeInTheDocument();
    expect(screen.getByText(/7,970/)).toBeInTheDocument();
  });
});

describe("a stock that has not been screened", () => {
  it("says what is missing, shows no tests and no pass, and offers one button", async () => {
    await open("not_screened");
    const verdict = within(screen.getByRole("group", { name: "Verdict" }));
    expect(verdict.getByText("Not screened")).toBeInTheDocument();
    expect(verdict.getByText(/is not screened yet/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "The four tests" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Business activity" })).toBeNull();
    expect(screen.queryByText("Passed")).toBeNull();
    expect(screen.getAllByRole("button", { name: "Screen this stock now" })).toHaveLength(1);
    expect(screen.getByText("This is a screening aid, not a fatwa.")).toBeInTheDocument();
  });
});

describe("the figures behind a test", () => {
  it("lists every input with its label, its crore value and its source field, and rupees on request", async () => {
    await open("split");
    const tasis = within(screen.getByRole("region", { name: "TASIS tests" }));
    const cash = within(tasis.getByText("Cash and securities compared with total assets").closest("li") as HTMLElement);
    fireEvent.click(cash.getByRole("button", { name: /Show the figures/ }));
    expect(cash.getByText("Cash and cash equivalents")).toBeInTheDocument();
    expect(cash.getByText("₹8,155 crore")).toBeInTheDocument();
    expect(cash.getByText("CashAndCashEquivalents")).toBeInTheDocument();
    expect(cash.getAllByText(/Source field:/)).toHaveLength(5);
    expect(cash.getAllByText(/Counted in the upper reading only/)).toHaveLength(2);
    expect(cash.getByText(/₹16,733 crore ÷ ₹1,61,124 crore = 10.4%/)).toBeInTheDocument();
    fireEvent.click(cash.getByRole("button", { name: "Show amounts in rupees" }));
    expect(cash.getByText("₹81,55,00,00,000")).toBeInTheDocument();
  });

  it("is closed until asked", async () => {
    await open("split");
    const buttons = screen.getAllByRole("button", { name: /Show the figures/ });
    expect(buttons[0]).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/Source field:/)).toBeNull();
  });
});

describe("the link to the filing", () => {
  it("opens on NSE in a new tab and never hands the page to it", async () => {
    await open("compliant");
    const source = section("Where this comes from");
    const link = source.getByRole("link", { name: /Open the filing on NSE/ });
    expect(link).toHaveAttribute("href", "https://nsearchives.nseindia.com/archives/financial_results/example.html");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    const file = source.getByRole("link", { name: /Download the filing file/ });
    expect(file).toHaveAttribute("href", expect.stringContaining("nsearchives.nseindia.com/corporate/xbrl/"));
  });

  const CASES_1 = [
    "https://www.nseindia.com.evil.example/filing",
    "http://www.nseindia.com/filing",
    "javascript:alert(1)",
    "https://evil.example/?https://www.nseindia.com/",
  ] as const;

  it.each(CASES_1)("shows %s as text, not as a link", async (hostile) => {
    const raw = rawProof("compliant");
    proofEngine(true, { ...raw, filing: { ...(raw.filing as object), detail_url: hostile } });
    renderPage(<StockProofPanel symbol="TCS" />);
    await screen.findByRole("group", { name: "Verdict" });
    const source = section("Where this comes from");
    expect(source.queryByRole("link", { name: /Open the filing on NSE/ })).toBeNull();
    expect(source.getByText(hostile)).toBeInTheDocument();
    expect(document.querySelector(`a[href="${hostile}"]`)).toBeNull();
  });

  it("copies the whole fingerprint", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await open("compliant");
    fireEvent.click(screen.getByRole("button", { name: "Copy the full fingerprint" }));
    await screen.findByText("Copied");
    expect(writeText).toHaveBeenCalledWith("ab".repeat(32));
  });

  it("says so, and shows the whole fingerprint, when the browser will not copy", async () => {
    const refuses = { writeText: vi.fn().mockRejectedValue(new Error("no")) };
    Object.defineProperty(navigator, "clipboard", { value: refuses, configurable: true });
    await open("compliant");
    fireEvent.click(screen.getByRole("button", { name: "Copy the full fingerprint" }));
    expect(await screen.findByText(/Your browser would not allow copying/)).toHaveTextContent("ab".repeat(32));
  });
});

describe("when the proof cannot be had", () => {
  it("says there is no screening yet for a stock the engine does not know, and offers the next click", async () => {
    proofMissing(true);
    renderPage(<StockProofPanel symbol="TCS" />);
    expect(await screen.findByText("No Shariah screening is available for this stock yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Screen this stock now" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the Shariah screener" })).toHaveAttribute("href", "/shariah");
  });

  const CASES_2 = [
    [new ApiError("ENGINE_OFFLINE", "offline", 0), "QuantOS could not reach its engine"],
    [new ApiError("HTTP_500", "broken", 500), "The Shariah screening could not be loaded"],
  ] as const;

  it.each(CASES_2)("says plainly what went wrong, and tries again on request", async (error, words) => {
    proofEngine(true, "compliant", {
      [PROOF_URL]: () => {
        throw error;
      },
    });
    renderPage(<StockProofPanel symbol="TCS" />);
    expect(await screen.findByText(words)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(callsTo("GET", "/api/v2/shariah/stocks/TCS/proof").length).toBeGreaterThan(1));
  });

  it("says it is loading while it waits", async () => {
    const slow = deferred<unknown>();
    proofEngine(true, "compliant", { [PROOF_URL]: () => slow.promise });
    renderPage(<StockProofPanel symbol="TCS" />);
    expect(await screen.findByText("Loading the Shariah screening...")).toBeInTheDocument();
    slow.resolve(rawProof("compliant"));
    await screen.findByRole("group", { name: "Verdict" });
  });
});

describe("in Institutional mode", () => {
  it("is one folded line that loads nothing until opened", async () => {
    proofEngine(false, "compliant");
    renderPage(<StockProofPanel symbol="TCS" />);
    const fold = await screen.findByRole("button", { name: "Shariah screening" });
    expect(fold).toHaveAttribute("aria-expanded", "false");
    expect(callsTo("GET", "/api/v2/shariah/stocks/TCS/proof")).toHaveLength(0);
    fireEvent.click(fold);
    expect(await screen.findByRole("group", { name: "Verdict" })).toBeInTheDocument();
    expect(fold).toHaveAttribute("aria-expanded", "true");
  });

  it("opens itself when a Shariah badge sent the person here", async () => {
    proofEngine(false, "compliant");
    renderPage(<StockProofPanel symbol="TCS" />, "/stock/TCS#shariah-proof");
    expect(await screen.findByRole("group", { name: "Verdict" })).toBeInTheDocument();
  });
});

describe("in Shariah mode", () => {
  it("is open with its own heading, and asks as soon as it shows", async () => {
    await open("compliant");
    expect(screen.getByRole("heading", { level: 2, name: "Shariah screening" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Shariah screening" })).toBeNull();
  });
});
