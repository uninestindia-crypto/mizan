import { CLI_PREFIX, sortApps } from "../../lib/aiSource";
import type { AgentCli } from "../../lib/types";

// The words and rules behind the "Set up AI apps on this computer" card. Plain language only: no engine names, no commands.

/** The apps the Copilot can ask a question. The rest can be set up but cannot answer yet. */
const ANSWERING: readonly string[] = ["claude", "codex", "gemini"];

const ONE_LINE: Record<string, string> = {
  claude: "Anthropic's AI assistant. Sign in with your Claude account.",
  codex: "OpenAI's AI assistant. Sign in with your ChatGPT account.",
  gemini: "Google's AI assistant. Sign in with your Google account.",
  antigravity: "Google's AI app. It cannot answer Copilot questions yet.",
};

const SIGN_IN_WINDOW_NOTE =
  "A sign-in window opened. Choose “Login with Google” there and finish in your browser, " +
  "then come back and press Check again.";

export type NextStep = "install" | "signin" | "done";
export type SetupAction = "install" | "signin";

export interface StateWords {
  text: string;
  tone: "neutral" | "brand" | "up" | "warn";
}

/** A sign-in that started no background job opened a window instead; this says what to do in it. */
export function signInNote(action: SetupAction, job: unknown): string | null {
  return action === "signin" && !job ? SIGN_IN_WINDOW_NOTE : null;
}

/** The name a person knows the app by, without the word the engine adds for programmers. */
export function plainName(agent: Pick<AgentCli, "name">): string {
  return agent.name.replace(/\s+CLI$/i, "");
}

/** One plain line about what the app is. An app this screen has no line for gets a plain default. */
export function oneLine(agent: Pick<AgentCli, "id" | "maker">): string {
  return ONE_LINE[agent.id] ?? `An AI app from ${agent.maker}.`;
}

/** What a person can do next: install it, sign in to it, or nothing because it is ready. */
export function nextStep(agent: Pick<AgentCli, "installed" | "state">): NextStep {
  if (!agent.installed) return "install";
  return agent.state === "CONNECTED" ? "done" : "signin";
}

/** Whether the Copilot can ask this app a question, so "Test this AI" makes sense for it. */
export function canAnswer(agent: Pick<AgentCli, "id">): boolean {
  return ANSWERING.includes(agent.id);
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

/** The state in words. While an install or sign-in runs, that is what the badge says. */
export function stateWords(agent: Pick<AgentCli, "state" | "job">): StateWords {
  if (agent.job?.state === "RUNNING") {
    return { text: agent.job.action === "install" ? "Installing" : "Signing in", tone: "brand" };
  }
  return STATES[agent.state] ?? STATES.NOT_INSTALLED;
}

/** Claude Code, Codex and Gemini first, in the order the AI choice above lists them; any other app after them. */
export function inOrder(apps: readonly AgentCli[]): AgentCli[] {
  return sortApps(apps);
}
