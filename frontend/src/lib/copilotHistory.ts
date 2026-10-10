// Saved Copilot chats: what the engine sends for them, the calls that read and change them, and the small plain-words
// helpers the history screen shares. Chats are kept on this computer by the engine; nothing here leaves it.

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import { buildChatRequest, type ChatReply, type ChatTurn, normaliseReply } from "./copilot";

// ------------------------------------------------------------------------------------------------------ shapes

export interface ChatSummary {
  id: string;
  title: string;
  updatedAt: string;
  messageCount: number;
  preview: string;
}

/** One message as the engine kept it. An assistant message also keeps what the Copilot looked at and offered. */
export interface SavedTurn {
  role: "user" | "assistant";
  content: string;
  meta: Record<string, unknown>;
}

export interface ChatDetail {
  id: string;
  title: string;
  turns: SavedTurn[];
}

/** A reply as the screen uses it: the answer, plus the chat it was saved into and any word about saving. */
export interface SavedReply extends ChatReply {
  conversationId: string | null;
  savedNote: string | null;
}

// ----------------------------------------------------------------------------------------------- reading replies

const text = (value: unknown): string => (typeof value === "string" ? value : "");
const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};

function cleanSummary(raw: unknown): ChatSummary | null {
  const found = record(raw);
  const id = text(found.id);
  if (!id) return null;
  const count = typeof found.message_count === "number" ? found.message_count : 0;
  return {
    id,
    title: text(found.title).trim() || "New chat",
    updatedAt: text(found.updated_at),
    messageCount: count,
    preview: text(found.preview).trim(),
  };
}

function cleanTurn(raw: unknown): SavedTurn | null {
  const found = record(raw);
  const role = found.role === "user" || found.role === "assistant" ? found.role : null;
  return role ? { role, content: text(found.content), meta: record(found.meta) } : null;
}

/** Whatever the engine sent for a chat's detail, as turns the screen can show without checking every field. */
export function readChatDetail(raw: unknown): ChatDetail {
  const found = record(raw);
  const turns = Array.isArray(found.messages) ? found.messages : [];
  return {
    id: text(found.id),
    title: text(found.title).trim() || "New chat",
    turns: turns.map(cleanTurn).filter((turn): turn is SavedTurn => turn !== null),
  };
}

/** The Copilot's reply, with the chat it was saved into and the engine's sentence when it could not be saved. */
export function readSavedReply(raw: unknown): SavedReply {
  const found = record(raw);
  const note = text(found.saved_note).trim();
  return {
    ...normaliseReply(found as Partial<ChatReply>),
    conversationId: text(found.conversation_id) || null,
    savedNote: found.saved === false && note ? note : null,
  };
}

// --------------------------------------------------------------------------------------------------- engine calls

const CHATS = "/api/v2/copilot/conversations";
const chatPath = (id: string) => `${CHATS}/${encodeURIComponent(id)}`;

/** The list address, with a search only when there is something to look for. */
export function listPath(query: string): string {
  const words = query.trim();
  return words ? `${CHATS}?q=${encodeURIComponent(words)}` : CHATS;
}

async function listChats(query: string): Promise<ChatSummary[]> {
  const data = record(await api<unknown>(listPath(query)));
  const found = Array.isArray(data.conversations) ? data.conversations : [];
  return found.map(cleanSummary).filter((chat): chat is ChatSummary => chat !== null);
}

export const historyApi = {
  list: listChats,
  get: async (id: string): Promise<ChatDetail> => readChatDetail(await api<unknown>(chatPath(id))),
  rename: (id: string, title: string) => api<unknown>(chatPath(id), "PUT", { title }),
  remove: (id: string) => api<unknown>(chatPath(id), "DELETE"),
  clear: () => api<unknown>(CHATS, "DELETE"),
};

/** Asks the Copilot, and saves the question and the answer in the chat. With no chat yet, a new one is started. */
export async function askInChat(turns: readonly ChatTurn[], page: string | null, chatId: string | null) {
  const body = { ...buildChatRequest(turns, page), conversation_id: chatId ?? "new" };
  return readSavedReply(await api<unknown>("/api/v2/copilot/chat", "POST", body));
}

/** Whether the engine said the chat is gone, for example deleted from another window. */
export function isChatGone(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && error.code === "NOT_FOUND";
}

export const chatListKey = ["copilot", "chats"] as const;

/** The saved chats, newest first. A search keeps the old list on screen until the new one arrives. */
export function useChatList(query: string) {
  return useQuery({
    queryKey: [...chatListKey, query],
    queryFn: () => listChats(query),
    placeholderData: keepPreviousData,
    staleTime: 0,
  });
}

// ------------------------------------------------------------------------------------------------ plain wording

const ANSWERED_BY: Record<string, string> = {
  "cli:antigravity": "Antigravity",
  "cli:claude": "Claude Code",
  "cli:codex": "Codex",
  anthropic: "Claude (Anthropic)",
  openai: "OpenAI",
  gemini: "Google Gemini",
  groq: "Groq",
  deepseek: "DeepSeek",
  mistral: "Mistral",
  openrouter: "OpenRouter",
};

/** "Answered by Claude Code" and the like, or null for an AI the screen cannot name. Never a model's own id. */
export function answeredBy(provider: string | null | undefined): string | null {
  const name = provider && Object.hasOwn(ANSWERED_BY, provider) ? ANSWERED_BY[provider] : null;
  return name ? `Answered by ${name}` : null;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function clock(when: Date): string {
  const hours = when.getHours() % 12 || 12;
  const minutes = String(when.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes} ${when.getHours() < 12 ? "am" : "pm"}`;
}

const dayStart = (when: Date) => new Date(when.getFullYear(), when.getMonth(), when.getDate());
const DAY_MS = 24 * 60 * 60 * 1000;

/** "Today 2:15 pm", "Yesterday", "12 Sep" (with the year once it is not this year's). Empty when it cannot be read. */
export function whenLabel(iso: string, now: Date = new Date()): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  const days = Math.round((dayStart(now).getTime() - dayStart(when).getTime()) / DAY_MS);
  if (days === 0) return `Today ${clock(when)}`;
  if (days === 1) return "Yesterday";
  const day = `${when.getDate()} ${MONTHS[when.getMonth()]}`;
  return when.getFullYear() === now.getFullYear() ? day : `${day} ${when.getFullYear()}`;
}

export const messageCountLabel = (count: number): string => `${count} ${count === 1 ? "message" : "messages"}`;

// ------------------------------------------------------------------------------------- the chat to reopen later

export const CHAT_STORAGE_KEY = "quantos.copilot.chat";

/** The chat that was open last time, or null. Storage can be blocked, and then nothing is remembered. */
export function rememberedChat(): string | null {
  try {
    return window.localStorage.getItem(CHAT_STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

export function rememberChat(id: string): void {
  try {
    window.localStorage.setItem(CHAT_STORAGE_KEY, id);
  } catch {
    // Blocked storage only means the chat is not reopened next time; the chat itself is saved by the engine.
  }
}

export function forgetChat(): void {
  try {
    window.localStorage.removeItem(CHAT_STORAGE_KEY);
  } catch {
    // Nothing was remembered, or storage is blocked: either way there is nothing to forget.
  }
}
