import { screen } from "@testing-library/react";
import type { Agent, Recipe, RunResult } from "../../lib/agents";
import { routeApi } from "./testHarness";

// What the Agents screen tests ask the engine and what it answers.

export const mine: Agent = {
  id: "mine1",
  name: "My halal check",
  description: "Checks a stock I am watching.",
  instructions: "",
  tools: ["shariah_check"],
  steps: ["Is {symbol} halal?", "Show the facts about {symbol}."],
  needs_symbol: true,
  built_in: false,
  created_at: "2026-10-06T10:00:00+00:00",
  updated_at: "2026-10-06T10:00:00+00:00",
};
export const daily: Agent = {
  ...mine,
  id: "mine2",
  name: "Daily look",
  steps: ["Show my watchlist."],
  needs_symbol: false,
};
export const ready: Recipe = {
  id: "recipe_check",
  name: "Check a stock, step by step",
  description: "Facts, halal screen and news for one stock.",
  instructions: "",
  tools: ["stock_facts", "shariah_check"],
  steps: ["Show the facts about {symbol}."],
  needs_symbol: true,
  built_in: true,
  needs_ai: false,
};
export const needsAi: Recipe = { ...ready, id: "recipe_news", name: "Read the news", needs_ai: true };

export const TOOLS = {
  tools: [
    { name: "stock_facts", label: "Price facts", help: "Prices.", description: "For the model: prices." },
    { name: "shariah_check", label: "Halal screening", help: "Both standards.", description: "For the model." },
  ],
};

export const RESULT: RunResult = {
  name: "Check a stock, step by step",
  symbol: "TCS",
  steps: [
    {
      number: 1,
      text: "Show the facts about TCS.",
      reply: "TCS has been **steady**.\n\n- one\n- see [the filing](https://example.com/f)",
      looked_at: [
        { label: "Price facts", summary: "One-year return 12%", ok: true },
        { label: "News", summary: "Could not reach the news.", ok: false },
      ],
      error: null,
    },
    { number: 2, text: "Is TCS halal?", reply: "", looked_at: [], error: "That step could not finish." },
  ],
  proposals: [
    { kind: "navigate", label: "Open TCS", path: "/stock/TCS", symbol: "TCS" },
    { kind: "second_opinion", label: "Get a second opinion on TCS", path: null, symbol: "TCS" },
    { kind: "navigate", label: "Somewhere else", path: "https://evil.example", symbol: null },
  ],
  model: null,
  completed: true,
  note: "No AI key was used, so each step used the built-in answers.",
};

// The engine lists the AI apps on this computer first, then the keys. An agent can run if either kind is ready.
const APPS = ["claude", "codex", "gemini"].map((name) => ({ id: `cli:${name}`, label: `${name} app`, ready: false }));
const key = (ready: boolean) => ({ id: "openai", label: "OpenAI", ready });
export const AI_READY = { models: [...APPS, key(true)] };
export const AI_APP_READY = { models: [{ ...APPS[0], ready: true }, ...APPS.slice(1), key(false)] };
export const AI_OFF = { models: [...APPS, key(false)] };

export function engine(extra: Record<string, unknown> = {}, agents: Agent[] = [mine, daily]) {
  routeApi({
    "GET /api/v2/copilot/tools": TOOLS,
    "GET /api/v2/copilot/models": AI_READY,
    "GET /api/v2/copilot/agents": { agents, recipes: [ready, needsAi] },
    ...extra,
  });
}

export const runUrl = (id: string) => `/api/v2/copilot/agents/${id}/run`;
export const card = (name: string) => screen.getByRole("heading", { name }).closest("article") as HTMLElement;

