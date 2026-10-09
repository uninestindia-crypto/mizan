import { ApiError } from "../../lib/api";
import { routeApi } from "../agents/testHarness";
import { statusFor } from "../mode/modeKit";

// Shared set-up for the fundamentals tests: the engine's answers, and the words no screen may use.

type Answers = Record<string, unknown>;

/** Words that would turn a fact into advice. None of them may appear on any fundamentals screen. */
export const ADVICE = /\b(buy|sell|best|undervalued|overvalued|recommend\w*|target|cheap|expensive|should)\b/i;

/** Colours that mean good or bad. A fact is never coloured as either. */
export const GOOD_BAD_COLOURS = /\b(text|bg|border)-(up|down)(-soft)?\b/;

export function engine(answers: Answers) {
  routeApi({ "GET /api/v2/status": statusFor(false), ...answers });
}

/** An answer that is the engine refusing in a plain sentence. */
export const refuses = (code: string, message: string, status: number) => () => {
  throw new ApiError(code, message, status);
};

export const url = (symbol: string) => `GET /api/v2/fundamentals/${symbol}`;
