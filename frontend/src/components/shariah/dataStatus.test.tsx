import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DataStatusBadge, dataStatusLabel } from "./dataStatus";

afterEach(cleanup);

describe("dataStatusLabel", () => {
  it("says a sample is a sample, not audited", () => {
    expect(dataStatusLabel("UNVERIFIED_SAMPLE")).toBe("Illustrative sample, not audited");
  });

  it("only calls data checked when a filing backs it", () => {
    expect(dataStatusLabel("VERIFIED_FILING")).toBe("Checked against the company's filing");
    expect(dataStatusLabel("STALE")).toBe("Out of date, needs a fresh check");
  });

  it("says Not verified for anything it does not know, or for nothing at all", () => {
    expect(dataStatusLabel("SOMETHING_NEW")).toBe("Not verified");
    expect(dataStatusLabel(null)).toBe("Not verified");
    expect(dataStatusLabel(undefined)).toBe("Not verified");
  });
});

describe("DataStatusBadge", () => {
  it("shows the plain words, so the verdict is never read without its data status", () => {
    render(<DataStatusBadge status="UNVERIFIED_SAMPLE" />);
    expect(screen.getByText("Illustrative sample, not audited")).toBeInTheDocument();
  });

  it("shows Not verified when the response has no status", () => {
    render(<DataStatusBadge status={undefined} />);
    expect(screen.getByText("Not verified")).toBeInTheDocument();
  });
});
