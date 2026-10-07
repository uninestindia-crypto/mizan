import { useCallback, useMemo, useReducer, useRef, useState } from "react";
import {
  buildChatRequest,
  copilotApi,
  MAX_MESSAGE_CHARS,
  normaliseReply,
  refusalSentence,
} from "../../lib/copilot";
import { type ChatAction, type ChatMessage, type ChatState, chatReducer, initialChat } from "./chatState";

export interface ChatSession {
  messages: ChatMessage[];
  thinking: boolean;
  failed: boolean;
  /** The engine's own sentence when it refused to read the last message; null after any other failure. */
  failure: string | null;
  /** What the person has typed but not sent yet; kept so closing the drawer does not lose it. */
  draft: string;
  setDraft: (text: string) => void;
  send: (text: string) => boolean;
  retry: () => void;
  newChat: () => void;
}

type Apply = (action: ChatAction) => ChatState;

interface Question {
  messages: ChatMessage[];
  page: string;
  requestId: number;
}

/** Asks the engine. A message it refuses goes back into the box, so the person can change it rather than retype it. */
async function answer(question: Question, apply: Apply, restore: (text: string) => void): Promise<void> {
  const { messages, page, requestId } = question;
  try {
    const raw = await copilotApi.chat(buildChatRequest(messages, page));
    apply({ type: "replied", requestId, reply: normaliseReply(raw) });
  } catch (error) {
    const refusal = refusalSentence(error) ?? undefined;
    const last = messages[messages.length - 1];
    if (refusal && last?.role === "user") restore(last.content);
    apply({ type: "failed", requestId, refusal });
  }
}

/** The conversation with the Copilot: what was said, what is awaited, and what the person is typing. */
export function useChatSession(page: string): ChatSession {
  const [state, dispatch] = useReducer(chatReducer, initialChat);
  const [draft, setDraft] = useState("");
  const live = useRef({ state, page, seq: 0 });
  live.current.page = page;

  // Reduce here as well as in React so a second click in the same instant sees the first one's effect.
  const apply = useCallback<Apply>((action) => {
    live.current.state = chatReducer(live.current.state, action);
    dispatch(action);
    return live.current.state;
  }, []);

  const begin = useCallback(
    (make: (requestId: number) => ChatAction): boolean => {
      const before = live.current.state;
      const requestId = ++live.current.seq;
      const next = apply(make(requestId));
      if (next === before) return false;
      const question = { messages: next.messages, page: live.current.page, requestId };
      void answer(question, apply, (text) => setDraft((current) => current || text));
      return true;
    },
    [apply],
  );

  const send = useCallback(
    (text: string) => {
      const content = text.trim().slice(0, MAX_MESSAGE_CHARS);
      return begin((requestId) => ({ type: "sent", content, requestId }));
    },
    [begin],
  );
  const retry = useCallback(() => void begin((requestId) => ({ type: "retried", requestId })), [begin]);
  const newChat = useCallback(() => void apply({ type: "cleared" }), [apply]);

  const { messages, status, failure } = state;
  const thinking = status === "thinking";
  const failed = status === "failed";
  return useMemo(
    () => ({ messages, thinking, failed, failure, draft, setDraft, send, retry, newChat }),
    [messages, thinking, failed, failure, draft, send, retry, newChat],
  );
}
