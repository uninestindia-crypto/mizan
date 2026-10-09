import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../lib/api";
import { CHAT_STORAGE_KEY } from "../../../lib/copilotHistory";
import { box, openDrawer, say, Shell } from "../chatTestKit";
import { renderApp } from "../testHarness";
import {
  BASE,
  CHAT,
  CHAT_GONE,
  callsStarting,
  chatButton,
  type EngineOptions,
  FakeEngine,
  holdBack,
  openHistory,
  SEED,
} from "./historyKit";

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

async function openedDrawer(options: EngineOptions = {}) {
  const engine = new FakeEngine(SEED, options);
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  return engine;
}

/** Opens a chat from the list, and waits for the panel to give way to the thread (the list also quotes the chat). */
async function openChatFromHistory(title: string) {
  await openHistory();
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(`^${title}`) }));
  await waitFor(() => expect(screen.queryByRole("region", { name: "Your chats" })).toBeNull());
}

/** What each question sent to the engine, oldest first. */
function bodies(): Record<string, unknown>[] {
  return callsStarting("POST", CHAT).map(([, , body]) => body as Record<string, unknown>);
}

describe("opening a saved chat", () => {
  it("shows its messages as they were, with what the Copilot looked at, its buttons and who answered", async () => {
    await openedDrawer();
    await openChatFromHistory("is AAA halal");
    expect(await screen.findByText("AAA passes both standards.")).toBeInTheDocument();
    expect(screen.getByText("is AAA halal?")).toBeInTheDocument();
    expect(screen.getByText("What I looked at")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open AAA" })).toBeInTheDocument();
    expect(screen.getByText("Answered by OpenAI")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Your chats" })).toBeNull();
  });

  it("puts the cursor in the message box, ready to carry on", async () => {
    await openedDrawer();
    await openChatFromHistory("show my watchlist");
    await screen.findByText("You are watching 3 stocks.");
    await waitFor(() => expect(box()).toHaveFocus());
  });

  it("carries the chat on: the next question names the chat and keeps what was said before", async () => {
    const engine = await openedDrawer();
    await openChatFromHistory("is AAA halal");
    await screen.findByText("AAA passes both standards.");
    await say("and its debt?");
    expect(await screen.findByText("Answer to: and its debt?")).toBeInTheDocument();
    expect(bodies()[0]).toMatchObject({ conversation_id: "chat-a" });
    expect(bodies()[0]?.messages).toEqual([
      { role: "user", content: "is AAA halal?" },
      { role: "assistant", content: "AAA passes both standards." },
      { role: "user", content: "and its debt?" },
    ]);
    expect(engine.chats.find((chat) => chat.id === "chat-a")?.messages).toHaveLength(4);
    expect(engine.chats).toHaveLength(3);
  });

  it("marks the chat that is open in the list", async () => {
    await openedDrawer();
    await openChatFromHistory("is AAA halal");
    await screen.findByText("AAA passes both standards.");
    await openHistory();
    expect(await screen.findByText("Open now")).toBeInTheDocument();
    expect(chatButton("is AAA halal?")).toHaveAttribute("aria-current", "true");
  });

  it("says so, and refreshes the list, when the chat was deleted from somewhere else", async () => {
    const engine = await openedDrawer();
    await openHistory();
    await screen.findByRole("list", { name: "Your saved chats" });
    engine.chats = engine.chats.filter((chat) => chat.id !== "chat-a");
    fireEvent.click(chatButton("is AAA halal?"));
    expect(await screen.findByText("That chat is no longer here. The list has been refreshed.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("button", { name: /^is AAA halal\?/ })).toBeNull());
    expect(screen.getByRole("region", { name: "Your chats" })).toBeInTheDocument();
  });
});

describe("the first message and New chat", () => {
  it("starts a saved chat with the first message, then keeps the chat it was given", async () => {
    const engine = await openedDrawer();
    await say("one");
    await screen.findByText("Answer to: one");
    await say("two");
    await screen.findByText("Answer to: two");
    expect(bodies().map((body) => body.conversation_id)).toEqual(["new", "made-1"]);
    expect(engine.chats.find((chat) => chat.id === "made-1")?.messages).toHaveLength(4);
  });

  it("starts an empty thread on New chat, deletes nothing, and the next question starts a new chat", async () => {
    const engine = await openedDrawer();
    await openChatFromHistory("is AAA halal");
    await screen.findByText("AAA passes both standards.");
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.queryByText("AAA passes both standards.")).toBeNull();
    expect(screen.getByRole("button", { name: "What can you do?" })).toBeInTheDocument();
    expect(callsStarting("DELETE", BASE)).toHaveLength(0);
    expect(engine.chats).toHaveLength(3);
    expect(window.localStorage.getItem(CHAT_STORAGE_KEY)).toBeNull();
    await say("fresh");
    await screen.findByText("Answer to: fresh");
    expect(bodies().map((body) => body.conversation_id)).toEqual(["new"]);
  });

  it("works from inside History too: New chat closes the panel on an empty thread", async () => {
    await openedDrawer();
    await openChatFromHistory("is AAA halal");
    await screen.findByText("AAA passes both standards.");
    await openHistory();
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.queryByRole("region", { name: "Your chats" })).toBeNull();
    expect(screen.queryByText("AAA passes both standards.")).toBeNull();
    await waitFor(() => expect(box()).toHaveFocus());
  });

  it("empties the thread when the chat that is open is deleted, so nothing is sent to it", async () => {
    await openedDrawer();
    await openChatFromHistory("is AAA halal");
    await screen.findByText("AAA passes both standards.");
    await openHistory();
    fireEvent.click(await screen.findByRole("button", { name: "Delete chat: is AAA halal?" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Open now")).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Back to chat" }));
    expect(screen.queryByText("AAA passes both standards.")).toBeNull();
    expect(screen.getByRole("button", { name: "What can you do?" })).toBeInTheDocument();
  });
});

const MOVES_ON: [string, () => Promise<unknown>][] = [
  ["opens another chat", async () => openChatFromHistory("show my watchlist")],
  ["starts a new chat", async () => fireEvent.click(screen.getByRole("button", { name: "New chat" }))],
];

describe("an answer that arrives after the person moved on", () => {
  it.each(MOVES_ON)("is not added to the wrong chat when the person %s while it is awaited", async (_name, moveOn) => {
    const { gate, release } = holdBack();
    const engine = await openedDrawer({ gate });
    await say("slow question");
    expect(await screen.findByText("Thinking…")).toBeInTheDocument();
    await moveOn();
    await act(async () => release());
    await waitFor(() => expect(engine.chats.some((chat) => chat.id === "made-1")).toBe(true));
    expect(screen.queryByText("Answer to: slow question")).toBeNull();
    expect(screen.queryByText("Thinking…")).toBeNull();
    expect(screen.queryByText("slow question")).toBeNull();
  });

  it("lets the person ask in the chat they moved to, and the late answer still reaches the saved list", async () => {
    const { gate, release } = holdBack();
    const engine = await openedDrawer({ gate });
    await say("slow question");
    await openChatFromHistory("show my watchlist");
    await screen.findByText("You are watching 3 stocks.");
    await act(async () => release());
    await say("next");
    expect(await screen.findByText("Answer to: next")).toBeInTheDocument();
    expect(bodies().map((body) => body.conversation_id)).toEqual(["new", "chat-b"]);
    expect(engine.chats.find((chat) => chat.id === "chat-b")?.messages).toHaveLength(4);
  });
});

describe("a chat that is gone while the person writes in it", () => {
  it("says so in the engine's own words, hands the question back, and starts a new chat next time", async () => {
    const engine = await openedDrawer();
    await openChatFromHistory("is AAA halal");
    await screen.findByText("AAA passes both standards.");
    engine.chats = [];
    await say("still there?");
    expect(await screen.findByText(CHAT_GONE)).toBeInTheDocument();
    expect(box()).toHaveValue("still there?");
    await say("still there?");
    await screen.findByText("Answer to: still there?");
    expect(bodies().map((body) => body.conversation_id)).toEqual(["chat-a", "new"]);
  });
});
