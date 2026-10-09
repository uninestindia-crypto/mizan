import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { renderPage } from "../update/updateKit";
import { engine, LIVE_OFF, statusAnswer, WED_MORNING_IN_INDIA, withUpdate } from "./topbarKit";
import { StatusArea } from "./StatusArea";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const LIST = { name: "Market, prices and updates" };

beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(WED_MORNING_IN_INDIA);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("on a phone", () => {
  it("is one icon button, with the words in its name and no chips beside it", async () => {
    withUpdate();
    renderPage(<StatusArea layout="phone" />);
    const button = await screen.findByRole("button", { name: "Status. Update available: v2.6.0" });
    expect(button).toHaveTextContent("");
    expect(screen.queryByRole("group", { name: "Status" })).not.toBeInTheDocument();
  });

  it("opens a list under the bar with each chip's sentence, as rows", async () => {
    engine({ live: LIVE_OFF, status: statusAnswer("2026-09-29") });
    renderPage(<StatusArea layout="phone" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Status/ }));
    const list = await screen.findByRole("group", LIST);
    expect(within(list).getByText("Out of date, 29 Sep")).toBeInTheDocument();
    expect(within(list).getByText("Live prices off")).toBeInTheDocument();
    expect(within(list).getByText(/Add your Upstox key in Settings/)).toBeInTheDocument();
  });

  it("names the out-of-date prices when there is no update", async () => {
    engine({ status: statusAnswer("2026-09-29") });
    renderPage(<StatusArea layout="phone" />);
    expect(await screen.findByRole("button", { name: "Status. Out of date, 29 Sep" })).toBeInTheDocument();
  });

  it("still says the market, which needs no engine, when every call fails", () => {
    vi.mocked(api).mockRejectedValue(new Error("offline"));
    renderPage(<StatusArea layout="phone" />);
    expect(screen.getByRole("button", { name: "Status. Market hours" })).toBeInTheDocument();
  });
});
