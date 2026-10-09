import { describe, expect, it } from "vitest";
import { type ChatReply, normaliseReply } from "../../lib/copilot";
import {
  type AssistantMessage,
  type ChatAction,
  type ChatState,
  chatReducer,
  initialChat,
  keyButton,
  keyHelp,
  replyExplainsKeys,
  type SavedMessage,
  visibleProposals,
} from "./chatState";

const run = (actions: ChatAction[], from: ChatState = initialChat): ChatState => actions.reduce(chatReducer, from);
const reply = (text: string) => normaliseReply({ reply: text, mode: "ai", provider: "openai", model: "m" });

const chooseAi = { kind: "navigate" as const, label: "Choose an AI", path: "/settings/ai", symbol: null };
// What the engine used to send. Still tolerated, so a chat saved before the rename reads correctly.
const oldAddKey = { kind: "navigate" as const, label: "Add an AI key", path: "/settings/accounts", symbol: null };

describe("the buttons under a reply", () => {
  const addKey = chooseAi;
  const openTcs = { kind: "navigate" as const, label: "Open TCS", path: "/stock/TCS", symbol: "TCS" };
  const answered = (mode: "ai" | "built_in") => {
    const proposals = [addKey, openTcs];
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: { ...reply("x"), mode, proposals } },
    ]);
    return state.messages[1] as AssistantMessage;
  };

  it("leaves out a second Choose an AI button when the built-in line already offers it", () => {
    expect(visibleProposals(answered("built_in"))).toEqual([openTcs]);
  });

  it("leaves out the old Add an AI key button just the same", () => {
    const message = { ...answered("built_in"), proposals: [oldAddKey, openTcs] };
    expect(visibleProposals(message)).toEqual([openTcs]);
  });

  it("shows every button when an AI model answered", () => {
    expect(visibleProposals(answered("ai"))).toEqual([addKey, openTcs]);
  });
});

describe("when a reply already talks about AI keys", () => {
  const addKey = chooseAi;
  const make = (text: string, mode: "ai" | "built_in", proposals: ChatReply["proposals"] = []) => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: { ...reply(text), mode, proposals } },
    ]);
    return state.messages[1] as AssistantMessage;
  };
  const NEED_AI = "To ask open-ended questions, set up an AI: open Settings, then AI assistants.";
  const OLD_NEED_AI = "To ask open-ended questions, add an AI key: open Settings, then Accounts and keys.";
  const REJECTED = "That AI service did not accept your key. Open Settings, then Accounts and keys, and check it.";

  it("recognises the engine's own key sentences", () => {
    expect(replyExplainsKeys(`Which stock?\n\n${NEED_AI}`)).toBe(true);
    expect(replyExplainsKeys(`Which stock?\n\n${OLD_NEED_AI}`)).toBe(true);
    expect(replyExplainsKeys(REJECTED)).toBe(true);
    expect(replyExplainsKeys("TCS passes both standards. Key ratios are below.")).toBe(false);
  });

  it("adds a note and a button of its own only when the reply says nothing about keys", () => {
    expect(keyHelp(make("Which stock?", "built_in"))).toBe("footer");
    expect(keyHelp(make("Which stock?", "ai"))).toBe("none");
  });

  it("adds no note when the reply already says to choose an AI, and keeps the engine's one button", () => {
    const message = make(`Which stock?\n\n${NEED_AI}`, "built_in", [addKey]);
    expect(keyHelp(message)).toBe("none");
    expect(visibleProposals(message)).toEqual([addKey]);
  });

  it("treats the old Add an AI key button as the engine's one button too", () => {
    const message = make(`Which stock?\n\n${OLD_NEED_AI}`, "built_in", [oldAddKey]);
    expect(keyHelp(message)).toBe("none");
    expect(visibleProposals(message)).toEqual([oldAddKey]);
  });

  const OWN_BUTTON: [string, string, string, string][] = [
    ["choosing an AI", NEED_AI, "Choose an AI", "/settings/ai"],
    ["the old wording", OLD_NEED_AI, "Choose an AI", "/settings/ai"],
    ["a refused key", REJECTED, "Check your AI keys", "/settings/accounts"],
  ];

  it.each(OWN_BUTTON)("offers one button of its own for a reply about %s", (_name, text, label, path) => {
    const message = make(text, "built_in");
    expect(keyHelp(message)).toBe("button");
    expect(keyButton(message)).toMatchObject({ kind: "navigate", label, path });
  });

  it("adds no note after a rejected key either, but makes sure there is one clear button", () => {
    const withButton = make(REJECTED, "built_in", [addKey]);
    expect(keyHelp(withButton)).toBe("none");
    expect(keyHelp(make(REJECTED, "built_in"))).toBe("button");
  });
});

describe("a message the engine refuses", () => {
  it("takes the refused message out of the conversation and keeps the engine's sentence", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1, refusal: "Your message is too long." },
    ]);
    expect(state).toMatchObject({ status: "failed", failure: "Your message is too long.", messages: [] });
  });

  it("keeps the question after any other failure, with no sentence of its own", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1 },
    ]);
    expect(state).toMatchObject({ status: "failed", failure: null });
    expect(state.messages).toHaveLength(1);
  });

  it("forgets the sentence when the person sends something new", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1, refusal: "Too long." },
      { type: "sent", content: "shorter", requestId: 2 },
    ]);
    expect(state).toMatchObject({ status: "thinking", failure: null });
  });
});

describe("the conversation", () => {
  it("adds what the person said and waits for the answer", () => {
    const state = run([{ type: "sent", content: "Is TCS halal?", requestId: 1 }]);
    expect(state.status).toBe("thinking");
    expect(state.messages).toMatchObject([{ role: "user", content: "Is TCS halal?" }]);
  });

  it("adds the answer for the request it is waiting on", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: reply("Hello") },
    ]);
    expect(state.status).toBe("idle");
    expect(state.messages.map((m) => [m.role, m.content])).toEqual([
      ["user", "hi"],
      ["assistant", "Hello"],
    ]);
    expect(state.messages[1]).toMatchObject({ mode: "ai", provider: "openai", steps: [], proposals: [] });
  });

  it("sends nothing while an answer is awaited, and nothing empty", () => {
    const waiting = run([{ type: "sent", content: "one", requestId: 1 }]);
    expect(chatReducer(waiting, { type: "sent", content: "two", requestId: 2 })).toBe(waiting);
    expect(chatReducer(initialChat, { type: "sent", content: "   ", requestId: 1 })).toBe(initialChat);
  });

  it("ignores an answer that arrives after New chat", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "cleared" },
      { type: "replied", requestId: 1, reply: reply("late") },
    ]);
    expect(state.messages).toEqual([]);
    expect(state.status).toBe("idle");
  });

  it("keeps the question after a failure so it can be tried again", () => {
    const failed = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "failed", requestId: 1 },
    ]);
    expect(failed.status).toBe("failed");
    expect(failed.messages).toHaveLength(1);
    const again = chatReducer(failed, { type: "retried", requestId: 2 });
    expect(again.status).toBe("thinking");
    expect(again.pending).toBe(2);
    expect(again.messages).toHaveLength(1);
  });

  it("does not retry when nothing failed", () => {
    expect(chatReducer(initialChat, { type: "retried", requestId: 1 })).toBe(initialChat);
  });

  it("ignores a failure for an old request", () => {
    const state = run([{ type: "sent", content: "hi", requestId: 2 }]);
    expect(chatReducer(state, { type: "failed", requestId: 1 })).toBe(state);
  });

  it("gives every message its own id", () => {
    const state = run([
      { type: "sent", content: "a", requestId: 1 },
      { type: "replied", requestId: 1, reply: reply("b") },
      { type: "sent", content: "c", requestId: 2 },
    ]);
    expect(new Set(state.messages.map((m) => m.id)).size).toBe(3);
  });
});

describe("saved chats", () => {
  const saved: SavedMessage[] = [
    { role: "user", content: "is TCS halal?" },
    { ...reply("Yes."), role: "assistant", content: "Yes.", savedNote: null },
  ];

  it("keeps the chat the first answer was saved into, and carries on with it", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "replied", requestId: 1, reply: { ...reply("Hello"), conversationId: "chat-1" } },
      { type: "sent", content: "more", requestId: 2 },
    ]);
    expect(state.chatId).toBe("chat-1");
  });

  it("starts with no chat, and forgets it on New chat", () => {
    const opened = run([{ type: "opened", chatId: "chat-1", messages: saved }]);
    expect(initialChat.chatId).toBeNull();
    expect(chatReducer(opened, { type: "cleared" })).toMatchObject({ chatId: null, messages: [] });
  });

  it("puts a saved chat in the thread, numbered after what came before so no key is reused", () => {
    const before = run([{ type: "sent", content: "old", requestId: 1 }]);
    const state = chatReducer(before, { type: "opened", chatId: "chat-9", messages: saved });
    expect(state).toMatchObject({ chatId: "chat-9", status: "idle", pending: null });
    expect(state.messages.map((m) => [m.id, m.role, m.content])).toEqual([
      [2, "user", "is TCS halal?"],
      [3, "assistant", "Yes."],
    ]);
  });

  it("drops an answer still awaited for the chat that was open before another was opened", () => {
    const state = run([
      { type: "sent", content: "hi", requestId: 1 },
      { type: "opened", chatId: "chat-9", messages: saved },
      { type: "replied", requestId: 1, reply: { ...reply("late"), conversationId: "chat-1" } },
    ]);
    expect(state.chatId).toBe("chat-9");
    expect(state.messages.map((m) => m.content)).toEqual(["is TCS halal?", "Yes."]);
  });

  it("lets go of a chat the engine says is gone, so the next question starts a new one", () => {
    const state = run([
      { type: "opened", chatId: "chat-9", messages: saved },
      { type: "sent", content: "more", requestId: 1 },
      { type: "failed", requestId: 1, refusal: "That chat no longer exists. Start a new chat.", chatGone: true },
    ]);
    expect(state).toMatchObject({ chatId: null, failure: "That chat no longer exists. Start a new chat." });
  });

  it("shows the note about a chat that could not be saved once, not under every answer", () => {
    const full = { ...reply("A"), conversationId: "c", savedNote: "This chat is full. Start a new chat." };
    const state = run([
      { type: "sent", content: "1", requestId: 1 },
      { type: "replied", requestId: 1, reply: full },
      { type: "sent", content: "2", requestId: 2 },
      { type: "replied", requestId: 2, reply: full },
      { type: "sent", content: "3", requestId: 3 },
      { type: "replied", requestId: 3, reply: full },
    ]);
    const notes = state.messages.flatMap((m) => (m.role === "assistant" ? [m.savedNote ?? null] : []));
    expect(notes).toEqual(["This chat is full. Start a new chat.", null, null]);
  });
});
