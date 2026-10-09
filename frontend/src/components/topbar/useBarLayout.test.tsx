import { act, cleanup, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { barWidth } from "./topbarKit";
import { barLayout, INLINE_FROM, useBarLayout } from "./useBarLayout";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("how much room the bar has", () => {
  const ROWS_1 = [
    [0, "inline"],
    [320, "popover"],
    [1000, "popover"],
    [INLINE_FROM - 1, "popover"],
    [INLINE_FROM, "inline"],
    [1920, "inline"],
  ] as const;

  it.each(ROWS_1)("a bar %i wide shows the chips %s", (width, layout) => {
    expect(barLayout(width)).toBe(layout);
  });
});

function Probe() {
  const bar = useRef<HTMLElement>(null);
  const layout = useBarLayout(bar);
  return <header ref={bar}>{layout}</header>;
}

describe("measuring the bar", () => {
  it("measures before the first paint, so the right shape is shown at once", () => {
    barWidth(900);
    render(<Probe />);
    expect(screen.getByRole("banner")).toHaveTextContent("popover");
  });

  it("shows the chips where nothing can be measured", () => {
    render(<Probe />);
    expect(screen.getByRole("banner")).toHaveTextContent("inline");
  });

  it("follows the window as it is resized", () => {
    let report: (entries: { contentRect: { width: number } }[]) => void = () => undefined;
    const disconnect = vi.fn();
    class FakeObserver {
      constructor(callback: typeof report) {
        report = callback;
      }
      observe() {}
      disconnect = disconnect;
    }
    vi.stubGlobal("ResizeObserver", FakeObserver);
    barWidth(1800);
    const view = render(<Probe />);
    expect(screen.getByRole("banner")).toHaveTextContent("inline");
    act(() => report([{ contentRect: { width: 1100 } }]));
    expect(screen.getByRole("banner")).toHaveTextContent("popover");
    act(() => report([{ contentRect: { width: 1700 } }]));
    expect(screen.getByRole("banner")).toHaveTextContent("inline");
    view.unmount();
    expect(disconnect).toHaveBeenCalled();
  });
});
