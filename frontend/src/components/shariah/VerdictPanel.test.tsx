import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { bankAudit, fullAudit, olderAudit } from "./shariahFixtures";
import { VerdictPanel } from "./VerdictPanel";

const TOGGLE = "How this verdict was reached";

function open() {
  fireEvent.click(screen.getByRole("button", { name: TOGGLE }));
}

afterEach(cleanup);

describe("VerdictPanel", () => {
  it("is closed until one click opens it, and says so to a screen reader", () => {
    render(<VerdictPanel audit={fullAudit()} />);
    const toggle = screen.getByRole("button", { name: TOGGLE });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Source document")).not.toBeVisible();
    open();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Source document")).toBeVisible();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("shows each ratio with its formula, figures, limit and headroom, per standard", () => {
    render(<VerdictPanel audit={fullAudit()} />);
    open();
    const aaoifi = screen.getByRole("region", { name: "AAOIFI: Passed" });
    const reason = "All four ratios are within their limits and the business line passed.";
    const formula = "Total Interest-Bearing Debt divided by 36-Month Rolling Average Market Cap";
    expect(within(aaoifi).getByText(reason)).toBeVisible();
    expect(within(aaoifi).getByText(formula)).toBeVisible();
    expect(within(aaoifi).getByText("₹7,970.00 Cr divided by ₹13,85,400.00 Cr = 0.58%")).toBeVisible();
    expect(within(aaoifi).getAllByText(/Limit: under 33%/).length).toBeGreaterThan(0);
    expect(within(aaoifi).getAllByText(/Headroom: 32.42 percentage points under the limit./).length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: "TASIS: Passed" })).toBeVisible();
  });

  it("names the rule and the word a failed business line matched on", () => {
    render(<VerdictPanel audit={bankAudit()} />);
    open();
    expect(screen.getByText("Business line: Financial Services. Failed.")).toBeVisible();
    expect(screen.getByText(/matched the word "financial services"/)).toBeVisible();
    expect(screen.getAllByText(/Over the limit by 55.20 percentage points\./)).toHaveLength(1);
  });

  it("shows where the figures came from, with their data status and notice", () => {
    render(<VerdictPanel audit={fullAudit()} />);
    open();
    expect(screen.getByText("BSE/NSE Annual Audited Report")).toBeVisible();
    expect(screen.getByText("Q4 FY24 Audited Consolidated")).toBeVisible();
    expect(screen.getByText("12 Apr 2024")).toBeVisible();
    expect(screen.getByText("Illustrative sample, not audited")).toBeVisible();
    expect(screen.getByText(/not read from audited filings and not live/)).toBeVisible();
  });

  it("says when it was screened, in India time, and by which rules", () => {
    render(<VerdictPanel audit={fullAudit()} />);
    open();
    expect(screen.getByText(/Screened at 7 Oct 2026, 10:15 am India time/)).toBeVisible();
    expect(screen.getByText(/rules version shariah-screen-v1/)).toBeVisible();
  });

  it("lists what the result does not cover and says it is not a ruling", () => {
    render(<VerdictPanel audit={fullAudit()} />);
    open();
    expect(screen.getByText("No scholar has reviewed this result.")).toBeVisible();
    expect(screen.getByText("A screening aid, not a religious ruling (fatwa)")).toBeVisible();
  });

  it("shows what exists and hides the rest for an older response, with no blank and no crash", () => {
    render(<VerdictPanel audit={olderAudit()} />);
    open();
    expect(screen.getByText("Q4 FY24 Audited Consolidated")).toBeVisible();
    expect(screen.getByText("Not verified")).toBeVisible();
    expect(screen.queryByText(/Screened at/)).toBeNull();
    expect(screen.queryByText("What this result does not cover")).toBeNull();
    expect(screen.getByText("A screening aid, not a religious ruling (fatwa)")).toBeVisible();
  });
});
