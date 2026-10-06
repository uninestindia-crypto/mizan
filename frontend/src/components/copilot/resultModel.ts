// What a finished second opinion says, as plain data the screen can draw without deciding anything itself.
// Every choice of words lives here so it can be tested: readings are described, never scored, coloured or advised.

import type {
  Dissent,
  HalalBlock,
  HalalStandard,
  ModelVerdict,
  Opinion,
  ProviderOption,
  VerifyFacts,
  VerifyResult,
} from "../../lib/copilot";

/** Shown whenever the engine sends no disclosure of its own. The disclosure is never left out. */
export const FALLBACK_DISCLOSURE =
  "These are opinions from AI models that read the same facts. They are not independent evidence: models trained on " +
  "similar text tend to agree, and none of them can see the live market. Use this to decide what to check yourself, " +
  "not as a reason to trade.";

export const HALAL_HEADING = "Halal screening (from the platform's screener, not from the AI models)";

const READING_WORDS: Record<string, string> = {
  POSITIVE: "Looks positive",
  MIXED: "Mixed",
  NEGATIVE: "Looks negative",
  UNCLEAR: "Not clear",
};
const READING_ORDER = ["POSITIVE", "MIXED", "NEGATIVE", "UNCLEAR"];

const CONSENSUS_WORDS: Record<string, string> = {
  AGREE: "The models agree",
  MAJORITY: "Most of the models agree",
  SPLIT: "The models are split",
  SINGLE: "Only one model answered",
  NONE: "No model could answer",
};

const TONE_WORDS: Record<string, string> = {
  POSITIVE: "positive",
  NEUTRAL: "neutral",
  NEGATIVE: "negative",
  MIXED: "mixed",
  NONE: "no headlines",
};

const STANDARD_STATUS_WORDS: Record<string, string> = {
  COMPLIANT: "Passes",
  NON_COMPLIANT: "Does not pass",
  QUESTIONABLE: "Questionable",
};

const DATA_STATUS_WORDS: Record<string, string> = {
  UNVERIFIED_SAMPLE: "Unverified sample data",
};

function sentenceCase(code: string): string {
  const text = code.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** How the evidence reads, in words. These describe a reading; they are never advice. */
export function readingWords(reading: string | null | undefined): string {
  return reading ? (READING_WORDS[reading] ?? "Not clear") : "No reading";
}

export function consensusWords(consensus: string): string {
  return CONSENSUS_WORDS[consensus] ?? "The models did not agree on a reading";
}

/** The company's name for a provider, or its id made readable when the list does not know it. */
export function providerName(id: string, models: readonly ProviderOption[]): string {
  return models.find((m) => m.id === id)?.label ?? sentenceCase(id);
}

const countOf = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

// ------------------------------------------------------------------------------------------------ one model

export interface ModelView {
  key: string;
  name: string;
  modelName: string | null;
  answered: boolean;
  reading: string | null;
  error: string | null;
  newsTone: string | null;
  reasons: string[];
  risks: string[];
  missing: string[];
  stability: string | null;
  anchoring: string | null;
  informed: string | null;
  recheckProblem: string | null;
}

function stabilityLine(verdict: ModelVerdict): string | null {
  if (verdict.stable === false) {
    return "Changed its mind when the same facts were shown in a different order, so treat this reading as weak.";
  }
  return verdict.stable === true ? "Gave the same reading when the same facts were shown in a different order." : null;
}

function anchoringLine(verdict: ModelVerdict): string | null {
  const shift = verdict.shift;
  if (shift === null || shift === undefined) return null;
  if (shift > 0) return "Read the stock more favourably after being told the platform's own pick. That is anchoring.";
  if (shift < 0) return "Read the stock less favourably after being told the platform's own pick.";
  return "Its reading did not change when it was told the platform's own pick.";
}

function informedLine(opinion: Opinion | null): string | null {
  if (!opinion) return null;
  if (!opinion.ok) return "When told the platform's own pick, it could not answer.";
  return `When told the platform's own pick, it read the evidence as: ${readingWords(opinion.reading)}.`;
}

function recheckProblem(opinion: Opinion | null): string | null {
  if (!opinion || opinion.ok) return null;
  return `Its second pass, with the facts in a different order, could not answer. ${opinion.error ?? ""}`.trim();
}

function tonePhrase(tone: string | null): string | null {
  return tone && TONE_WORDS[tone] ? `Read the news headlines as ${TONE_WORDS[tone]}.` : null;
}

function modelView(verdict: ModelVerdict, index: number, models: readonly ProviderOption[]): ModelView {
  const blind = verdict.blind;
  const answered = blind.ok;
  return {
    key: `${blind.provider}-${blind.model ?? ""}-${index}`,
    name: providerName(blind.provider, models),
    modelName: blind.model,
    answered,
    reading: answered ? blind.reading : null,
    error: answered ? null : blind.error?.trim() || "No reason was given.",
    newsTone: answered ? tonePhrase(blind.news_tone) : null,
    reasons: answered ? blind.reasons : [],
    risks: answered ? blind.risks : [],
    missing: answered ? blind.missing : [],
    stability: answered ? stabilityLine(verdict) : null,
    anchoring: answered ? anchoringLine(verdict) : null,
    informed: informedLine(verdict.informed),
    recheckProblem: answered ? recheckProblem(verdict.recheck) : null,
  };
}

// --------------------------------------------------------------------------------------------- dissenters

export interface DissentView {
  key: string;
  name: string;
  modelName: string | null;
  reading: string | null;
  reasons: string[];
  risks: string[];
}

function dissentView(entry: Dissent, index: number, models: readonly ProviderOption[]): DissentView {
  return {
    key: `${entry.provider}-${entry.model ?? ""}-${index}`,
    name: providerName(entry.provider, models),
    modelName: entry.model,
    reading: entry.reading,
    reasons: entry.reasons ?? [],
    risks: entry.risks ?? [],
  };
}

// ---------------------------------------------------------------------------------------------- the screener

export interface RatioView {
  name: string;
  line: string;
}

export interface StandardView {
  name: string;
  status: string;
  summary: string | null;
  ratios: RatioView[];
}

export interface HalalView {
  heading: string;
  covered: boolean;
  message: string | null;
  dataStatus: string;
  dataNotice: string | null;
  standards: StandardView[];
  disagreement: string | null;
  purification: string | null;
  disclaimer: string | null;
}

const percent = (n: number) => `${(Math.round(n * 100) / 100).toString()}%`;

function ratioLine(ratio: NonNullable<HalalStandard["ratios"]>[number]): RatioView {
  const actual = typeof ratio.actual_pct === "number" ? percent(ratio.actual_pct) : "not available";
  const limit = typeof ratio.threshold_pct === "number" ? `, limit ${percent(ratio.threshold_pct)}` : "";
  const state = ratio.within_limit === false ? ". Over the limit" : ratio.in_warning_band ? ". Close to the limit" : "";
  return { name: ratio.name, line: `${actual}${limit}${state}` };
}

function standardView(standard: HalalStandard): StandardView {
  return {
    name: standard.standard,
    status: STANDARD_STATUS_WORDS[standard.status] ?? sentenceCase(standard.status),
    summary: standard.summary?.trim() || null,
    ratios: (standard.ratios ?? []).map(ratioLine),
  };
}

function purificationLine(value: HalalBlock["purification_ratio_pct"]): string | null {
  if (value === null || value === undefined || value === "") return null;
  return typeof value === "number" ? percent(value) : String(value);
}

function halalView(block: HalalBlock | null): HalalView | null {
  if (!block) return null;
  const status = block.data_status ?? "";
  return {
    heading: HALAL_HEADING,
    covered: block.covered === true,
    message: block.message?.trim() || null,
    dataStatus: status ? (DATA_STATUS_WORDS[status] ?? sentenceCase(status)) : "Data status not given",
    dataNotice: block.data_notice?.trim() || null,
    standards: (block.standards ?? []).map(standardView),
    disagreement: block.standards_disagree ? block.disagreement_reason?.trim() || "The two standards disagree." : null,
    purification: purificationLine(block.purification_ratio_pct),
    disclaimer: block.disclaimer?.trim() || null,
  };
}

// ------------------------------------------------------------------------------------------------- the result

export interface FactSectionView {
  title: string;
  summary: string;
  fromOutside: boolean;
}

export interface ResultView {
  symbol: string;
  headline: string;
  consensus: string;
  sharedReading: string | null;
  answeredLine: string;
  counts: { reading: string; count: number }[];
  newsTones: string | null;
  models: ModelView[];
  dissent: DissentView[];
  noDissent: boolean;
  notes: string[];
  disclosure: string;
  halal: HalalView | null;
  facts: { sections: FactSectionView[]; unavailable: string[] };
}

function countRows(counts: Record<string, number>): { reading: string; count: number }[] {
  const known = READING_ORDER.filter((r) => (counts[r] ?? 0) > 0);
  const other = Object.keys(counts).filter((r) => !READING_ORDER.includes(r) && (counts[r] ?? 0) > 0);
  return [...known, ...other].map((reading) => ({ reading, count: counts[reading] ?? 0 }));
}

function toneSummary(tones: Record<string, number>): string | null {
  const parts = Object.entries(tones)
    .filter(([tone, n]) => TONE_WORDS[tone] && n > 0)
    .map(([tone, n]) => `${TONE_WORDS[tone]}: ${n}`);
  return parts.length > 0 ? `How the models read the news headlines: ${parts.join(", ")}.` : null;
}

function factsView(facts: VerifyFacts | null): ResultView["facts"] {
  const sections = (facts?.sections ?? []).map((s) => ({
    title: s.title,
    summary: s.summary,
    fromOutside: s.from_outside === true,
  }));
  return { sections, unavailable: [...(facts?.unavailable ?? [])] };
}

export function buildResultView(result: VerifyResult, models: readonly ProviderOption[] = []): ResultView {
  const dissent = (result.dissent ?? []).map((d, i) => dissentView(d, i, models));
  return {
    symbol: result.symbol,
    headline: result.headline,
    consensus: consensusWords(result.consensus),
    sharedReading: result.reading ? readingWords(result.reading) : null,
    answeredLine: `${result.answered} of ${countOf(result.asked, "model")} answered.`,
    counts: countRows(result.counts ?? {}),
    newsTones: toneSummary(result.news_tones ?? {}),
    models: (result.verdicts ?? []).map((v, i) => modelView(v, i, models)),
    dissent,
    noDissent: dissent.length === 0 && result.consensus === "AGREE",
    notes: [...(result.notes ?? [])],
    disclosure: result.disclosure?.trim() || FALLBACK_DISCLOSURE,
    halal: halalView(result.halal ?? null),
    facts: factsView(result.facts ?? null),
  };
}
