import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import {
  answeredBy,
  CHAT_STORAGE_KEY,
  forgetChat,
  isChatGone,
  listPath,
  messageCountLabel,
  readChatDetail,
  readSavedReply,
  rememberChat,
  rememberedChat,
  whenLabel,
} from "./copilotHistory";

const NAMED: [string, string][] = [
  ["cli:claude", "Answered by Claude Code"],
  ["cli:codex", "Answered by Codex"],
  ["cli:gemini", "Answered by Gemini"],
  ["anthropic", "Answered by Claude (Anthropic)"],
  ["openai", "Answered by OpenAI"],
  ["gemini", "Answered by Google Gemini"],
  ["groq", "Answered by Groq"],
  ["deepseek", "Answered by DeepSeek"],
  ["mistral", "Answered by Mistral"],
  ["openrouter", "Answered by OpenRouter"],
];
const UNNAMED: [string | null | undefined][] = [
  ["cli:unknown"],
  ["acme-ai"],
  ["constructor"],
  ["__proto__"],
  [""],
  [null],
  [undefined],
];

describe("which AI answered", () => {
  it.each(NAMED)("names %s", (provider, line) => {
    expect(answeredBy(provider)).toBe(line);
  });

  it.each(UNNAMED)("says nothing for %s", (provider) => {
    expect(answeredBy(provider)).toBeNull();
  });
});

// Wednesday 7 Oct 2026, 3:30 pm, in the computer's own time.
const NOW = new Date(2026, 9, 7, 15, 30);
const WHEN: [Date, string][] = [
  [new Date(2026, 9, 7, 14, 15), "Today 2:15 pm"],
  [new Date(2026, 9, 7, 0, 5), "Today 12:05 am"],
  [new Date(2026, 9, 7, 12, 0), "Today 12:00 pm"],
  [new Date(2026, 9, 6, 23, 59), "Yesterday"],
  [new Date(2026, 9, 5, 9, 0), "5 Oct"],
  [new Date(2026, 0, 1, 9, 0), "1 Jan"],
  [new Date(2025, 8, 12, 9, 0), "12 Sep 2025"],
];
const COUNTS: [number, string][] = [
  [0, "0 messages"],
  [1, "1 message"],
  [2, "2 messages"],
];

describe("when a chat was last used", () => {
  const now = NOW;
  it.each(WHEN)("reads %s as %s", (when, label) => {
    expect(whenLabel(when.toISOString(), now)).toBe(label);
  });

  it("reads the engine's own time stamp, with its fraction of a second and its zone", () => {
    expect(whenLabel("2026-10-07T10:18:40.123456+00:00", new Date("2026-10-07T12:00:00+00:00"))).toMatch(/^Today /);
  });

  it("says nothing for a time it cannot read", () => {
    expect(whenLabel("", now)).toBe("");
    expect(whenLabel("not a date", now)).toBe("");
  });

  it.each(COUNTS)("counts %i as %s", (count, label) => {
    expect(messageCountLabel(count)).toBe(label);
  });
});

const LIST_PATHS: [string, string][] = [
  ["", "/api/v2/copilot/conversations"],
  ["   ", "/api/v2/copilot/conversations"],
  ["halal", "/api/v2/copilot/conversations?q=halal"],
  [" TCS & INFY ", "/api/v2/copilot/conversations?q=TCS%20%26%20INFY"],
];

describe("the address of the list", () => {
  it.each(LIST_PATHS)("asks for %j at %s", (query, path) => {
    expect(listPath(query)).toBe(path);
  });
});

const GONE_OR_NOT: [unknown, boolean][] = [
  [new ApiError("NOT_FOUND", "gone", 404), true],
  [new ApiError("HTTP_404", "gone", 404), false],
  [new ApiError("NOT_FOUND", "gone", 500), false],
  [new Error("gone"), false],
];

describe("reading what the engine sends", () => {
  it("reads a reply with the chat it was saved into", () => {
    const sent = { reply: "Hi", mode: "ai", provider: "cli:claude", conversation_id: "c1", saved: true };
    const reply = readSavedReply(sent);
    expect(reply).toMatchObject({ reply: "Hi", provider: "cli:claude", conversationId: "c1", savedNote: null });
  });

  it("keeps the engine's sentence only when the chat could not be saved", () => {
    const note = "This chat is full. Start a new chat.";
    expect(readSavedReply({ reply: "Hi", saved: false, saved_note: note }).savedNote).toBe(note);
    expect(readSavedReply({ reply: "Hi", saved: true, saved_note: note }).savedNote).toBeNull();
  });

  it("reads an old-style reply with nothing about saving", () => {
    expect(readSavedReply({ reply: "Hi" })).toMatchObject({ conversationId: null, savedNote: null });
    expect(readSavedReply(null)).toMatchObject({ conversationId: null, savedNote: null });
  });

  it("reads a chat's messages, leaving out anything that is not a message", () => {
    const detail = readChatDetail({
      id: "c1",
      title: " Halal picks ",
      messages: [
        { role: "user", content: "hi", meta: {} },
        { role: "assistant", content: "hello", meta: { mode: "ai" } },
        { role: "system", content: "x" },
        "junk",
      ],
    });
    expect(detail.title).toBe("Halal picks");
    expect(detail.turns).toEqual([
      { role: "user", content: "hi", meta: {} },
      { role: "assistant", content: "hello", meta: { mode: "ai" } },
    ]);
  });

  it("gives a chat with no name the name the engine gives a new chat", () => {
    expect(readChatDetail({ id: "c1", title: "  ", messages: [] }).title).toBe("New chat");
  });

  it.each(GONE_OR_NOT)("knows whether %o means the chat is gone", (error, gone) => {
    expect(isChatGone(error)).toBe(gone);
  });
});

describe("remembering the open chat", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("keeps the id between visits and lets it go", () => {
    expect(rememberedChat()).toBeNull();
    rememberChat("c1");
    expect(window.localStorage.getItem(CHAT_STORAGE_KEY)).toBe("c1");
    expect(rememberedChat()).toBe("c1");
    forgetChat();
    expect(rememberedChat()).toBeNull();
  });

  it("carries on quietly when storage is blocked", () => {
    const blocked = () => {
      throw new DOMException("blocked", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(blocked);
    expect(() => rememberChat("c1")).not.toThrow();
    expect(rememberedChat()).toBeNull();
    expect(() => forgetChat()).not.toThrow();
  });
});
