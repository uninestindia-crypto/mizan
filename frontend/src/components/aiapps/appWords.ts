import { CLI_PREFIX, sortApps } from "../../lib/aiSource";
import type { AgentCli } from "../../lib/types";

// The words and rules behind the "Set up AI apps on this computer" card. Plain language only: no engine names, no commands.

/** The apps the Copilot can ask a question. The rest can be set up but cannot answer yet. */
const ANSWERING: readonly string[] = ["antigravity", "claude", "codex"];

const ONE_LINE: Record<string, string> = {
  antigravity: "Google's AI assistant. Sign in with your Google account.",
  claude: "Anthropic's AI assistant. Sign in with your Claude account.",
  codex: "OpenAI's AI assistant. Sign in with your ChatGPT account.",
};

const SIGN_IN_WINDOW_NOTE =
  "A sign-in window opened. Finish in your browser, then come back and press Check again.";

export type NextStep = "install" | "signin" | "update" | "done";
export type SetupAction = "install" | "signin" | "update";

export interface StateWords {
  text: string;
  tone: "neutral" | "brand" | "up" | "warn";
}

/** A sign-in that started no background job opened a window instead; this says what to do in it. */
export function signInNote(action: SetupAction, job: unknown): string | null {
  return action === "signin" && !job ? SIGN_IN_WINDOW_NOTE : null;
}

/** What the engine said about a started step, as a note under the app: the sign-in window, or "it is busy with". */
export function launchNote(
  action: SetupAction,
  reply: { job?: { action: string } | null; joined?: boolean; message?: string },
): string | null {
  if (reply.joined && reply.job && reply.job.action !== action) return reply.message ?? null;
  return signInNote(action, reply.job);
}

/** The name a person knows the app by, without the word the engine adds for programmers. */
export function plainName(agent: Pick<AgentCli, "name">): string {
  return agent.name.replace(/\s+CLI$/i, "");
}

/** One plain line about what the app is. An app this screen has no line for gets a plain default. */
export function oneLine(agent: Pick<AgentCli, "id" | "maker" | "description">): string {
  return ONE_LINE[agent.id] ?? agent.description ?? `An AI app from ${agent.maker}.`;
}

/** What a person can do next: install it, sign in to it, or nothing because it is ready. */
export function nextStep(agent: Pick<AgentCli, "installed" | "state">): NextStep {
  if (!agent.installed) return "install";
  return agent.state === "CONNECTED" ? "done" : "signin";
}

/** Whether the Copilot can ask this app a question, so "Test this AI" makes sense for it. */
export function canAnswer(agent: Pick<AgentCli, "id" | "is_custom">): boolean {
  return ANSWERING.includes(agent.id) || agent.is_custom === true;
}

/** The id the engine's test takes for this app. */
export function testModel(agent: Pick<AgentCli, "id">): string {
  return CLI_PREFIX + agent.id;
}

const STATES: Record<AgentCli["state"], StateWords> = {
  NOT_INSTALLED: { text: "Not installed", tone: "neutral" },
  NEEDS_SIGN_IN: { text: "Installed, not signed in", tone: "warn" },
  UNKNOWN: { text: "Installed, not checked yet", tone: "neutral" },
  CONNECTED: { text: "Signed in", tone: "up" },
};

/** The state in words. While an install, sign-in or update runs, that is what the badge says. */
export function stateWords(agent: Pick<AgentCli, "state" | "job">): StateWords {
  if (agent.job?.state === "RUNNING") {
    const actionLabel =
      agent.job.action === "install" ? "Installing" : agent.job.action === "update" ? "Updating" : "Signing in";
    return { text: actionLabel, tone: "brand" };
  }
  return STATES[agent.state] ?? STATES.NOT_INSTALLED;
}

/** Claude Code, Codex and Gemini first, in the order the AI choice above lists them; any other app after them. */
export function inOrder(apps: readonly AgentCli[]): AgentCli[] {
  return sortApps(apps);
}
