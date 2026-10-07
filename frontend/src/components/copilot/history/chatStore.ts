import { type RefObject, useCallback, useReducer, useRef } from "react";
import { type ChatAction, type ChatState, chatReducer, initialChat } from "../chatState";

export type Apply = (action: ChatAction) => ChatState;

interface Live {
  state: ChatState;
  page: string;
  /** Counts the questions asked, so each answer can be matched to the question it belongs to. */
  seq: number;
  /** Counts the times a saved chat was asked for. Anything else the person does makes an older request out of date. */
  opening: number;
}

export interface ChatStore {
  state: ChatState;
  live: RefObject<Live>;
  apply: Apply;
}

// Asking a new question, retrying and starting over each mean any saved chat still being fetched is no longer wanted.
const OUTDATES_OPENING = new Set<ChatAction["type"]>(["sent", "retried", "cleared"]);

/** The conversation's state, kept in step with React so a second click in the same instant sees the first's effect. */
export function useChatStore(page: string): ChatStore {
  const [state, dispatch] = useReducer(chatReducer, initialChat);
  const live = useRef<Live>({ state, page, seq: 0, opening: 0 });
  live.current.page = page;

  const apply = useCallback<Apply>((action) => {
    if (OUTDATES_OPENING.has(action.type)) live.current.opening += 1;
    live.current.state = chatReducer(live.current.state, action);
    dispatch(action);
    return live.current.state;
  }, []);

  return { state, live, apply };
}
