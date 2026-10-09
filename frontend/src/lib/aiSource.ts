// Which AI answers: the shapes the Settings card and the second-opinion picker share, and the plain rules that say, in
// words a person can read, where a question goes. The order mirrors the engine's (src/quant_system/copilot/ai_choice.py):
// the kind the person chose first, the other kind behind it when the backup is on; the apps in a fixed order and the
// saved keys in a fixed order, a favourite first within its kind; only apps that are installed and keys that are saved.

import type { ProviderOption } from "./copilot";

export type AiKind = "cli" | "api";
export type AppId = "claude" | "codex" | "gemini";
export type AppState = "CONNECTED" | "NEEDS_SIGN_IN" | "NOT_INSTALLED" | "UNKNOWN";

export interface AiApp {
  id: AppId;
  /** The name the install and sign-in cards below use. */
  name: string;
  label: string;
  state: AppState;
  installed: boolean;
  ready: boolean;
}

export interface AiChoice {
  source: AiKind;
  cli: AppId | null;
  api: string | null;
  fallback: boolean;
}

/** What GET /api/v2/copilot/status says about the AI. Other fields it carries are not used here. */
export interface AiStatus {
  ai_ready: boolean;
  apps: AiApp[];
  ai: AiChoice;
  providers: ProviderOption[];
}

export interface AiTestResult {
  ok: boolean;
  who: string | null;
  message: string;
}

/** The four settings that hold the choice. A save sends only the ones that changed. */
export interface AiSettings {
  ai_source: AiKind;
  ai_cli: AppId | null;
  ai_api: string | null;
  ai_fallback: boolean;
}

export type AiSettingsPatch = Partial<AiSettings>;

export const CLI_PREFIX = "cli:";
/** Where the install and sign-in cards sit on the Settings screen, so "Set up" can take a person to them. */
export const APPS_ANCHOR = "ai-apps-setup";

const APP_ORDER: readonly string[] = ["claude", "codex", "antigravity"];
const KEY_ORDER: readonly string[] = ["anthropic", "openai", "gemini", "groq", "deepseek", "mistral", "openrouter"];
const APP_NAMES: Record<string, string> = { antigravity: "Antigravity", claude: "Claude Code", codex: "Codex" };

/** The plain name of an app in a sentence. */
export function appName(app: Pick<AiApp, "id" | "name">): string {
  return APP_NAMES[app.id] ?? app.name;
}

export function choiceFrom(saved: AiSettings): AiChoice {
  return { source: saved.ai_source, cli: saved.ai_cli, api: saved.ai_api, fallback: saved.ai_fallback };
}

/** The choice as it will be once a save goes through, so the screen answers a click at once. */
export function applyPatch(choice: AiChoice, patch: AiSettingsPatch): AiChoice {
  return {
    source: patch.ai_source ?? choice.source,
    cli: patch.ai_cli === undefined ? choice.cli : patch.ai_cli,
    api: patch.ai_api === undefined ? choice.api : patch.ai_api,
    fallback: patch.ai_fallback ?? choice.fallback,
  };
}

/** Drops from the changes still on their way the ones a finished save was about, unless a newer click replaced them. */
export function settle(wanted: AiSettingsPatch, finished: AiSettingsPatch): AiSettingsPatch {
  const keep = Object.entries(wanted).filter(([name, value]) => finished[name as keyof AiSettings] !== value);
  return Object.fromEntries(keep) as AiSettingsPatch;
}

// -------------------------------------------------------------------------------------------------- the order

/** "signed_out" is an installed app that says it is not signed in: it is asked, and fails, so it never answers. */
export type EntryState = "ready" | "unknown" | "signed_out";

export interface PlanEntry {
  kind: AiKind;
  id: string;
  name: string;
  state: EntryState;
}

function rank(order: readonly string[], id: string): number {
  const at = order.indexOf(id);
  return at < 0 ? order.length : at;
}

function favouriteFirst<T extends { id: string }>(items: T[], favourite: string | null): T[] {
  const chosen = items.filter((item) => item.id === favourite);
  return [...chosen, ...items.filter((item) => item.id !== favourite)];
}

function appEntry(app: AiApp): PlanEntry {
  const state: EntryState = app.state === "CONNECTED" ? "ready" : app.state === "UNKNOWN" ? "unknown" : "signed_out";
  return { kind: "cli", id: app.id, name: appName(app), state };
}

/** The apps in the order they are asked when none is favoured. */
export function sortApps<T extends { id: string }>(apps: readonly T[]): T[] {
  return [...apps].sort((a, b) => rank(APP_ORDER, a.id) - rank(APP_ORDER, b.id));
}

/** The saved-key providers in the order they are asked when none is favoured. */
export function sortKeys<T extends { id: string }>(providers: readonly T[]): T[] {
  return [...providers].sort((a, b) => rank(KEY_ORDER, a.id) - rank(KEY_ORDER, b.id));
}

function appEntries(apps: readonly AiApp[], favourite: string | null): PlanEntry[] {
  const present = apps.filter((app) => app.installed && app.state !== "NOT_INSTALLED");
  return favouriteFirst(sortApps(present), favourite).map(appEntry);
}

function keyEntries(providers: readonly ProviderOption[], favourite: string | null): PlanEntry[] {
  const entries = favouriteFirst(sortKeys(providers.filter((p) => p.ready)), favourite);
  return entries.map((p): PlanEntry => ({ kind: "api", id: p.id, name: p.label, state: "ready" }));
}

type PlanSource = Pick<AiStatus, "apps" | "providers">;

/** Every AI that would be asked, in the order it would be asked. */
export function buildPlan(status: PlanSource, choice: AiChoice): PlanEntry[] {
  const apps = appEntries(status.apps, choice.cli);
  const keys = keyEntries(status.providers, choice.api);
  const [first, second] = choice.source === "cli" ? [apps, keys] : [keys, apps];
  return choice.fallback ? [...first, ...second] : first;
}

const answers = (entry: PlanEntry) => entry.state !== "signed_out";

// ------------------------------------------------------------------------------------------------ the sentence

function join(parts: readonly string[]): string {
  if (parts.length < 2) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function describe(entry: PlanEntry): string {
  if (entry.kind === "api") return `your saved ${entry.name} key`;
  return entry.state === "unknown" ? `${entry.name} (not checked yet)` : entry.name;
}

function nothingReady(status: PlanSource, choice: AiChoice): string {
  const everything = buildPlan(status, { ...choice, fallback: true });
  if (everything.some(answers)) {
    const chosen = choice.source === "cli" ? "No AI app on this computer is ready" : "No saved AI key is ready";
    return `${chosen}, and trying the other kind is turned off, so your questions have nowhere to go.`;
  }
  const signedOut = everything.filter((entry) => entry.state === "signed_out").map((entry) => entry.name);
  if (signedOut.length === 0) return "No AI is set up yet.";
  return `No AI is ready yet. ${join(signedOut)} ${signedOut.length > 1 ? "are" : "is"} not signed in.`;
}

function backupNote(status: PlanSource, choice: AiChoice, backups: readonly PlanEntry[], used: number): string {
  if (backups.length > 0) {
    const noun = backups.length > 1 ? "backups" : "a backup";
    return `, with ${join(backups.map(describe))} as ${noun}`;
  }
  const withBackup = buildPlan(status, { ...choice, fallback: true }).filter(answers).length;
  return !choice.fallback && withBackup > used ? " and nowhere else" : "";
}

/** One sentence that says where a question goes right now. It is built only from what is set up. */
export function summarise(status: PlanSource, choice: AiChoice): string {
  const plan = buildPlan(status, choice);
  const [first, ...backups] = plan.filter(answers);
  if (!first) return nothingReady(status, choice);
  const skipped = plan.slice(0, plan.indexOf(first)).map((entry) => entry.name);
  const lead = skipped.length
    ? `${join(skipped)} ${skipped.length > 1 ? "are" : "is"} not signed in, so right now your questions go to`
    : "Right now your questions go to";
  return `${lead} ${describe(first)}${backupNote(status, choice, backups, 1 + backups.length)}.`;
}

/** Whether any AI is in a position to answer under the current choice. */
export function hasAnswerer(status: PlanSource, choice: AiChoice): boolean {
  return buildPlan(status, choice).some(answers);
}

// ---------------------------------------------------------------------------------------------------- the chips

export interface Chip {
  text: string;
  tone: "up" | "warn" | "neutral";
}

const APP_CHIPS: Record<AppState, Chip> = {
  CONNECTED: { text: "Ready", tone: "up" },
  NEEDS_SIGN_IN: { text: "Not signed in", tone: "warn" },
  NOT_INSTALLED: { text: "Not installed", tone: "neutral" },
  UNKNOWN: { text: "Not checked yet", tone: "neutral" },
};

export function appChip(app: Pick<AiApp, "state">): Chip {
  return APP_CHIPS[app.state] ?? APP_CHIPS.UNKNOWN;
}

export function keyChip(provider: Pick<ProviderOption, "ready">): Chip {
  return provider.ready ? { text: "Key saved", tone: "up" } : { text: "No key yet", tone: "neutral" };
}

/** An app that the install and sign-in cards below can fix. */
export function needsSetup(app: Pick<AiApp, "state">): boolean {
  return app.state === "NOT_INSTALLED" || app.state === "NEEDS_SIGN_IN";
}

export const UNKNOWN_HINT = "Not checked yet. Press Test this AI.";

// ---------------------------------------------------------------------------------------------------- testing

/** The AI to test: the favourite for the chosen kind, or null for whatever the Copilot would use. */
export function testTarget(choice: AiChoice): string | null {
  if (choice.source === "cli") return choice.cli ? CLI_PREFIX + choice.cli : null;
  return choice.api;
}

/** What the test is about, for the line next to the button. */
export function testSubject(status: Pick<AiStatus, "apps" | "providers">, target: string | null): string {
  if (target === null) return "Tests whichever AI your questions go to first.";
  const app = status.apps.find((a) => CLI_PREFIX + a.id === target);
  const name = app ? app.label : (status.providers.find((p) => p.id === target)?.label ?? target);
  return `Tests ${name}.`;
}

/** The sentence under a finished test: the engine's own words, led by which AI they are about when they do not say. */
export function testLine(result: AiTestResult): string {
  const { who, message } = result;
  return who && !message.includes(who) ? `${who}: ${message}` : message;
}

// ------------------------------------------------------------------------------------------- the second opinion

export interface ModelGroups {
  apps: ProviderOption[];
  keys: ProviderOption[];
}

/** The AIs a second opinion can ask, apps first, as the engine lists them. An app's id starts with "cli:". */
export function groupModels(models: readonly ProviderOption[]): ModelGroups {
  const isApp = (model: ProviderOption) => model.id.startsWith(CLI_PREFIX);
  return { apps: models.filter(isApp), keys: models.filter((model) => !isApp(model)) };
}

// ----------------------------------------------------------------------------------------------- "Set up" jump

/** Each card names the app it is for in data-app-name, the engine's name for it, so a title can be worded freely. */
function findCard(root: HTMLElement, name: string): HTMLElement | null {
  const cards = Array.from(root.querySelectorAll<HTMLElement>("[data-app-name]"));
  return cards.find((card) => card.dataset.appName === name) ?? null;
}

/** Scrolls to the install and sign-in card of one app (or to the whole group) and puts the keyboard there. */
export function showAppSetup(bridgeName: string | null): void {
  const root = document.getElementById(APPS_ANCHOR);
  if (!root) return;
  const card = bridgeName ? findCard(root, bridgeName) : null;
  const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
  (card ?? root).scrollIntoView?.({ behavior: calm ? "auto" : "smooth", block: "center" });
  const control = card?.querySelector<HTMLElement>("button:not(:disabled)") ?? root;
  control.focus({ preventScroll: true });
}
