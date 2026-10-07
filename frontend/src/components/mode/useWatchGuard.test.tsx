import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useShariahStatuses } from "../../lib/shariahStatus";
import { routeApi } from "../agents/testHarness";
import {
  COMPLIANT_ROW,
  NON_COMPLIANT_ROW,
  NOT_SCREENED_ROW,
  QUESTIONABLE_ROW,
  renderPage,
  statuses,
  statusFor,
  statusUrl,
} from "./modeKit";
import { useWatchGuard } from "./useWatchGuard";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

function Page({ add = true, go }: { add?: boolean; go: () => void }) {
  const guard = useWatchGuard("TCS");
  const lookup = useShariahStatuses(["TCS"]);
  return (
    <>
      <output>{lookup.state}</output>
      <button type="button" onClick={() => guard.ask(add, go)}>
        Watch
      </button>
      {guard.dialog}
    </>
  );
}

function engine(shariah: boolean, row?: unknown) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    [statusUrl("TCS")]: statuses({ TCS: row as never }),
  });
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("adding a stock to a watchlist in Shariah mode", () => {
  const CASES_1 = [
    [NON_COMPLIANT_ROW, "TCS is not Shariah-compliant (Debt is over the limit). Add it anyway?"],
    [QUESTIONABLE_ROW, "TCS is questionable under Shariah screening (The standards disagree). Add it anyway?"],
    [NOT_SCREENED_ROW, "TCS has not been screened for Shariah compliance (Not screened yet). Add it anyway?"],
  ] as const;

  it.each(CASES_1)("asks first, in plain words, for a stock that is not confirmed compliant", async (row, question) => {
    engine(true, row);
    const go = vi.fn();
    renderPage(<Page go={go} />);
    await screen.findByText("ready");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(question);
    expect(go).not.toHaveBeenCalled();
  });

  it("does not add it when the person says no, and gives focus back to the button", async () => {
    engine(true, NON_COMPLIANT_ROW);
    const go = vi.fn();
    renderPage(<Page go={go} />);
    await screen.findByText("ready");
    const watch = screen.getByRole("button", { name: "Watch" });
    watch.focus();
    fireEvent.click(watch);
    fireEvent.click(await screen.findByRole("button", { name: "Don't add" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(go).not.toHaveBeenCalled();
    await waitFor(() => expect(watch).toHaveFocus());
  });

  it("adds it when the person says so", async () => {
    engine(true, NON_COMPLIANT_ROW);
    const go = vi.fn();
    renderPage(<Page go={go} />);
    await screen.findByText("ready");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    fireEvent.click(await screen.findByRole("button", { name: "Add anyway" }));
    expect(go).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("treats Escape as no", async () => {
    engine(true, NON_COMPLIANT_ROW);
    const go = vi.fn();
    renderPage(<Page go={go} />);
    await screen.findByText("ready");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    await screen.findByRole("dialog");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(go).not.toHaveBeenCalled();
  });

  it("does not ask for a compliant stock", async () => {
    engine(true, COMPLIANT_ROW);
    const go = vi.fn();
    renderPage(<Page go={go} />);
    await screen.findByText("ready");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(go).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("never asks before taking a stock off a watchlist", async () => {
    engine(true, NON_COMPLIANT_ROW);
    const go = vi.fn();
    renderPage(<Page add={false} go={go} />);
    await screen.findByText("ready");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(go).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("adding a stock to a watchlist in Institutional mode", () => {
  it("never asks, and never looks up a Shariah result", async () => {
    engine(false, NON_COMPLIANT_ROW);
    const go = vi.fn();
    renderPage(<Page go={go} />);
    await screen.findByText("off");
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(go).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api).mock.calls.filter(([p]) => String(p).includes("/shariah/status"))).toHaveLength(0);
  });
});
