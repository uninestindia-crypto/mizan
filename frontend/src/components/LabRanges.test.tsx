import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { LabRanges as Ranges } from "../lib/types";
import { LabRanges } from "./LabRanges";

const NOTE = "How much of this could be luck of the particular days. The range is where the middle 90 out of 100 reshuffles of the same days landed. It is not a promise about the future, and it does not count the other ideas you may have tried: the verdict above does.";

const RANGES: Ranges = {
  level: 0.9,
  resamples: 2000,
  block: 10,
  sessions: 1250,
  sharpe: { low: -0.31, high: 1.42 },
  cagr: { low: -0.021, high: 0.184 },
  max_drawdown: { low: -0.38, high: -0.12 },
  note: NOTE,
};

afterEach(cleanup);

describe("How much of this could be luck", () => {
  it("shows each measure as a range, in the units the table above uses", () => {
    render(<LabRanges ranges={RANGES} />);
    const box = screen.getByRole("region", { name: "How much of this could be luck" });
    expect(within(box).getByText("The middle 90 of 100 reshuffles of the same 1,250 days")).toBeInTheDocument();
    expect(within(box).getByText("−2.1% to +18.4%")).toBeInTheDocument();
    expect(within(box).getByText("−38.0% to −12.0%")).toBeInTheDocument();
    expect(within(box).getByText("-0.31 to 1.42")).toBeInTheDocument();
  });

  it("says what the range does not cover", () => {
    render(<LabRanges ranges={RANGES} />);
    expect(screen.getByText(NOTE)).toBeInTheDocument();
    expect(screen.getByText(/It is not a promise about the future/)).toBeInTheDocument();
  });

  it("says so when a measure cannot be estimated, for example the Sharpe ratio of a flat strategy", () => {
    render(<LabRanges ranges={{ ...RANGES, sharpe: { low: null, high: null } }} />);
    expect(screen.getByText("Not enough movement to say")).toBeInTheDocument();
  });

  it("shows nothing for a run saved before ranges existed, or one that was too short", () => {
    const { container, rerender } = render(<LabRanges ranges={undefined} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<LabRanges ranges={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("promises nothing and gives no advice", () => {
    const { container } = render(<LabRanges ranges={RANGES} />);
    expect(container.textContent ?? "").not.toMatch(/\b(will|guarantee|should|buy|sell|profit)\b/i);
  });
});
