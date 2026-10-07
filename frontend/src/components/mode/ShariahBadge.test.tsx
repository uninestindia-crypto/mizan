import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import type { ShariahStatus } from "../../lib/shariahStatus";
import { ShariahBadge } from "./ShariahBadge";

afterEach(cleanup);

const row = (verdict: ShariahStatus["verdict"], data_status: ShariahStatus["data_status"], as_of: string | null) => ({
  verdict,
  data_status,
  short: "Because of a reason.",
  as_of,
});

const FILED = row("COMPLIANT", "VERIFIED_FILING", "2024-09-30");

describe("the Shariah badge", () => {
  const CASES_1 = [
    ["COMPLIANT", "VERIFIED_FILING", "2024-09-30", "Compliant", /Screened from the company's own filing, 30 Sep/],
    ["NON_COMPLIANT", "VERIFIED_FILING", "2024-09-30", "Not compliant", /Screened from the company's own filing/],
    ["QUESTIONABLE", "STALE", "2023-03-31", "Questionable", /Based on an old filing/],
    ["COMPLIANT", "UNVERIFIED_SAMPLE", null, "Compliant", /Illustrative sample, not from a filing/],
    ["NOT_SCREENED", "NOT_SCREENED", null, "Not screened", /Not screened yet/],
  ] as const;

  it.each(CASES_1)("says %s on %s in words, with what it rests on", (verdict, dataStatus, asOf, word, rests) => {
    render(<ShariahBadge status={row(verdict, dataStatus, asOf)} />);
    const badge = screen.getByText(word).closest("span[title]") as HTMLElement;
    expect(badge).toHaveTextContent(word);
    expect(badge.getAttribute("title")).toMatch(rests);
    expect(badge.getAttribute("title")).toContain("Because of a reason.");
    expect(badge).toHaveTextContent(rests);
  });

  const CASES_2 = [
    ["STALE", "· old filing"],
    ["UNVERIFIED_SAMPLE", "· sample"],
  ] as const;

  it.each(CASES_2)("shows a visible qualifier for a %s result", (dataStatus, qualifier) => {
    render(<ShariahBadge status={row("COMPLIANT", dataStatus, null)} compact />);
    expect(screen.getByText(qualifier)).toBeInTheDocument();
  });

  it("adds no qualifier to a result read from a filing", () => {
    render(<ShariahBadge status={row("COMPLIANT", "VERIFIED_FILING", "2024-09-30")} compact />);
    expect(screen.queryByText(/·/)).toBeNull();
  });

  it("is a link to the stock's screening when it is given a symbol", () => {
    render(<ShariahBadge status={FILED} symbol="TCS" />, { wrapper: MemoryRouter });
    const link = screen.getByRole("link", { name: /Compliant.*Open the Shariah screening for TCS/s });
    expect(link).toHaveAttribute("href", "/stock/TCS#shariah-proof");
  });

  it("is plain text, not a link, without a symbol (inside a row that already links)", () => {
    render(<ShariahBadge status={row("NON_COMPLIANT", "VERIFIED_FILING", null)} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows nothing while a stock has no result yet", () => {
    const { container } = render(<ShariahBadge status={null} symbol="TCS" />, { wrapper: MemoryRouter });
    expect(container).toBeEmptyDOMElement();
  });

  it.each(["certified", "approved", "guaranteed", "halal"])("never says %s", (word) => {
    const { container } = render(<ShariahBadge status={FILED} symbol="TCS" />, { wrapper: MemoryRouter });
    expect(container.textContent?.toLowerCase()).not.toContain(word);
  });
});
