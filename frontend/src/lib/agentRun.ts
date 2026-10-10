// The Copilot working on a task, step by step: what it has done so far, the changes it has asked the person to approve,
// and the final answer. The engine keeps the run; the screen asks for what is new and answers the changes.

import { api } from "./api";
import { buildChatRequest, type ChatTurn } from "./copilot";
import { prefsBody, type AnswerPrefs } from "./answerPrefs";

export type AgentStatus = "running" | "waiting" | "done" | "failed" | "cancelled";

/** One line of progress, in plain words. ``kind`` says what sort it is, so the screen can pick an icon. */
export interface AgentEvent {
  n: number;
  kind: string;
  text: string;
  ok: boolean;
  action_id?: string;
}

/** A change the Copilot has asked for. Nothing happens until the person approves it. */
export interface PendingChange {
  id: string;
  title: string;
  detail: string | null;
  note: string | null;
  /** The Copilot's own sentence on why it asks, with any advice taken out. */
  why: string;
}

export interface AgentPoll {
  status: AgentStatus;
  events: AgentEvent[];
  /** Where to carry on from at the next look. */
  next: number;
  pending: PendingChange[];
  /** The Copilot's answer, in the same shape as a chat reply, once there is one. */
  result: unknown;
  error: string | null;
}

/** What the screen shows while a run is going. */
export interface AgentView {
  runId: string | null;
  status: AgentStatus;
  events: AgentEvent[];
  pending: PendingChange[];
  /** Changes whose answer is on its way, so a second press cannot be sent. */
  answering: string[];
  stopping: boolean;
}

export const STARTING: AgentView = {
  runId: null,
  status: "running",
  events: [],
  pending: [],
  answering: [],
  stopping: false,
};

const RUNS = "/api/v2/copilot/agent/runs";

export const agentApi = {
  start: (turns: readonly ChatTurn[], page: string | null, chatId: string | null, prefs: AnswerPrefs) => {
    const asked = prefsBody(prefs);
    const body = {
      ...buildChatRequest(turns, page),
      conversation_id: chatId ?? "new",
      ...(asked ? { prefs: asked } : {}),
    };
    return api<{ run_id: string }>(RUNS, "POST", body);
  },
  poll: (runId: string, after: number) => api<AgentPoll>(`${RUNS}/${encodeURIComponent(runId)}?after=${after}`),
  stop: (runId: string) => api<{ cancelled?: boolean }>(`${RUNS}/${encodeURIComponent(runId)}`, "DELETE"),
  decide: (runId: string, actionId: string, approve: boolean) =>
    api<{ text: string }>(`${RUNS}/${encodeURIComponent(runId)}/decisions/${encodeURIComponent(actionId)}`, "POST", {
      approve,
    }),
};

export const STOPPED_REPLY = "You stopped this run before it finished.";

/** The view after one more look at the run: new lines added, and what is waiting for the person now. */
export function applyPoll(view: AgentView, poll: AgentPoll): AgentView {
  const seen = new Set(view.events.map((event) => event.n));
  const fresh = poll.events.filter((event) => !seen.has(event.n));
  const waiting = new Set(poll.pending.map((change) => change.id));
  return {
    ...view,
    status: poll.status,
    events: [...view.events, ...fresh],
    pending: poll.pending,
    answering: view.answering.filter((id) => waiting.has(id)),
  };
}

/** The person has pressed Approve or Skip on one change; it stays on screen, disabled, until the engine agrees. */
export function answering(view: AgentView, actionId: string): AgentView {
  return view.answering.includes(actionId) ? view : { ...view, answering: [...view.answering, actionId] };
}

/** Plain words for how far along the run is, for the line beside the spinner. */
export function progressWords(view: AgentView): string {
  if (view.stopping) return "Stopping…";
  if (view.pending.length > 0) return "Waiting for you to decide";
  return view.events.length === 0 ? "Getting started…" : "Working on it…";
}
