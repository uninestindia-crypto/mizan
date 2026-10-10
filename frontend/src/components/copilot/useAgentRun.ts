import { useCallback, useEffect, useRef, useState } from "react";
import {
  agentApi,
  type AgentPoll,
  type AgentView,
  answering,
  applyPoll,
  STARTING,
  STOPPED_REPLY,
} from "../../lib/agentRun";
import type { AnswerPrefs } from "../../lib/answerPrefs";
import { normaliseReply } from "../../lib/copilot";
import { readSavedReply } from "../../lib/copilotHistory";
import type { ChatAction, ChatMessage } from "./chatState";
import { startPoller } from "./verifyPolling";

/** How the screen learns of an ending: the answer, a failure, or a sentence that something was lost. */
export interface RunEnd {
  apply: (action: ChatAction) => unknown;
  /** A chat was saved, so the list of chats is out of date. */
  saved: () => void;
  /** The request failed to start; the caller words it. */
  failed: (error: unknown) => void;
}

export interface AgentQuestion {
  messages: ChatMessage[];
  page: string;
  requestId: number;
  chatId: string | null;
  prefs: AnswerPrefs;
}

/** How often a running task is looked at. A test makes this short. */
export const agentPolling = { intervalMs: 1000 };
/** A stopped run hands back what it found a moment later; this many more looks wait for it. */
const GRACE_LOOKS = 6;

export interface AgentRun {
  view: AgentView | null;
  start: (question: AgentQuestion, end: RunEnd) => void;
  decide: (actionId: string, approve: boolean) => void;
  stop: () => void;
  /** Stops the run quietly, for a person who moved to another chat. */
  abandon: () => void;
}

function sentence(text: string) {
  return { ...normaliseReply({ reply: text }), mode: "ai" as const };
}

/** A task the Copilot works on in steps, asking before it changes anything. The engine keeps the run. */
export function useAgentRun(): AgentRun {
  const [view, setView] = useState<AgentView | null>(null);
  const live = useRef<{ question: AgentQuestion; end: RunEnd } | null>(null);
  const after = useRef(0);
  const grace = useRef(GRACE_LOOKS);
  const runId = view?.runId ?? null;
  const runNow = useRef<string | null>(null);
  runNow.current = runId;

  const finish = useCallback((reply: ReturnType<typeof readSavedReply> | null, failed: boolean) => {
    const current = live.current;
    live.current = null;
    setView(null);
    if (!current) return;
    const { requestId } = current.question;
    if (failed || reply === null) current.end.apply({ type: "failed", requestId });
    else {
      current.end.apply({ type: "replied", requestId, reply });
      current.end.saved();
    }
  }, []);

  const onPoll = useCallback(
    (poll: AgentPoll) => {
      after.current = poll.next;
      setView((before) => (before ? applyPoll(before, poll) : before));
      if (poll.status === "done") finish(readSavedReply(poll.result), false);
      else if (poll.status === "failed") finish(null, true);
      else if (poll.status === "cancelled") {
        if (poll.result !== null) finish(readSavedReply(poll.result), false);
        else if ((grace.current -= 1) <= 0) {
          finish({ ...sentence(STOPPED_REPLY), conversationId: null, savedNote: null }, false);
        }
      }
    },
    [finish],
  );

  useEffect(() => {
    if (!runId) return undefined;
    return startPoller<AgentPoll>({
      intervalMs: agentPolling.intervalMs,
      fetch: () => agentApi.poll(runId, after.current),
      keepGoing: (poll) => poll.status === "running" || poll.status === "waiting" || (poll.status === "cancelled" && poll.result === null && grace.current > 0),
      onPoll,
      onGiveUp: () => finish(null, true),
    });
  }, [runId, onPoll, finish]);

  const start = useCallback((question: AgentQuestion, end: RunEnd) => {
    live.current = { question, end };
    after.current = 0;
    grace.current = GRACE_LOOKS;
    setView(STARTING);
    agentApi.start(question.messages, question.page, question.chatId, question.prefs).then(
      ({ run_id }) => {
        if (live.current?.question.requestId === question.requestId) {
          setView((before) => (before ? { ...before, runId: run_id } : before));
        } else void agentApi.stop(run_id).catch(() => undefined);
      },
      (error) => {
        if (live.current?.question.requestId !== question.requestId) return;
        live.current = null;
        setView(null);
        end.failed(error);
      },
    );
  }, []);

  const decide = useCallback((actionId: string, approve: boolean) => {
    const id = runNow.current;
    if (!id) return;
    setView((before) => (before ? answering(before, actionId) : before));
    // An answer that arrives too late (already answered, or the run is over) is not an error: the next look shows it.
    void agentApi.decide(id, actionId, approve).catch(() => undefined);
  }, []);

  const stop = useCallback(() => {
    const id = runNow.current;
    if (!id) return;
    setView((before) => (before ? { ...before, stopping: true } : before));
    void agentApi.stop(id).catch(() => undefined);
  }, []);

  const abandon = useCallback(() => {
    const id = runNow.current;
    live.current = null;
    setView(null);
    if (id) void agentApi.stop(id).catch(() => undefined);
  }, []);

  return { view, start, decide, stop, abandon };
}
