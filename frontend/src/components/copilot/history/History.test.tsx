import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../../lib/api";
import { box, openDrawer, Shell } from "../chatTestKit";
import { renderApp, serveApi } from "../testHarness";
import {
  BASE,
  callsStarting,
  FakeEngine,
  historyButton,
  listedTitles,
  openHistory,
  panel,
  SEED,
  search,
  searchBox,
} from "./historyKit";

vi.mock("../../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../lib/api")>();
  return { ...original, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  window.localStorage.clear();
  // Only the clock is held still, so "Yesterday" and "5 Oct" read the same on any day the tests run.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 7, 12, 0));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

async function showHistory(seed = SEED) {
  const engine = new FakeEngine(seed);
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  await openHistory();
  return engine;
}

describe("the History panel", () => {
  it("replaces the thread, says the chats stay on this computer, and puts the cursor in the search box", async () => {
    await showHistory();
    const region = panel();
    expect(within(region).getByText("Your chats are saved on this computer only.")).toBeInTheDocument();
    expect(within(region).getByRole("button", { name: "Back to chat" })).toBeInTheDocument();
    expect(searchBox()).toHaveFocus();
    expect(screen.queryByRole("textbox", { name: "Your message to the Copilot" })).toBeNull();
    expect(screen.queryByText("Ask the Copilot")).toBeNull();
  });

  it("has a History button and a New chat button in the header, each with a name", async () => {
    new FakeEngine(SEED);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    expect(historyButton()).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "New chat" })).toBeInTheDocument();
    await openHistory();
    expect(historyButton()).toHaveAttribute("aria-pressed", "true");
  });

  it("lists the saved chats newest first as a real list", async () => {
    await showHistory();
    const list = await screen.findByRole("list", { name: "Your saved chats" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(listedTitles()).toEqual(["show my watchlist", "is AAA halal?", "how is INFY doing?"]);
  });

  it("shows each chat's one-line preview, a plain date and its message count", async () => {
    await showHistory();
    const watchlist = (await screen.findByRole("button", { name: /^show my watchlist/ })).textContent;
    expect(watchlist).toContain("You are watching 3 stocks.");
    expect(watchlist).toContain("Yesterday · 2 messages");
    const older = screen.getByRole("button", { name: /^is AAA halal\?/ }).textContent;
    expect(older).toContain("5 Oct · 2 messages");
    expect(screen.getByRole("button", { name: /^how is INFY doing\?/ }).textContent).toContain("4 Oct · 1 message");
  });

  it("says plainly that there is nothing saved yet", async () => {
    await showHistory([]);
    const sentence = "No saved chats yet. Ask the Copilot something and it will appear here.";
    expect(await screen.findByText(sentence)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear all history" })).toBeNull();
  });

  it("says so when the engine cannot be reached, and asks again on Try again", async () => {
    serveApi(() => {
      throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
    });
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    await openHistory();
    expect(await screen.findByText("Your chats could not be loaded just now.")).toBeInTheDocument();
    new FakeEngine(SEED);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Your saved chats" })).toBeInTheDocument();
    expect(screen.queryByText("Your chats could not be loaded just now.")).toBeNull();
  });
});

const SEARCHES: [string, string, string[]][] = [
  ["a word in a title", "halal", ["is AAA halal?"]],
  ["a word said inside a chat", "watching", ["show my watchlist"]],
  ["capital letters it does not care about", "INFY", ["how is INFY doing?"]],
];

describe("searching the chats", () => {
  it.each(SEARCHES)("finds %s", async (_name, words, found) => {
    await showHistory();
    await screen.findByRole("list", { name: "Your saved chats" });
    search(words);
    await waitFor(() => expect(listedTitles()).toEqual(found));
    expect(callsStarting("GET", `${BASE}?q=${words}`)).toHaveLength(1);
  });

  it("asks the engine once when typing stops, not once for every letter", async () => {
    await showHistory();
    await screen.findByRole("list", { name: "Your saved chats" });
    ["h", "ha", "hal"].forEach(search);
    await waitFor(() => expect(listedTitles()).toEqual(["is AAA halal?"]));
    expect(callsStarting("GET", `${BASE}?q=`).map(([path]) => path)).toEqual([`${BASE}?q=hal`]);
  });

  it("says no chat matches, and brings every chat back when the search is cleared", async () => {
    await showHistory();
    await screen.findByRole("list", { name: "Your saved chats" });
    search("zzzz");
    expect(await screen.findByText("No chat matches that.")).toBeInTheDocument();
    search("");
    await waitFor(() => expect(listedTitles()).toHaveLength(3));
    expect(screen.queryByText("No chat matches that.")).toBeNull();
  });

  it("does not offer Clear all history while only some of the chats are shown", async () => {
    await showHistory();
    expect(await screen.findByRole("button", { name: "Clear all history" })).toBeInTheDocument();
    search("halal");
    await waitFor(() => expect(listedTitles()).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "Clear all history" })).toBeNull();
  });
});

describe("leaving the History panel", () => {
  it("goes back to the thread with Back to chat, and focus returns to the History button", async () => {
    await showHistory();
    fireEvent.click(screen.getByRole("button", { name: "Back to chat" }));
    expect(box()).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Your chats" })).toBeNull();
    await waitFor(() => expect(historyButton()).toHaveFocus());
  });

  it("goes back with the History button too, and keeps what was typed", async () => {
    new FakeEngine(SEED);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByRole("dialog");
    fireEvent.change(box(), { target: { value: "half a thought" } });
    await openHistory();
    fireEvent.click(historyButton());
    expect(box()).toHaveValue("half a thought");
  });

  it("takes Escape back to the thread first, and the drawer closes on the next one", async () => {
    await showHistory();
    fireEvent.keyDown(searchBox(), { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(box()).toBeInTheDocument();
    await waitFor(() => expect(historyButton()).toHaveFocus());
    fireEvent.keyDown(historyButton(), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("shows the thread again, not the history, when the drawer is closed and opened", async () => {
    await showHistory();
    fireEvent.click(screen.getByRole("button", { name: "Close Copilot" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    openDrawer();
    expect(await screen.findByRole("textbox", { name: "Your message to the Copilot" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Your chats" })).toBeNull();
  });
});
