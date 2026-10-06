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
  nextId: number;
}

export type ChatAction =
  | { type: "sent"; content: string; requestId: number }
  | { type: "retried"; requestId: number }
  | { type: "replied"; requestId: number; reply: ChatReply }
  | { type: "failed"; requestId: number }
  | { type: "cleared" };

export const ACCOUNTS_PATH = "/settings/accounts";

/**
 * The buttons to show under a reply. A built-in answer already carries its own "Add an AI key" line, so a second
 * button for the same place would only repeat it.
 */
export function visibleProposals(message: AssistantMessage): ChatReply["proposals"] {
  if (message.mode !== "built_in") return message.proposals;
  return message.proposals.filter((p) => p.path !== ACCOUNTS_PATH);
}

export const initialChat: ChatState = { messages: [], status: "idle", pending: null, nextId: 1 };

function onSent(state: ChatState, content: string, requestId: number): ChatState {
  if (state.status === "thinking" || !content.trim()) return state;
  const message: UserMessage = { id: state.nextId, role: "user", content };
  const messages = [...state.messages, message];
  return { messages, status: "thinking", pending: requestId, nextId: state.nextId + 1 };
}

function onRetried(state: ChatState, requestId: number): ChatState {
  const last = state.messages[state.messages.length - 1];
  if (state.status !== "failed" || last?.role !== "user") return state;
  return { ...state, status: "thinking", pending: requestId };
}

function onReplied(state: ChatState, requestId: number, answer: ChatReply): ChatState {
  if (requestId !== state.pending) return state;
  const { reply, ...rest } = answer;
  const message: AssistantMessage = { ...rest, id: state.nextId, role: "assistant", content: reply };
  const messages = [...state.messages, message];
  return { messages, status: "idle", pending: null, nextId: state.nextId + 1 };
}

function onFailed(state: ChatState, requestId: number): ChatState {
  return requestId === state.pending ? { ...state, status: "failed", pending: null } : state;
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
      return onFailed(state, action.requestId);
    case "cleared":
      return { ...initialChat, nextId: state.nextId };
  }
}
