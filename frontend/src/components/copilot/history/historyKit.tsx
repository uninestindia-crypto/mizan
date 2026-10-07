// A fake engine for the saved chats, and the small helpers the history tests share.

import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api, ApiError } from "../../../lib/api";
import { reply } from "../chatTestKit";
import { serveApi } from "../testHarness";

export const BASE = "/api/v2/copilot/conversations";
export const CHAT = "/api/v2/copilot/chat";
export const CHAT_GONE = "That chat no longer exists. Start a new chat.";

export interface FakeMessage {
  role: "user" | "assistant";
  content: string;
  meta?: Record<string, unknown>;
}

export interface FakeChat {
  id: string;
  title: string;
  updated_at: string;
  messages: FakeMessage[];
}

export interface EngineOptions {
  /** Extra fields for every reply, such as who answered or a note about saving. */
  replyWith?: Record<string, unknown>;
  /** Holds every question until this settles, so a test can open another chat while one is awaited. */
  gate?: Promise<unknown>;
  /** Holds the fetch of a saved chat's messages until this settles. */
  detailGate?: Promise<unknown>;
}

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function summary(chat: FakeChat) {
  const last = chat.messages[chat.messages.length - 1];
  const { messages, ...rest } = chat;
  const count = messages.length;
  return { ...rest, agent_id: null, created_at: chat.updated_at, message_count: count, preview: last?.content ?? "" };
}

function matches(chat: FakeChat, query: string): boolean {
  const words = query.toLowerCase();
  const said = [chat.title, ...chat.messages.map((message) => message.content)];
  return said.some((text) => text.toLowerCase().includes(words));
}

export class FakeEngine {
  chats: FakeChat[];
  private count = 0;

  constructor(seed: FakeChat[], private readonly options: EngineOptions = {}) {
    this.chats = structuredClone(seed);
    serveApi((method, path, body) => this.handle({ method, path, body }));
  }

  private find(id: string | null): FakeChat {
    const found = this.chats.find((chat) => chat.id === id);
    if (!found) throw new ApiError("NOT_FOUND", CHAT_GONE, 404);
    return found;
  }

  private list(query: string) {
    const newest = [...this.chats].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return { conversations: newest.filter((chat) => matches(chat, query.trim())).map(summary) };
  }

  private rename(id: string, body: unknown) {
    const title = String((body as { title?: string }).title ?? "").trim();
    if (!title) throw new ApiError("BAD_REQUEST", "Give the chat a name.", 400);
    this.find(id).title = title;
    return { id, title };
  }

  private async detail(id: string | null) {
    await this.options.detailGate;
    return { ...this.find(id), agent_id: null, created_at: "" };
  }

  private async ask(body: unknown) {
    await this.options.gate;
    const { messages, conversation_id: wanted } = body as { messages: FakeMessage[]; conversation_id: string };
    const question = messages[messages.length - 1]?.content ?? "";
    const chat = wanted === "new" ? this.start(question) : this.find(wanted);
    const answer = { ...reply({ reply: `Answer to: ${question}` }), ...this.options.replyWith };
    const meta = { mode: answer.mode, provider: answer.provider, model: answer.model, steps: [], proposals: [] };
    chat.messages.push({ role: "user", content: question }, { role: "assistant", content: answer.reply, meta });
    chat.updated_at = new Date().toISOString();
    return { ...answer, conversation_id: chat.id, saved: true };
  }

  private start(question: string): FakeChat {
    const chat = { id: `made-${++this.count}`, title: question, updated_at: "", messages: [] };
    this.chats.push(chat);
    return chat;
  }

  private handle({ method, path, body }: Call): unknown {
    const url = new URL(path, "http://engine");
    const id = url.pathname === BASE ? null : decodeURIComponent(url.pathname.slice(BASE.length + 1));
    if (url.pathname === CHAT) return this.ask(body);
    if (method === "GET" && id === null) return this.list(url.searchParams.get("q") ?? "");
    if (method === "GET") return this.detail(id);
    if (method === "PUT") return this.rename(this.find(id).id, body);
    if (id === null) return { cleared: this.chats.splice(0).length };
    this.chats = this.chats.filter((chat) => chat.id !== this.find(id).id);
    return { deleted: true };
  }
}

// ------------------------------------------------------------------------------------------------- the chats

const ASSISTANT_META = {
  mode: "ai",
  provider: "openai",
  model: "gpt-x",
  error: null,
  steps: [{ label: "Halal screening", summary: "AAA: both standards checked", ok: true }],
  proposals: [{ kind: "navigate", label: "Open AAA", path: "/stock/AAA", symbol: "AAA" }],
};

const PLAIN_META = { ...ASSISTANT_META, steps: [], proposals: [] };

export const SEED: FakeChat[] = [
  {
    id: "chat-a",
    title: "is AAA halal?",
    updated_at: "2026-10-05T09:15:00",
    messages: [
      { role: "user", content: "is AAA halal?" },
      { role: "assistant", content: "AAA passes both standards.", meta: ASSISTANT_META },
    ],
  },
  {
    id: "chat-b",
    title: "show my watchlist",
    updated_at: "2026-10-06T14:15:00",
    messages: [
      { role: "user", content: "show my watchlist" },
      { role: "assistant", content: "You are watching 3 stocks.", meta: PLAIN_META },
    ],
  },
  {
    id: "chat-c",
    title: "how is INFY doing?",
    updated_at: "2026-10-04T08:00:00",
    messages: [{ role: "user", content: "how is INFY doing?" }],
  },
];

// ----------------------------------------------------------------------------------------------- the screen

/** A promise the test settles by hand, to hold the engine's answer back. */
export function holdBack() {
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { gate, release };
}

/** The calls made to the engine with this method and a path that starts this way, oldest first. */
export const callsStarting = (method: string, pathStart: string) =>
  vi.mocked(api).mock.calls.filter(([path, how = "GET"]) => how === method && String(path).startsWith(pathStart));

export const historyButton = () => screen.getByRole("button", { name: "History" });
export const searchBox = () => screen.getByRole("searchbox", { name: "Search your chats" });
export const panel = () => screen.getByRole("region", { name: "Your chats" });

export async function openHistory() {
  fireEvent.click(historyButton());
  return screen.findByRole("region", { name: "Your chats" });
}

/** The titles of the chats listed, top to bottom. */
export const listedTitles = () =>
  screen.getAllByRole("button", { name: /^Rename chat: / }).map((b) => (b.getAttribute("aria-label") ?? "").slice(13));

export const chatButton = (title: string) =>
  screen.getByRole("button", { name: new RegExp(`^${title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`) });

export function search(text: string) {
  fireEvent.change(searchBox(), { target: { value: text } });
}
