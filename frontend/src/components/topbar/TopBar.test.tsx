import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { renderPage } from "../update/updateKit";
import { barWidth, engine, HOLIDAYS_2026, LIVE_OFF, statusAnswer, WED_MORNING_IN_INDIA, withUpdate } from "./topbarKit";
import { TopBar } from "./TopBar";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});
// The Copilot's own button and the second-opinion chip are tested with the Copilot; here they are stand-ins.
vi.mock("../copilot/CopilotButton", () => ({ CopilotButton: () => <button type="button">Copilot</button> }));
vi.mock("../copilot/SecondOpinionReady", () => ({ SecondOpinionReady: () => null }));

function show(path = "/", onSearch = vi.fn()) {
  renderPage(<TopBar onSearch={onSearch} />, path);
  return onSearch;
}
const chip = (name: string) => screen.findByRole("link", { name });
const status = () => screen.getByRole("group", { name: "Status" });
const controls = (box: HTMLElement) => [...box.querySelectorAll("a, button")];

beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(WED_MORNING_IN_INDIA);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("where you are", () => {
  it("names the screen, and the screen it sits inside as a way back", async () => {
    engine();
    show("/settings/ai");
    expect(screen.getByText("AI assistants")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Settings" })).toHaveAttribute("href", "/settings/profile");
    await chip("Prices as of 6 Oct");
  });

  it("names a screen that sits inside nothing without a way back", async () => {
    engine();
    show("/markets");
    expect(screen.getByText("Markets", { selector: "p" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Back to/ })).not.toBeInTheDocument();
    await chip("Prices as of 6 Oct");
  });

  it("names a stock by its symbol, with Markets as the way back", async () => {
    engine();
    show("/stock/tcs");
    expect(screen.getByText("TCS")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Markets" })).toHaveAttribute("href", "/markets");
    await chip("Prices as of 6 Oct");
  });
});

describe("search", () => {
  it("looks like a search field and opens the search window when pressed", async () => {
    engine();
    const onSearch = show();
    const field = screen.getByRole("button", { name: /Search stocks, pages/ });
    fireEvent.click(field);
    expect(onSearch).toHaveBeenCalledTimes(1);
    expect(field).toHaveAttribute("aria-keyshortcuts", "Control+K");
    await chip("Prices as of 6 Oct");
  });
});

describe("the chips, on a wide bar", () => {
  it("says the market, the prices and live prices, each as a link with words", async () => {
    engine();
    show();
    const prices = await chip("Prices as of 6 Oct");
    const group = status();
    const live = await within(group).findByRole("link", { name: "Live prices on" });
    expect(within(group).getByRole("link", { name: "Market hours" })).toHaveAttribute("href", "/markets");
    expect(prices).toHaveAttribute("href", "/settings/data");
    expect(live).toHaveAttribute("href", "/settings/accounts");
  });

  it("says Market open, not Market hours, once the engine has sent this year's holidays", async () => {
    engine({ holidays: HOLIDAYS_2026 });
    show();
    expect(await chip("Market open")).toHaveAttribute("href", "/markets");
    expect(within(status()).queryByRole("link", { name: "Market hours" })).not.toBeInTheDocument();
  });

  it("says Market closed, holiday, on a day the exchange is shut", async () => {
    engine({ holidays: { years: [2026], holidays: [{ date: "2026-10-07", name: "A day off" }] } });
    show();
    expect(await chip("Market closed, holiday")).toHaveAttribute("href", "/markets");
  });

  it("keeps saying Market hours when the holidays it was sent are for another year", async () => {
    engine({ holidays: { years: [2025], holidays: [{ date: "2025-10-02", name: "Mahatma Gandhi Jayanti" }] } });
    show();
    await chip("Prices as of 6 Oct");
    expect(within(status()).getByRole("link", { name: "Market hours" })).toBeInTheDocument();
    expect(within(status()).queryByRole("link", { name: /^Market (open|closed)/ })).not.toBeInTheDocument();
  });

  it("keeps saying Market hours when the engine has no holidays to send", async () => {
    engine();
    show();
    await chip("Prices as of 6 Oct");
    expect(within(status()).getByRole("link", { name: "Market hours" })).toBeInTheDocument();
  });

  it("says Out of date, with the day, when prices are more than a trading day old", async () => {
    engine({ status: statusAnswer("2026-09-29") });
    show();
    expect(await chip("Out of date, 29 Sep")).toHaveAttribute("href", "/settings/data");
  });

  it("says No prices yet, and links to Market data, on a computer with none", async () => {
    engine({ status: statusAnswer(null) });
    show();
    expect(await chip("No prices yet")).toHaveAttribute("href", "/settings/data");
  });

  it("says Live prices off, and links to Accounts and keys, when no key works", async () => {
    engine({ live: LIVE_OFF });
    show();
    expect(await chip("Live prices off")).toHaveAttribute("href", "/settings/accounts");
  });

  it("shows no live prices chip while it cannot tell", async () => {
    engine({
      live: () => {
        throw new Error("The engine could not say.");
      },
    });
    show();
    await chip("Prices as of 6 Oct");
    expect(screen.queryByText(/Live prices|last close/i)).not.toBeInTheDocument();
  });

  it("shows no update chip when there is no newer version", async () => {
    engine();
    show();
    await chip("Prices as of 6 Oct");
    expect(screen.queryByText(/Update available/)).not.toBeInTheDocument();
  });

  it("leaves every chip reachable by keyboard", async () => {
    withUpdate();
    show();
    await screen.findByRole("button", { name: "Update available: v2.6.0" });
    const reachable = controls(status());
    expect(reachable).toHaveLength(4);
    reachable.forEach((item) => expect(item).not.toHaveAttribute("tabindex", "-1"));
  });
});

describe("the update chip", () => {
  it("says Update available with the version and opens what is new", async () => {
    withUpdate();
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Update available: v2.6.0" }));
    expect(await screen.findByText("QuantOS 2.6.0 is ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update and restart" })).toBeInTheDocument();
  });
});

describe("on a narrow bar", () => {
  beforeEach(() => {
    barWidth(1000);
  });

  it("collapses the chips into one Status button that names what needs doing", async () => {
    withUpdate();
    show();
    const button = await screen.findByRole("button", { name: "Status. Update available: v2.6.0" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("group", { name: "Status" })).not.toBeInTheDocument();
  });

  it("speaks for the market when nothing needs doing", async () => {
    engine();
    show();
    expect(await screen.findByRole("button", { name: "Status. Market hours" })).toBeInTheDocument();
  });

  it("opens a list of every chip, and Escape closes it and gives focus back to the button", async () => {
    withUpdate();
    show();
    const button = await screen.findByRole("button", { name: /^Status/ });
    button.focus();
    fireEvent.click(button);
    const list = await screen.findByRole("group", { name: "Market, prices and updates" });
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(controls(list)).toHaveLength(4);
    fireEvent.keyDown(list, { key: "Escape" });
    expect(screen.queryByRole("group", { name: "Market, prices and updates" })).not.toBeInTheDocument();
    expect(button).toHaveFocus();
  });

  it("closes on a click elsewhere", async () => {
    engine();
    show();
    fireEvent.click(await screen.findByRole("button", { name: /^Status/ }));
    await screen.findByRole("group", { name: "Market, prices and updates" });
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("group", { name: "Market, prices and updates" })).not.toBeInTheDocument();
  });

  it("closes the list and opens the update window from the update row", async () => {
    withUpdate();
    show();
    fireEvent.click(await screen.findByRole("button", { name: /^Status/ }));
    const list = await screen.findByRole("group", { name: "Market, prices and updates" });
    fireEvent.click(within(list).getByRole("button", { name: /Update available/ }));
    expect(await screen.findByText("QuantOS 2.6.0 is ready")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Market, prices and updates" })).not.toBeInTheDocument();
  });

  it("shows the market chip's longer sentence in the list", async () => {
    engine();
    show();
    fireEvent.click(await screen.findByRole("button", { name: /^Status/ }));
    const list = await screen.findByRole("group", { name: "Market, prices and updates" });
    await waitFor(() => expect(within(list).getByText(/cannot see exchange holidays/)).toBeInTheDocument());
  });
});
