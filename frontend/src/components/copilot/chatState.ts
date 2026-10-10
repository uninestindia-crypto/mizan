// The conversation, as a plain reducer so its rules can be tested without a screen.

import type { ChatProposal, ChatReply } from "../../lib/copilot";

export interface UserMessage {
  id: number;
  role: "user";
  content: string;
}

export interface AssistantMessage extends Omit<ChatReply, "reply"> {
  id: number;
  role: "assistant";
  content: string;
  /** The engine's own sentence when this answer could not be saved. Shown once, quietly; never as an error. */
  savedNote?: string | null;
}

export type ChatMessage = UserMessage | AssistantMessage;

/** A message of a chat that was saved earlier, before the thread has numbered it. */
export type SavedMessage = Omit<UserMessage, "id"> | Omit<AssistantMessage, "id">;

/** What the engine answered, and the saved chat it went into (absent when the chat was not saved). */
export type ReplyIn = ChatReply & { conversationId?: string | null; savedNote?: string | null };

export interface ChatState {
  messages: ChatMessage[];
  status: "idle" | "thinking" | "failed";
  /** The request whose answer is awaited. An answer for any other request is out of date and is ignored. */
  pending: number | null;
  /** The engine's own sentence when it refused to read a message. Null after any other kind of failure. */
  failure: string | null;
  /** The saved chat this conversation belongs to. Null until the first answer is saved, and again after New chat. */
  chatId: string | null;
  nextId: number;
}

export type ChatAction =
  | { type: "sent"; content: string; requestId: number }
  | { type: "retried"; requestId: number }
  | { type: "replied"; requestId: number; reply: ReplyIn }
  | { type: "failed"; requestId: number; refusal?: string; chatGone?: boolean }
  | { type: "opened"; chatId: string; messages: SavedMessage[] }
  | { type: "cleared" };

/** Where a person chooses which AI answers. The old button pointed at the keys page and may still be sent. */
export const AI_PATH = "/settings/ai";
export const ACCOUNTS_PATH = "/settings/accounts";
export const CHOOSE_AI = "Choose an AI";

const KEY_WORDS = /\bAI keys?\b|\byour key\b|\bset up an AI\b|\bAI assistants\b/i;
const CHOOSE_WORDS = /add an AI key|set up an AI|AI assistants/i;
const isKeyPath = (proposal: ChatProposal) => proposal.path === AI_PATH || proposal.path === ACCOUNTS_PATH;

/** Whether the reply's own words already tell the person what to do about an AI key. */
export function replyExplainsKeys(text: string): boolean {
  return KEY_WORDS.test(text);
}

export type KeyHelp = "footer" | "button" | "none";

/**
 * What to add under a built-in reply about AI keys. The engine often says it in the reply itself, and after a rejected
 * key it says so more precisely; then a note of ours would only say it again, or say something different.
 * "footer" is our note with its button, "button" is one lone button, "none" adds nothing.
 */
export function keyHelp(message: AssistantMessage): KeyHelp {
  if (message.mode !== "built_in") return "none";
  if (!replyExplainsKeys(message.content)) return "footer";
  return message.proposals.some(isKeyPath) ? "none" : "button";
}

/** The one button for a reply that talks about AI but offered none: to choose an AI, or to check a rejected key. */
export function keyButton(message: AssistantMessage): ChatProposal {
  if (CHOOSE_WORDS.test(message.content)) return { kind: "navigate", label: CHOOSE_AI, path: AI_PATH, symbol: null };
  return { kind: "navigate", label: "Check your AI keys", path: ACCOUNTS_PATH, symbol: null };
}

/** The buttons under a reply. When our own note carries the "Choose an AI" button, a second would repeat it. */
export function visibleProposals(message: AssistantMessage): ChatReply["proposals"] {
  if (keyHelp(message) !== "footer") return message.proposals;
  return message.proposals.filter((p) => !isKeyPath(p));
}

export const initialChat: ChatState = {
  messages: [],
  status: "idle",
  pending: null,
  failure: null,
  chatId: null,
  nextId: 1,
};

function onSent(state: ChatState, content: string, requestId: number): ChatState {
  if (state.status === "thinking" || !content.trim()) return state;
  const message: UserMessage = { id: state.nextId, role: "user", content };
  const messages = [...state.messages, message];
  return { ...state, messages, status: "thinking", pending: requestId, failure: null, nextId: state.nextId + 1 };
}

function onRetried(state: ChatState, requestId: number): ChatState {
  const last = state.messages[state.messages.length - 1];
  if (state.status !== "failed" || last?.role !== "user") return state;
  return { ...state, status: "thinking", pending: requestId, failure: null };
}

/** A full chat says so with every answer. Once is enough: a note the thread already carries is not repeated. */
function newSavedNote(state: ChatState, note: string | null | undefined): string | null {
  const shown = state.messages.map((m) => (m.role === "assistant" ? m.savedNote : null)).filter(Boolean);
  return note && note !== shown[shown.length - 1] ? note : null;
}

function onReplied(state: ChatState, requestId: number, answer: ReplyIn): ChatState {
  if (requestId !== state.pending) return state;
  const { reply, conversationId, savedNote, ...rest } = answer;
  const note = newSavedNote(state, savedNote);
  const message: AssistantMessage = { ...rest, id: state.nextId, role: "assistant", content: reply, savedNote: note };
  const messages = [...state.messages, message];
  const chatId = conversationId ?? state.chatId;
  return { messages, status: "idle", pending: null, failure: null, chatId, nextId: state.nextId + 1 };
}

function onFailed(state: ChatState, requestId: number, refusal?: string, chatGone = false): ChatState {
  if (requestId !== state.pending) return state;
  const chatId = chatGone ? null : state.chatId;
  if (!refusal) return { ...state, status: "failed", pending: null, failure: null, chatId };
  // A message the engine cannot read would be refused again with every later question, so it leaves the conversation.
  const last = state.messages[state.messages.length - 1];
  const messages = last?.role === "user" ? state.messages.slice(0, -1) : state.messages;
  return { ...state, messages, status: "failed", pending: null, failure: refusal, chatId };
}

/** A saved chat takes the thread's place. An answer still awaited for the chat that was open is out of date now. */
function onOpened(state: ChatState, chatId: string, saved: SavedMessage[]): ChatState {
  const number = (message: SavedMessage, index: number) => ({ ...message, id: state.nextId + index }) as ChatMessage;
  const messages = saved.map(number);
  return { messages, status: "idle", pending: null, failure: null, chatId, nextId: state.nextId + saved.length };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "sent":
      return onSent(state, action.content, action.requestId);
    case "retried":
      return onRetried(state, action.requestId);
    case "replied":
      return onReplied(state, action.requestId, action.reply);
    case "failed":
      return onFailed(state, action.requestId, action.refusal, action.chatGone);
    case "opened":
      return onOpened(state, action.chatId, action.messages);
    case "cleared":
      return { ...initialChat, nextId: state.nextId };
  }
}
