// A realistic finished run, shaped exactly as the contract describes, for tests of the result view.

import type {
  Dissent,
  HalalBlock,
  HalalRatio,
  ModelVerdict,
  Opinion,
  VerifyFacts,
  VerifyResult,
} from "../../lib/copilot";

export function opinion(over: Partial<Opinion> = {}): Opinion {
  return {
    provider: "openai",
    model: "gpt-x",
    arm: "blind",
    ok: true,
    reading: "MIXED",
    news_tone: "NEUTRAL",
    reasons: ["Steady earnings history"],
    risks: ["Slowing demand abroad"],
    missing: ["No recent filing in the facts"],
    removed: 0,
    error: null,
    ...over,
  };
}

const NOT_ACCEPTED = "The key was not accepted. Check it in Settings, then Accounts and keys.";

function verdict(blind: Opinion, over: Partial<ModelVerdict> = {}): ModelVerdict {
  return { blind, informed: null, recheck: null, stable: null, shift: null, ...over };
}

function sampleVerdicts(): ModelVerdict[] {
  const failed = { ok: false, reading: null, error: NOT_ACCEPTED, reasons: [], risks: [], missing: [] };
  return [
    verdict(opinion(), {
      informed: opinion({ arm: "informed", reading: "POSITIVE" }),
      recheck: opinion({ arm: "recheck", reading: "POSITIVE" }),
      stable: false,
      shift: 1,
    }),
    verdict(
      opinion({
        provider: "anthropic",
        model: "claude-x",
        reading: "POSITIVE",
        reasons: ["Strong order book"],
        risks: ["Currency swings"],
      }),
      { recheck: opinion({ provider: "anthropic", arm: "recheck", reading: "POSITIVE" }), stable: true },
    ),
    verdict(opinion({ provider: "gemini", model: "gem-x", reasons: ["Valuation is fair"] })),
    verdict(opinion({ provider: "mistral", model: "mis-x", ...failed })),
  ];
}

const DEBT: HalalRatio = { name: "Debt ratio", actual_pct: 12.345, threshold_pct: 30, within_limit: true };
const CASH: HalalRatio = {
  name: "Cash ratio",
  actual_pct: 29,
  threshold_pct: 30,
  within_limit: true,
  in_warning_band: true,
};

const DISSENTER: Dissent = {
  provider: "anthropic",
  model: "claude-x",
  reading: "POSITIVE",
  reasons: ["Strong order book"],
  risks: ["Currency swings"],
};

function sampleHalal(): HalalBlock {
  const aaoifi = { standard: "AAOIFI", status: "COMPLIANT", summary: "All ratios within limits", ratios: [DEBT] };
  const tasis = { standard: "TASIS", status: "QUESTIONABLE", summary: null, ratios: [CASH] };
  return {
    covered: true,
    data_status: "UNVERIFIED_SAMPLE",
    data_notice: "Illustrative sample figures.",
    standards: [aaoifi, tasis],
    disclaimer: "A screening aid, not a religious ruling.",
  };
}

function sampleFacts(): VerifyFacts {
  return {
    symbol: "TCS",
    sections: [
      { title: "Price history facts", summary: "Up 12% in a year.", from_outside: false },
      { title: "Recent headlines", summary: "Three headlines.", from_outside: true },
    ],
    unavailable: ["Live price"],
  };
}

export function sampleResult(over: Partial<VerifyResult> = {}): VerifyResult {
  return {
    symbol: "TCS",
    headline: "2 of 3 models that answered read the evidence as MIXED.",
    consensus: "MAJORITY",
    reading: "MIXED",
    asked: 4,
    answered: 3,
    counts: { MIXED: 2, POSITIVE: 1 },
    news_tones: { NEUTRAL: 2, POSITIVE: 1 },
    verdicts: sampleVerdicts(),
    dissent: [DISSENTER],
    notes: ["1 of 4 model(s) could not answer. Their reason is listed below.", "A second note.", "A third note."],
    halal: sampleHalal(),
    facts: sampleFacts(),
    disclosure: "These are opinions from AI models. They are not independent evidence.",
    ...over,
  };
}
