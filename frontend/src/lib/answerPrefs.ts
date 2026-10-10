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
  /** Who does the work of a task in agent mode: an AI app by its id ("cli:claude"), or null for the Copilot itself. */
  runner: string | null;
}

export const NO_PREFS: AnswerPrefs = { ai: null, model: null, thinking: null, speed: null, helpers: null, runner: null };

/** Nothing asked for: the message is answered exactly as Settings says. */
export function isUsual(prefs: AnswerPrefs): boolean {
  return !isSavable(prefs) && prefs.runner === null;
}

/**
 * Something was chosen that "Make this my usual" can keep. An AI app doing a task is chosen again for each task, and the
 * model and thinking level picked for it belong to that task, so they are not kept.
 */
export function isSavable(prefs: AnswerPrefs): boolean {
  const ownAi = prefs.runner === null && (prefs.ai !== null || prefs.model !== null || prefs.thinking !== null);
  return ownAi || prefs.speed !== null || prefs.helpers !== null;
}

/** What is left after the savable choices were kept: the ones that belong to this task alone. */
export function afterSaving(prefs: AnswerPrefs): AnswerPrefs {
  if (prefs.runner === null) return NO_PREFS;
  return { ...NO_PREFS, ai: prefs.ai, model: prefs.model, thinking: prefs.thinking, runner: prefs.runner };
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
  if (prefs.runner) body.runner = prefs.runner;
  return body;
}

/** A change of AI starts that AI's own choices over: a model of one AI means nothing to another. */
export function withAi(prefs: AnswerPrefs, ai: string | null): AnswerPrefs {
  return { ...prefs, ai, model: null, thinking: null };
}
