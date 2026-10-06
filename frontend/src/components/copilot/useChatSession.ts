import { useCallback, useMemo, useReducer, useRef, useState } from "react";
import { buildChatRequest, copilotApi, MAX_MESSAGE_CHARS, normaliseReply } from "../../lib/copilot";
import { type ChatAction, type ChatMessage, type ChatState, chatReducer, initialChat } from "./chatState";

export interface ChatSession {
  messages: ChatMessage[];
  thinking: boolean;
  failed: boolean;
  /** What the person has typed but not sent yet; kept so closing the drawer does not lose it. */
  draft: string;
  setDraft: (text: string) => void;
  send: (text: string) => boolean;
  retry: () => void;
  newChat: () => void;
}

type Apply = (action: ChatAction) => ChatState;

async function answer(messages: ChatMessage[], page: string, requestId: number, apply: Apply): Promise<void> {
  try {
    const raw = await copilotApi.chat(buildChatRequest(messages, page));
    apply({ type: "replied", requestId, reply: normaliseReply(raw) });
  } catch {
    apply({ type: "failed", requestId });
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
      void answer(next.messages, live.current.page, requestId, apply);
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

  const { messages, status } = state;
  const thinking = status === "thinking";
  const failed = status === "failed";
  return useMemo(
    () => ({ messages, thinking, failed, draft, setDraft, send, retry, newChat }),
    [messages, thinking, failed, draft, send, retry, newChat],
  );
}
