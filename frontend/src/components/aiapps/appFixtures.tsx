import { type BoundFunctions, type queries, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import type { AgentCli, AgentCliJob } from "../../lib/types";
import { AgentCliBridge } from "../AgentCliBridge";
import { renderApp, routeApi } from "../agents/testHarness";
import { useAiStatus } from "../settings/AiSourceQueries";

// Shared by the tests of the "Set up AI apps on this computer" card: a fake engine, the apps it lists, and finders.

export const STATUS = "/api/v2/cli/status";
export const RECHECK = "/api/v2/cli/status?refresh=true";
export const LAUNCH = "/api/v2/cli/launch";
export const AI_STATUS = "/api/v2/copilot/status";
export const AI_TEST = "/api/v2/copilot/ai/test";

const MAKERS: Record<string, [string, string]> = {
  antigravity: ["Antigravity", "Google"],
  claude: ["Claude Code", "Anthropic"],
  codex: ["Codex", "OpenAI"],
};

/** An app as the engine lists it. The engine's own wording is kept in, to show that this screen does not use it. */
export function app(id: string, state: AgentCli["state"] = "CONNECTED", over: Partial<AgentCli> = {}): AgentCli {
  const [name, maker] = MAKERS[id] ?? [id, "Someone"];
  const signed = { CONNECTED: true, UNKNOWN: null, NEEDS_SIGN_IN: false, NOT_INSTALLED: false }[state];
  return {
    id,
    name,
    maker,
    description: `${maker}'s coding agent for the terminal.`,
    docs_url: "",
    installed: state !== "NOT_INSTALLED",
    command: id,
    path: null,
    version: "1.0.0",
    authenticated: signed,
    auth_detail: "Using the ANTHROPIC_API_KEY key saved in QuantOS",
    state,
    signin_mode: "browser",
    job: null,
    ...over,
  };
}

export function job(over: Partial<AgentCliJob> = {}): AgentCliJob {
  return {
    id: "job-1",
    action: "signin",
    state: "RUNNING",
    message: "Your browser will open. Sign in there, then come back to QuantOS.",
    url: null,
    accepts_code: false,
    output: [],
    seconds: 3.2,
    ended_seconds_ago: null,
    before: null,
    after: null,
    ...over,
  };
}

export interface Engine {
  apps: AgentCli[];
}

type Routes = (engine: Engine) => Record<string, unknown>;

const AI_CHOICE = { source: "cli", cli: null, api: null, fallback: true };
const AI_READY = { ai_ready: true, apps: [], ai: AI_CHOICE, providers: [] };

/** A fake engine. What `apps` holds is what the next look at the apps returns. */
export function engine(apps: AgentCli[], routes: Routes = () => ({})): Engine {
  const state: Engine = { apps };
  const listing = () => structuredClone(state.apps);
  const base = { [`GET ${STATUS}`]: listing, [`GET ${RECHECK}`]: listing, [`GET ${AI_STATUS}`]: AI_READY };
  routeApi({ ...base, ...routes(state) });
  return state;
}

function withJob(apps: AgentCli[], id: string, running: AgentCliJob): AgentCli[] {
  return apps.map((a) => (a.id === id ? { ...a, job: running } : a));
}

/** The engine starts a job on one app: the launch answer carries it, and the next look shows it running. */
export function startsJob(id: string, running: AgentCliJob): Routes {
  const start = (state: Engine) => () => {
    state.apps = withJob(state.apps, id, running);
    return { success: true, message: running.message, job: running };
  };
  return (state) => ({ [`POST ${LAUNCH}`]: start(state) });
}

/** The card, with the Copilot's own AI check running beside it, as it does on the Settings screen. */
export function WithCopilotCheck() {
  useAiStatus();
  return <AgentCliBridge />;
}

export async function shown(apps: AgentCli[], routes?: Routes, ui: ReactElement = <AgentCliBridge />) {
  const state = engine(apps, routes);
  const view = renderApp(ui);
  await screen.findAllByRole("heading", { level: 3 });
  return { state, ...view };
}

type Scope = BoundFunctions<typeof queries>;

/** One app's card, found by the name a person sees. */
export function cardOf(name: string): Scope {
  const title = screen.getByRole("heading", { level: 3, name });
  return within(title.closest("[data-app-name]") as HTMLElement);
}

/** The names of the buttons in a scope, as a screen reader says them. */
export function buttonsIn(scope: Scope): string[] {
  return scope.queryAllByRole("button").map((b: HTMLElement) => b.getAttribute("aria-label") ?? b.textContent ?? "");
}
