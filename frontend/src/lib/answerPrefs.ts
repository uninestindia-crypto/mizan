// How one Copilot message asks to be answered, over what Settings says. Every part is optional: nothing chosen means
// "as usual". The engine checks every value again before it uses it.

import type { Speed } from "./aiSource";

export interface AnswerPrefs {
  /** An AI by its id in the order ("cli:claude", "openai"), or null for the person's own order. */
  ai: string | null;
  model: string | null;
  thinking: string | null;
  speed: Speed | null;
  /** How many AIs work on a task in agent mode, the Copilot itself included. Null: as Settings says. */
  helpers: number | null;
}

export const NO_PREFS: AnswerPrefs = { ai: null, model: null, thinking: null, speed: null, helpers: null };

/** Nothing asked for: the message is answered exactly as Settings says. */
export function isUsual(prefs: AnswerPrefs): boolean {
  return prefs.ai === null && prefs.model === null && prefs.thinking === null && prefs.speed === null && prefs.helpers === null;
}

/** The part of a chat request that carries the choices, or undefined when there are none. */
export function prefsBody(prefs: AnswerPrefs): Partial<AnswerPrefs> | undefined {
  if (isUsual(prefs)) return undefined;
  const body: Partial<AnswerPrefs> = {};
  if (prefs.ai) body.ai = prefs.ai;
  if (prefs.model) body.model = prefs.model;
  if (prefs.thinking) body.thinking = prefs.thinking;
  if (prefs.speed) body.speed = prefs.speed;
  if (prefs.helpers) body.helpers = prefs.helpers;
  return body;
}

/** A change of AI starts that AI's own choices over: a model of one AI means nothing to another. */
export function withAi(prefs: AnswerPrefs, ai: string | null): AnswerPrefs {
  return { ...prefs, ai, model: null, thinking: null };
}
