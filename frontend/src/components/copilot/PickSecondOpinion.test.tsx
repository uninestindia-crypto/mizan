import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SECOND_OPINION_EVENT } from "../../lib/copilot";
import { PickSecondOpinion } from "./PickSecondOpinion";

afterEach(() => vi.restoreAllMocks());

describe("PickSecondOpinion", () => {
  it("opens the Second opinion window for the stock with the pick note", () => {
    const heard: unknown[] = [];
    const listener = (event: Event) => heard.push((event as CustomEvent).detail);
    window.addEventListener(SECOND_OPINION_EVENT, listener);
    render(<PickSecondOpinion symbol="TCS" note="Held by a paper book." />);
    fireEvent.click(screen.getByRole("button", { name: "Get a second opinion on TCS" }));
    window.removeEventListener(SECOND_OPINION_EVENT, listener);
    expect(heard).toEqual([{ symbol: "TCS", pickNote: "Held by a paper book." }]);
  });
});
