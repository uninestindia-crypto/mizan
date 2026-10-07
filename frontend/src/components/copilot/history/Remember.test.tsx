import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../lib/api";
import { CHAT_STORAGE_KEY } from "../../../lib/copilotHistory";
import { box, openDrawer, say, Shell } from "../chatTestKit";
import { renderApp } from "../testHarness";
import { BASE, callsStarting, FakeEngine, holdBack, SEED } from "./historyKit";

vi.mock("../../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../lib/api")>();
  return { ...original, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const remember = (id: string) => window.localStorage.setItem(CHAT_STORAGE_KEY, id);
const remembered = () => window.localStorage.getItem(CHAT_STORAGE_KEY);

function startAgain() {
  cleanup();
  renderApp(<Shell />);
  openDrawer();
}

describe("reopening the chat that was open last time", () => {
  it("remembers the chat once it is saved, and a fresh start reopens it", async () => {
    new FakeEngine(SEED);
    renderApp(<Shell />);
    openDrawer();
    await say("remember me");
    await screen.findByText("Answer to: remember me");
    await waitFor(() => expect(remembered()).toBe("made-1"));
    startAgain();
    expect(await screen.findByText("Answer to: remember me")).toBeInTheDocument();
    expect(screen.getByText("remember me")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "What can you do?" })).toBeNull();
  });

  it("carries on in the reopened chat", async () => {
    remember("chat-b");
    new FakeEngine(SEED);
    renderApp(<Shell />);
    openDrawer();
    await screen.findByText("You are watching 3 stocks.");
    await say("and tomorrow?");
    await screen.findByText("Answer to: and tomorrow?");
    const sent = callsStarting("POST", "/api/v2/copilot/chat")[0]?.[2];
    expect(sent).toMatchObject({ conversation_id: "chat-b" });
  });

  it("asks for the chat only when the drawer opens, and only the first time", async () => {
    remember("chat-b");
    new FakeEngine(SEED);
    renderApp(<Shell />);
    expect(callsStarting("GET", BASE)).toHaveLength(0);
    openDrawer();
    await screen.findByText("You are watching 3 stocks.");
    fireEvent.click(screen.getByRole("button", { name: "Close Copilot" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    openDrawer();
    await screen.findByText("You are watching 3 stocks.");
    expect(callsStarting("GET", `${BASE}/chat-b`)).toHaveLength(1);
  });

  it("starts a fresh chat without a word when the remembered chat is gone", async () => {
    remember("deleted-long-ago");
    new FakeEngine(SEED);
    renderApp(<Shell />);
    openDrawer();
    expect(await screen.findByRole("button", { name: "What can you do?" })).toBeInTheDocument();
    await waitFor(() => expect(remembered()).toBeNull());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/no longer/)).toBeNull();
    await say("hello");
    await screen.findByText("Answer to: hello");
    expect(callsStarting("POST", "/api/v2/copilot/chat")[0]?.[2]).toMatchObject({ conversation_id: "new" });
  });

  it("starts fresh, quietly, when the engine cannot be reached, and tries that chat again next time", async () => {
    remember("chat-b");
    vi.mocked(api).mockRejectedValue(new Error("offline"));
    renderApp(<Shell />);
    openDrawer();
    expect(await screen.findByRole("button", { name: "What can you do?" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(remembered()).toBe("chat-b");
  });

  it("says it is opening the chat, instead of flashing the starter questions, while it loads", async () => {
    remember("chat-b");
    const held = holdBack();
    new FakeEngine(SEED, { detailGate: held.gate });
    renderApp(<Shell />);
    openDrawer();
    expect(await screen.findByText("Opening your chat…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "What can you do?" })).toBeNull();
    await act(async () => held.release());
    expect(await screen.findByText("You are watching 3 stocks.")).toBeInTheDocument();
    expect(screen.queryByText("Opening your chat…")).toBeNull();
  });

  it("drops the remembered chat, without a word, if the person asks something before it has loaded", async () => {
    remember("chat-b");
    const held = holdBack();
    new FakeEngine(SEED, { detailGate: held.gate });
    renderApp(<Shell />);
    openDrawer();
    await say("typed first");
    await screen.findByText("Answer to: typed first");
    await act(async () => held.release());
    expect(screen.queryByText("You are watching 3 stocks.")).toBeNull();
    expect(screen.getByText("Answer to: typed first")).toBeInTheDocument();
    expect(callsStarting("POST", "/api/v2/copilot/chat")[0]?.[2]).toMatchObject({ conversation_id: "new" });
    expect(box()).toBeInTheDocument();
  });
});

describe("when the browser will not keep anything", () => {
  it("still saves, answers and continues the chat", async () => {
    const blocked = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(blocked);
    new FakeEngine(SEED);
    renderApp(<Shell />);
    openDrawer();
    await say("one");
    await screen.findByText("Answer to: one");
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    await say("two");
    expect(await screen.findByText("Answer to: two")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
