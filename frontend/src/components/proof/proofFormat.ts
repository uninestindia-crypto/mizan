import { CircleCheck, CircleHelp, CircleX, TriangleAlert } from "lucide-react";
import { inr, int, num } from "../../lib/format";
import type { ActivityStatus, ProofFigure, ProofInput, ProofTest, StandardStatus, TestResult } from "../../lib/proof";

// How the proof says things: plain words, an icon beside every colour, and percentages that are already percentages.

type Tone = "up" | "down" | "warn" | "neutral";

export const RESULT: Record<TestResult, { word: string; tone: Tone; icon: typeof CircleCheck }> = {
  PASS: { word: "Pass", tone: "up", icon: CircleCheck },
  FAIL: { word: "Fail", tone: "down", icon: CircleX },
  BORDERLINE: { word: "Borderline", tone: "warn", icon: TriangleAlert },
  DEPENDS: { word: "Depends", tone: "warn", icon: TriangleAlert },
  NOT_COMPUTED: { word: "Not computed", tone: "neutral", icon: CircleHelp },
};

export const STANDARD_RESULT: Record<StandardStatus, { word: string; tone: Tone; icon: typeof CircleCheck }> = {
  COMPLIANT: { word: "Compliant", tone: "up", icon: CircleCheck },
  NON_COMPLIANT: { word: "Not compliant", tone: "down", icon: CircleX },
  QUESTIONABLE: { word: "Questionable", tone: "warn", icon: TriangleAlert },
  NOT_COMPUTED: { word: "Not computed", tone: "neutral", icon: CircleHelp },
};

export const ACTIVITY_RESULT: Record<ActivityStatus, { word: string; tone: Tone; icon: typeof CircleCheck }> = {
  PASS: { word: "Passed", tone: "up", icon: CircleCheck },
  FAIL: { word: "Failed", tone: "down", icon: CircleX },
  NOT_CONFIRMED: { word: "Business not confirmed", tone: "warn", icon: CircleHelp },
};

/** The sentence a test that depends on a figure the filing does not itemise always carries. */
export const DEPENDS_SENTENCE =
  "The filing does not break this figure down, so QuantOS cannot say which side of the limit this company is on.";

/** The sentence for a figure the filing does not itemise, when both readings land on the same side of the limit. */
export const TWO_READINGS_SENTENCE =
  "The filing does not break this figure down, so QuantOS shows a lower and an upper reading.";

/** True when the test's own sentence already says it cannot tell which side of the limit the company is on. */
export const SAYS_CANNOT_SAY = "cannot say which side of the limit";

export const NOT_A_FATWA = "This is a screening aid, not a fatwa.";

/** Rule names as a person reads them. A rule this app does not know is spelled out from its own name. */
const RULES: Record<string, string> = {
  interest_based_finance: "Interest-based finance",
  alcohol: "Alcohol",
  tobacco: "Tobacco",
  gambling: "Gambling",
  cinema: "Cinemas",
};

export function ruleName(rule: string): string {
  const known = RULES[rule];
  if (known) return known;
  const spaced = rule.replace(/_/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : rule;
}

/** Where the business test looked, in words. */
export const MATCHED_IN: Record<string, string> = {
  name: "the company's name",
  segment: "a business segment in its filing",
  sample: "the hand-entered sample",
};

/** A percentage that is already a percentage (12.5 is 12.5%), with a second decimal only when it is tiny. */
export function percent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "not available";
  if (value === 0) return "0%";
  return `${num(value, Math.abs(value) < 0.1 ? 2 : 1)}%`;
}

/** A limit as the rules state it: 33%, 5%, 4.5%. No trailing zero. */
export function limitPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "not available";
  return `${Number(value.toFixed(2))}%`;
}

export function croreText(value: number | null): string {
  if (value === null) return "not available";
  const digits = Math.abs(value) >= 1 ? 0 : 2;
  return `₹${num(value, digits)} crore`;
}

/** The filed rupee value, exactly as filed, grouped the Indian way. */
export function rupeeText(value: string | null): string {
  if (value === null) return "not available";
  const amount = Number(value);
  return Number.isFinite(amount) ? inr(amount, 0) : value;
}

export function shortHash(hash: string): string {
  return hash.slice(0, 12);
}

/** True when the lower and the upper reading are different figures, so both must be shown. */
export function readingsDiffer(test: ProofTest): boolean {
  const low = test.low?.pct;
  const high = test.high?.pct;
  return typeof low === "number" && typeof high === "number" && Math.abs(high - low) >= 0.005;
}

/** The sum behind a figure, so a person can redo it: top divided by bottom. */
export function sumText(figure: ProofFigure): string {
  return `${croreText(figure.numerator_cr)} ÷ ${croreText(figure.denominator_cr)} = ${percent(figure.pct)}`;
}

const ROLE_WORDS = {
  numerator: "The part being measured",
  denominator: "What it is measured against",
  derived: "Worked out from the other figures",
} as const;

const COUNTED_WORDS = {
  both: "",
  lower_only: "Counted in the lower reading only",
  upper_only: "Counted in the upper reading only",
} as const;

export function inputRole(input: ProofInput): string {
  return ROLE_WORDS[input.role];
}

export function countedWords(input: ProofInput): string {
  return COUNTED_WORDS[input.counted_in];
}

export const count = (n: number, word: string) => `${int(n)} ${word}${n === 1 ? "" : "s"}`;
