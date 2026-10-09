import { describe, expect, it } from "vitest";
import { bankAudit, fullAudit, olderAudit, ratio, standard } from "./shariahFixtures";
import { buildVerdictView, indiaTime } from "./verdictModel";

/** The nth item, or a loud failure: an index out of range is a broken test, not a quiet undefined. */
function nth<T>(items: readonly T[], index: number): T {
  const item = items[index];
  if (item === undefined) throw new Error(`No item at ${index}`);
  return item;
}

describe("indiaTime", () => {
  it("shows a UTC time as India time, with the date", () => {
    expect(indiaTime("2026-10-07T04:45:00+00:00")).toBe("7 Oct 2026, 10:15 am India time");
  });

  it("reads a time with no zone as UTC, as the engine writes it", () => {
    expect(indiaTime("2026-10-07T04:45:00")).toBe("7 Oct 2026, 10:15 am India time");
  });

  it("gives nothing for a missing or unreadable time", () => {
    expect(indiaTime(null)).toBeNull();
    expect(indiaTime("last Tuesday")).toBeNull();
  });
});

describe("buildVerdictView, ratios", () => {
  it("shows the formula in words, the figures, the limit and the headroom", () => {
    const view = buildVerdictView(fullAudit());
    const debt = nth(view.standards[0].ratios, 0);
    expect(debt.name).toBe("Debt");
    expect(debt.formula).toBe("Total Interest-Bearing Debt divided by 36-Month Rolling Average Market Cap");
    expect(debt.figures).toBe("₹7,970.00 Cr divided by ₹13,85,400.00 Cr = 0.58%");
    expect(debt.limit).toBe("under 33%");
    expect(debt.headroom).toBe("Headroom: 32.42 percentage points under the limit.");
    expect(debt.state).toBe("within");
  });

  it("says by how much a ratio is over its limit", () => {
    const view = buildVerdictView(bankAudit());
    const debt = nth(view.standards[0].ratios, 0);
    expect(debt.state).toBe("over");
    expect(debt.headroom).toBe("Over the limit by 55.20 percentage points.");
  });

  it("marks a ratio inside the warning band as close", () => {
    const close = ratio({ actual_pct: 32.4, is_warning: true });
    const questionable = standard("AAOIFI", { status: "QUESTIONABLE", debt_ratio: close });
    const view = buildVerdictView(fullAudit({ aaoifi_evaluation: questionable }));
    expect(nth(view.standards[0].ratios, 0).state).toBe("close");
  });

  it("never reads a ratio exactly at its limit as headroom", () => {
    const atLimit = ratio({ actual_pct: 33, is_compliant: false });
    const view = buildVerdictView(fullAudit({ aaoifi_evaluation: standard("AAOIFI", { debt_ratio: atLimit }) }));
    expect(nth(view.standards[0].ratios, 0).headroom).toBe("Exactly at the limit, which does not pass.");
  });
});

describe("buildVerdictView, one-line reasons", () => {
  it("says a failed business line fails the share whatever the figures are", () => {
    const view = buildVerdictView(bankAudit());
    expect(view.standards[0].reason).toBe("Fails the business-line test, whatever its figures.");
  });

  it("names the ratios over the limit when the business line passed", () => {
    const debt = ratio({ is_compliant: false, actual_pct: 40 });
    const cash = ratio({ is_compliant: false, actual_pct: 50 });
    const failing = standard("TASIS", { status: "NON_COMPLIANT", debt_ratio: debt, cash_ratio: cash });
    const view = buildVerdictView(fullAudit({ tasis_evaluation: failing }));
    expect(view.standards[1].reason).toBe("Over the limit: debt and cash and bank balances.");
  });

  it("names the ratio close to its limit for a questionable result", () => {
    const close = ratio({ actual_pct: 32.4, is_warning: true });
    const questionable = standard("AAOIFI", { status: "QUESTIONABLE", receivables_ratio: close });
    const view = buildVerdictView(fullAudit({ aaoifi_evaluation: questionable }));
    expect(view.standards[0].reason).toBe("Close to the limit: money owed to the company.");
  });

  it("says a passing result is within every limit", () => {
    expect(buildVerdictView(fullAudit()).standards[0].reason).toBe(
      "All four ratios are within their limits and the business line passed.",
    );
  });

  it("combines the two standards the way the list does", () => {
    expect(buildVerdictView(fullAudit()).overall).toBe("COMPLIANT");
    expect(buildVerdictView(bankAudit()).overall).toBe("NON_COMPLIANT");
  });

  it("calls a stock the two standards disagree on questionable, not the worse of the two", () => {
    const split = fullAudit({ tasis_evaluation: standard("TASIS", { status: "NON_COMPLIANT", is_compliant: false }) });
    expect(buildVerdictView(split).overall).toBe("QUESTIONABLE");
  });

  it("uses the engine's own verdict when the result carries one", () => {
    const split = fullAudit({
      aaoifi_evaluation: standard("AAOIFI", { status: "QUESTIONABLE", is_compliant: false }),
      tasis_evaluation: standard("TASIS", { status: "NON_COMPLIANT", is_compliant: false }),
    });
    expect(buildVerdictView(split).overall).toBe("QUESTIONABLE"); // two statuses alone
    expect(buildVerdictView({ ...split, overall_status: "NON_COMPLIANT" }).overall).toBe("NON_COMPLIANT");
  });
});

describe("buildVerdictView, business line", () => {
  it("shows the rule and the word it matched on", () => {
    const sector = buildVerdictView(bankAudit()).sector;
    expect(sector.passed).toBe(false);
    expect(sector.detail).toBe(
      'The rule "Interest based finance" matched the word "financial services". ' +
        "Conventional banking and interest lending (Riba).",
    );
  });

  it("says a passing business line matched no rule", () => {
    const sector = buildVerdictView(fullAudit()).sector;
    expect(sector.passed).toBe(true);
    expect(sector.heading).toBe("Business line: Information Technology. Passed.");
  });

  it("falls back to the older fields when the rule is missing", () => {
    const view = buildVerdictView(olderAudit({ sector_compliant: false, sector_failure_reason: "Sells liquor" }));
    expect(view.sector.passed).toBe(false);
    expect(view.sector.detail).toBe("Sells liquor.");
  });
});

describe("buildVerdictView, evidence", () => {
  it("lists where the figures came from, with the filing date written for a person", () => {
    const view = buildVerdictView(fullAudit());
    expect(view.sources).toEqual([
      { label: "Source document", value: "BSE/NSE Annual Audited Report" },
      { label: "Reporting period", value: "Q4 FY24 Audited Consolidated" },
      { label: "Filed on", value: "12 Apr 2024" },
    ]);
  });

  it("keeps the new fields when they are there", () => {
    const view = buildVerdictView(fullAudit());
    expect(view.dataStatus).toBe("UNVERIFIED_SAMPLE");
    expect(view.dataNotice).toContain("Illustrative sample");
    expect(view.screenedAt).toBe("7 Oct 2026, 10:15 am India time");
    expect(view.methodology).toBe("shariah-screen-v1");
    expect(view.notCovered).toHaveLength(3);
  });

  it("hides what an older response does not have, without failing", () => {
    const view = buildVerdictView(olderAudit({ source_document: null }));
    expect(view.dataStatus).toBeUndefined();
    expect(view.dataNotice).toBeNull();
    expect(view.screenedAt).toBeNull();
    expect(view.methodology).toBeNull();
    expect(view.notCovered).toEqual([]);
    expect(view.sources.map((row) => row.label)).toEqual(["Reporting period", "Filed on"]);
  });
});
