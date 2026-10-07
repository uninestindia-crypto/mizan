// The conversation, as a plain reducer so its rules can be tested without a screen.

import type { ChatReply } from "../../lib/copilot";

export interface UserMessage {
  id: number;
  role: "user";
  content: string;
}

export interface AssistantMessage extends Omit<ChatReply, "reply"> {
  id: number;
  role: "assistant";
  content: string;
}

export type ChatMessage = UserMessage | AssistantMessage;

export interface ChatState {
  messages: ChatMessage[];
  status: "idle" | "thinking" | "failed";
  /** The request whose answer is awaited. An answer for any other request is out of date and is ignored. */
  pending: number | null;
  /** The engine's own sentence when it refused to read a message. Null after any other kind of failure. */
  failure: string | null;
  nextId: number;
}

export type ChatAction =
  | { type: "sent"; content: string; requestId: number }
  | { type: "retried"; requestId: number }
  | { type: "replied"; requestId: number; reply: ChatReply }
  | { type: "failed"; requestId: number; refusal?: string }
  | { type: "cleared" };

export const ACCOUNTS_PATH = "/settings/accounts";

const KEY_WORDS = /\bAI keys?\b|\byour key\b/i;

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
  return message.proposals.some((p) => p.path === ACCOUNTS_PATH) ? "none" : "button";
}

/** The buttons under a reply. When our own note carries the "Add an AI key" button, a second would repeat it. */
export function visibleProposals(message: AssistantMessage): ChatReply["proposals"] {
  if (keyHelp(message) !== "footer") return message.proposals;
  return message.proposals.filter((p) => p.path !== ACCOUNTS_PATH);
}

export const initialChat: ChatState = { messages: [], status: "idle", pending: null, failure: null, nextId: 1 };

function onSent(state: ChatState, content: string, requestId: number): ChatState {
  if (state.status === "thinking" || !content.trim()) return state;
  const message: UserMessage = { id: state.nextId, role: "user", content };
  const messages = [...state.messages, message];
  return { messages, status: "thinking", pending: requestId, failure: null, nextId: state.nextId + 1 };
}

function onRetried(state: ChatState, requestId: number): ChatState {
  const last = state.messages[state.messages.length - 1];
  if (state.status !== "failed" || last?.role !== "user") return state;
  return { ...state, status: "thinking", pending: requestId, failure: null };
}

function onReplied(state: ChatState, requestId: number, answer: ChatReply): ChatState {
  if (requestId !== state.pending) return state;
  const { reply, ...rest } = answer;
  const message: AssistantMessage = { ...rest, id: state.nextId, role: "assistant", content: reply };
  const messages = [...state.messages, message];
  return { messages, status: "idle", pending: null, failure: null, nextId: state.nextId + 1 };
}

function onFailed(state: ChatState, requestId: number, refusal: string | undefined): ChatState {
  if (requestId !== state.pending) return state;
  if (!refusal) return { ...state, status: "failed", pending: null, failure: null };
  // A message the engine cannot read would be refused again with every later question, so it leaves the conversation.
  const last = state.messages[state.messages.length - 1];
  const messages = last?.role === "user" ? state.messages.slice(0, -1) : state.messages;
  return { ...state, messages, status: "failed", pending: null, failure: refusal };
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
      return onFailed(state, action.requestId, action.refusal);
    case "cleared":
      return { ...initialChat, nextId: state.nextId };
  }
}
