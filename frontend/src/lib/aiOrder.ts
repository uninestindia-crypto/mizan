// The person's own order of AIs: which are on the list, in what order, and the model and thinking level chosen for each.
// Pure functions, so the screen only draws what these say. The engine checks every value again (copilot/ai_prefs.py).

import { appName, buildPlan, CLI_PREFIX, type AiChoice, type AiStatus, type OrderEntry } from "./aiSource";
import type { AiModels, CliCapabilities } from "./types";

export type CandidateState = "ready" | "unknown" | "signed_out" | "missing";

/** Any AI the person could put on the list: an app on this computer, or a provider they may have a key for. */
export interface Candidate {
  id: string;
  kind: "cli" | "api";
  name: string;
  state: CandidateState;
  /** The engine's name for an app, which its install and sign-in card is found by. */
  setupName?: string;
}

export interface OrderView {
  /** On the list and set up, in the order they are asked. */
  listed: { candidate: Candidate; entry: OrderEntry }[];
  /** Set up but not on the list. */
  addable: Candidate[];
  /** Not set up (not installed, no key). A choice saved for one is kept for when it is. */
  missing: Candidate[];
}

const APP_STATE: Record<string, CandidateState> = {
  CONNECTED: "ready",
  UNKNOWN: "unknown",
  NEEDS_SIGN_IN: "signed_out",
  NOT_INSTALLED: "missing",
};

export function candidates(status: Pick<AiStatus, "apps" | "providers">): Candidate[] {
  const apps = status.apps.map(
    (app): Candidate => ({
      id: CLI_PREFIX + app.id,
      kind: "cli",
      name: appName(app),
      state: app.installed ? (APP_STATE[app.state] ?? "unknown") : "missing",
      setupName: app.name,
    }),
  );
  const keys = status.providers.map(
    (provider): Candidate => ({
      id: provider.id,
      kind: "api",
      name: provider.label,
      state: provider.ready ? "ready" : "missing",
    }),
  );
  return [...apps, ...keys];
}

/** The order that is really in force: the person's own, or the one the built-in rules produce. */
export function effectiveOrder(status: AiStatus, choice: AiChoice): OrderEntry[] {
  if (choice.order && choice.order.length > 0) return choice.order;
  const builtIn = buildPlan(status, { ...choice, order: undefined, fallback: true });
  return builtIn.map((entry) => ({
    id: entry.kind === "cli" ? CLI_PREFIX + entry.id : entry.id,
    model: null,
    thinking: null,
  }));
}

export function orderView(status: AiStatus, choice: AiChoice): OrderView {
  const all = new Map(candidates(status).map((c) => [c.id, c]));
  const order = effectiveOrder(status, choice);
  const onList = new Set<string>();
  const listed: OrderView["listed"] = [];
  for (const entry of order) {
    const candidate = all.get(entry.id);
    if (!candidate || candidate.state === "missing" || onList.has(entry.id)) continue;
    onList.add(entry.id);
    listed.push({ candidate, entry });
  }
  const rest = [...all.values()].filter((c) => !onList.has(c.id));
  return { listed, addable: rest.filter((c) => c.state !== "missing"), missing: rest.filter((c) => c.state === "missing") };
}

// ------------------------------------------------------------------------------------------------ editing

/** What gets saved: the edited list, then the choices kept for AIs that are not set up right now. */
export function withKept(edited: readonly OrderEntry[], status: AiStatus, choice: AiChoice): OrderEntry[] {
  const kept = (choice.order ?? []).filter((entry) => {
    const candidate = candidates(status).find((c) => c.id === entry.id);
    return candidate?.state === "missing" && !edited.some((e) => e.id === entry.id);
  });
  return [...edited, ...kept];
}

export function move(list: readonly OrderEntry[], from: number, by: -1 | 1): OrderEntry[] {
  const to = from + by;
  const next = [...list];
  const moved = next[from];
  if (moved === undefined || to < 0 || to >= next.length) return next;
  next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export function choose(list: readonly OrderEntry[], id: string, model: string | null, thinking: string | null): OrderEntry[] {
  return list.map((entry) => (entry.id === id ? { id, model, thinking } : entry));
}

export function without(list: readonly OrderEntry[], id: string): OrderEntry[] {
  return list.filter((entry) => entry.id !== id);
}

export function added(list: readonly OrderEntry[], id: string): OrderEntry[] {
  return list.some((entry) => entry.id === id) ? [...list] : [...list, { id, model: null, thinking: null }];
}

// ---------------------------------------------------------------------------------------- models and levels

/** A model a person may pick for one AI, read live from the app or the provider. */
export interface ModelOption {
  /** What is saved when it is picked (unless its thinking level is part of its name; see ``variants``). */
  value: string;
  name: string;
  levels: string[];
  /** When the level is part of the model's name: level -> the exact name to use. */
  variants: Record<string, string> | null;
  newest: boolean;
}

export function appOptions(caps: CliCapabilities | undefined): ModelOption[] {
  return (caps?.models ?? []).map((model) => ({
    value: model.id,
    name: model.name,
    levels: model.thinking?.levels ?? [],
    variants: model.variants,
    newest: model.newest,
  }));
}

/** Levels worth offering for a provider whose model list does not say. The engine drops one a model refuses. */
const PROVIDER_LEVELS: Record<string, string[]> = {
  openai: ["low", "medium", "high", "xhigh"],
  groq: ["low", "medium", "high"],
  openrouter: ["low", "medium", "high"],
  gemini: ["low", "medium", "high"],
};

export function keyOptions(provider: string, data: AiModels | undefined): ModelOption[] {
  return (data?.newest ?? []).map((model) => ({
    value: model.id,
    name: model.name,
    levels: model.effort_levels?.length ? model.effort_levels : (PROVIDER_LEVELS[provider] ?? []),
    variants: null,
    newest: false,
  }));
}

/** The levels offered when no model is picked: every level any model of the app takes. */
export function anyLevels(caps: CliCapabilities | undefined, provider: string | null): string[] {
  if (caps) return caps.thinking_levels;
  return provider ? (PROVIDER_LEVELS[provider] ?? []) : [];
}

export interface Selection {
  option: ModelOption | null;
  level: string | null;
  /** A model saved earlier that the live list no longer shows. It is kept, and named as it was saved. */
  unlisted: string | null;
}

export function selectionOf(options: readonly ModelOption[], entry: OrderEntry): Selection {
  if (!entry.model) return { option: null, level: entry.thinking, unlisted: null };
  for (const option of options) {
    if (option.value === entry.model) return { option, level: entry.thinking, unlisted: null };
    const tier = Object.entries(option.variants ?? {}).find(([, name]) => name === entry.model);
    if (tier) return { option, level: tier[0], unlisted: null };
  }
  return { option: null, level: entry.thinking, unlisted: entry.model };
}

/** What to save for a model and a level. A model whose level is part of its name gets the right name. */
export function savedChoice(option: ModelOption | null, level: string | null): { model: string | null; thinking: string | null } {
  if (!option) return { model: null, thinking: level };
  if (option.variants) {
    const tiers = Object.keys(option.variants);
    const tier = level && option.variants[level] ? level : tiers.includes("medium") ? "medium" : tiers[0];
    return { model: tier ? (option.variants[tier] ?? option.value) : option.value, thinking: null };
  }
  return { model: option.value, thinking: level };
}

/** The levels to offer for the current pick. A model with its level in its name offers only its own. */
export function levelsFor(selection: Selection, fallback: readonly string[]): string[] {
  if (selection.option) return selection.option.levels;
  return [...fallback];
}
