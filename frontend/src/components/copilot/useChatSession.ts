import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";
import type { AgentView } from "../../lib/agentRun";
import { type AnswerPrefs, NO_PREFS } from "../../lib/answerPrefs";
import { MAX_MESSAGE_CHARS, refusalSentence } from "../../lib/copilot";
import { askInChat, chatListKey, forgetChat, isChatGone } from "../../lib/copilotHistory";
import type { ChatAction, ChatMessage } from "./chatState";
import { type Apply, type ChatStore, useChatStore } from "./history/chatStore";
import { type OpenResult, useOpenChat } from "./history/useOpenChat";
import { type AgentRun, useAgentRun } from "./useAgentRun";
import { useRememberedChat } from "./history/useRememberedChat";

/** "chat" answers a question; "agent" works through a task in steps and asks before it changes anything. */
export type ChatMode = "chat" | "agent";

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
  /** Starts an empty thread. The chat that was open stays saved. */
  newChat: () => void;
  /** The saved chat this thread belongs to, or null while it has none yet. */
  chatId: string | null;
  /** Puts a saved chat in the thread, so the next question carries it on. */
  openChat: (id: string) => Promise<OpenResult>;
  /** A saved chat is being fetched. */
  openingChat: boolean;
  /** How the next message asks to be answered. Nothing chosen means as Settings says. */
  prefs: AnswerPrefs;
  setPrefs: (prefs: AnswerPrefs) => void;
  mode: ChatMode;
  /** Changing the mode is not possible while a question is being answered. */
  setMode: (mode: ChatMode) => void;
  /** The task being worked on, with its steps and the changes waiting for the person. Null when none is. */
  agent: AgentView | null;
  /** The person's answer to one change the Copilot asked for. */
  decideChange: (actionId: string, approve: boolean) => void;
  /** Stops the task being worked on. */
  stopRun: () => void;
}

interface Question {
  messages: ChatMessage[];
  page: string;
  requestId: number;
  chatId: string | null;
  prefs: AnswerPrefs;
}

interface Around {
  apply: Apply;
  /** Whether the answer to this question is still the one awaited. The person may have moved to another chat. */
  isAwaited: (requestId: number) => boolean;
  restore: (text: string) => void;
  /** A chat was saved, so the list of chats is out of date. */
  saved: () => void;
}

/** A message the engine refuses goes back into the box, so the person can change it rather than retype it. */
function failedWith(error: unknown, question: Question, around: Around): void {
  const { messages, requestId } = question;
  const awaited = around.isAwaited(requestId);
  const refusal = refusalSentence(error) ?? undefined;
  const last = messages[messages.length - 1];
  if (awaited && refusal && last?.role === "user") around.restore(last.content);
  const chatGone = awaited && isChatGone(error);
  if (chatGone) forgetChat();
  around.apply({ type: "failed", requestId, refusal, chatGone });
}

/** Asks the engine, which saves the question and the answer in the chat. */
async function answer(question: Question, around: Around): Promise<void> {
  const { messages, page, requestId, chatId, prefs } = question;
  try {
    const reply = await askInChat(messages, page, chatId, prefs);
    around.apply({ type: "replied", requestId, reply });
    around.saved();
  } catch (error) {
    failedWith(error, question, around);
  }
}

function makeAround(store: ChatStore, restore: (text: string) => void, saved: () => void): Around {
  const { live, apply } = store;
  return { apply, restore, saved, isAwaited: (id) => live.current.state.pending === id };
}

/** Sending and retrying. An answer that arrives after the person moved to another chat is saved but not shown. */
interface Route {
  mode: { current: ChatMode };
  run: AgentRun;
}

function useAsking(
  store: ChatStore,
  restore: (text: string) => void,
  prefs: { current: AnswerPrefs },
  route: Route,
) {
  const { live, apply } = store;
  const client = useQueryClient();
  const saved = useCallback(() => void client.invalidateQueries({ queryKey: chatListKey }), [client]);
  const begin = useCallback(
    (make: (requestId: number) => ChatAction): boolean => {
      const before = live.current.state;
      const requestId = ++live.current.seq;
      const next = apply(make(requestId));
      if (next === before) return false;
      const question = {
        messages: next.messages,
        page: live.current.page,
        requestId,
        chatId: next.chatId,
        prefs: prefs.current,
      };
      const around = makeAround(store, restore, saved);
      if (route.mode.current === "agent") {
        const failed = (error: unknown) => failedWith(error, question, around);
        route.run.start(question, { apply: around.apply, saved, failed });
      } else void answer(question, around);
      return true;
    },
    [live, apply, store, restore, saved, prefs, route],
  );
  const send = useCallback(
    (text: string) => {
      const content = text.trim().slice(0, MAX_MESSAGE_CHARS);
      return begin((requestId) => ({ type: "sent", content, requestId }));
    },
    [begin],
  );
  const retry = useCallback(() => void begin((requestId) => ({ type: "retried", requestId })), [begin]);
  return { send, retry };
}

/** The conversation with the Copilot: what was said, what is awaited, and what the person is typing. */
export function useChatSession(page: string): ChatSession {
  const store = useChatStore(page);
  const { apply, live, state } = store;
  const [draft, setDraft] = useState("");
  const restore = useCallback((text: string) => setDraft((current) => current || text), []);
  const [prefs, setPrefs] = useState<AnswerPrefs>(NO_PREFS);
  const prefsNow = useRef(prefs);
  prefsNow.current = prefs;
  const [mode, setModeState] = useState<ChatMode>("chat");
  const modeNow = useRef(mode);
  modeNow.current = mode;
  const run = useAgentRun();
  const route = useMemo(() => ({ mode: modeNow, run }), [run]);
  const { send, retry } = useAsking(store, restore, prefsNow, route);
  const opening = useOpenChat(store);
  useRememberedChat(state.chatId);

  const { abandon } = run;
  const newChat = useCallback(() => {
    abandon();
    forgetChat();
    apply({ type: "cleared" });
  }, [apply, abandon]);
  const openChat = useCallback(
    async (id: string) => {
      abandon();
      return opening.openChat(id);
    },
    [abandon, opening],
  );
  const setMode = useCallback((next: ChatMode) => {
    if (live.current.state.status !== "thinking") setModeState(next);
  }, [live]);

  const { messages, status, failure, chatId } = state;
  const thinking = status === "thinking";
  const failed = status === "failed";
  return useMemo(
    () => ({
      messages,
      thinking,
      failed,
      failure,
      draft,
      setDraft,
      send,
      retry,
      newChat,
      chatId,
      openChat,
      openingChat: opening.openingChat,
      prefs,
      setPrefs,
      mode,
      setMode,
      agent: run.view,
      decideChange: run.decide,
      stopRun: run.stop,
    }),
    [
      messages,
      thinking,
      failed,
      failure,
      draft,
      send,
      retry,
      newChat,
      chatId,
      openChat,
      opening.openingChat,
      prefs,
      mode,
      setMode,
      run.view,
      run.decide,
      run.stop,
    ],
  );
}
