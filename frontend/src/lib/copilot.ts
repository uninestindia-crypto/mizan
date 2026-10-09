// The Copilot and the Second opinion: the shapes the screens exchange with the engine
// (agent_context/decisions/20261006-copilot-api-contract.md) and the small pure helpers both screens share.

import { useQuery } from "@tanstack/react-query";
import { api, ApiError, errorMessage } from "./api";

// ----------------------------------------------------------------------------------------------- chat shapes

export type ChatRole = "user" | "assistant";

export interface ChatTurn {
  role: ChatRole;
  content: string;
}

export interface ChatStep {
  label: string;
  summary: string;
  ok: boolean;
}

export interface ChatProposal {
  kind: "navigate" | "second_opinion";
  label: string;
  path: string | null;
  symbol: string | null;
}

export interface ChatReply {
  reply: string;
  steps: ChatStep[];
  proposals: ChatProposal[];
  mode: "ai" | "built_in";
  provider: string | null;
  model: string | null;
  error: string | null;
}

export interface ChatRequest {
  messages: ChatTurn[];
  page: string | null;
  agent_id: string | null;
}

// ------------------------------------------------------------------------------------- second opinion shapes

export interface ProviderOption {
  id: string;
  label: string;
  ready: boolean;
}

export interface VerifyRequest {
  symbol: string;
  providers: string[];
  recheck: boolean;
  pick_note?: string;
  chained?: boolean;
}

export interface Opinion {
  provider: string;
  model: string | null;
  arm: string;
  ok: boolean;
  reading: string | null;
  news_tone: string | null;
  reasons: string[];
  risks: string[];
  missing: string[];
  removed: number;
  error: string | null;
}

export interface ModelVerdict {
  blind: Opinion;
  informed: Opinion | null;
  recheck: Opinion | null;
  stable: boolean | null;
  shift: number | null;
}

export interface Dissent {
  provider: string;
  model: string | null;
  reading: string | null;
  reasons: string[];
  risks: string[];
}

export interface HalalRatio {
  name: string;
  actual_pct: number | null;
  threshold_pct: number | null;
  within_limit?: boolean;
  in_warning_band?: boolean;
}

export interface HalalStandard {
  standard: string;
  status: string;
  summary?: string | null;
  ratios?: HalalRatio[];
}

/** The screener's own answer, carried through untouched. The AI models never produce it. */
export interface HalalBlock {
  covered: boolean;
  data_status?: string | null;
  data_notice?: string | null;
  message?: string | null;
  company?: string | null;
  standards?: HalalStandard[];
  standards_disagree?: boolean;
  disagreement_reason?: string | null;
  purification_ratio_pct?: number | string | null;
  disclaimer?: string | null;
}

export interface FactSection {
  title: string;
  summary: string;
  from_outside: boolean;
}

export interface VerifyFacts {
  symbol?: string;
  sections: FactSection[];
  unavailable: string[];
}

export interface VerifyResult {
  symbol: string;
  headline: string;
  consensus: string;
  reading: string | null;
  asked: number;
  answered: number;
  counts: Record<string, number>;
  news_tones: Record<string, number>;
  verdicts: ModelVerdict[];
  dissent: Dissent[];
  notes: string[];
  halal: HalalBlock | null;
  facts: VerifyFacts | null;
  disclosure: string;
}

export interface VerifyProgress {
  done: number;
  total: number;
}

export interface VerifyPoll {
  status: "running" | "done" | "failed" | "cancelled";
  progress: VerifyProgress | null;
  result: VerifyResult | null;
  error: string | null;
}

// -------------------------------------------------------------------------------------------------- engine calls

async function listModels(): Promise<ProviderOption[]> {
  const data = await api<{ models?: ProviderOption[] }>("/api/v2/copilot/models");
  return (data.models ?? [])
    .filter((m) => typeof m?.id === "string")
    .map((m) => ({ ...m, label: m.label || m.id, ready: m.ready === true }));
}

export const copilotApi = {
  chat: (body: ChatRequest) => api<Partial<ChatReply>>("/api/v2/copilot/chat", "POST", body),
  models: listModels,
  startVerify: (body: VerifyRequest) => api<{ job_id: string }>("/api/v2/copilot/verify", "POST", body),
  pollVerify: (jobId: string) => api<VerifyPoll>(`/api/v2/copilot/verify/${encodeURIComponent(jobId)}`),
  /** Asks the engine to stop a run for good. A caller that does not need the answer may ignore a failure. */
  cancelVerify: (jobId: string) =>
    api<{ cancelled?: boolean }>(`/api/v2/copilot/verify/${encodeURIComponent(jobId)}`, "DELETE"),
};

export const copilotKeys = { models: ["copilot", "models"] as const };

/** The AI providers the person can pick for a second opinion. Always asks again when the dialog opens. */
export function useCopilotModels(enabled = true) {
  return useQuery({ queryKey: copilotKeys.models, queryFn: copilotApi.models, enabled, staleTime: 0 });
}

// ---------------------------------------------------------------------------------------------- request building

/** The engine reads this many recent turns; sending more only makes the request larger. */
export const HISTORY_LIMIT = 8;
/** The most the engine accepts for one turn. A person may type that much, and a long reply can approach it. */
export const MAX_MESSAGE_CHARS = 4000;
/** The counter appears once a message is longer than this. */
const COUNT_FROM = 3500;
const MAX_PICK_NOTE_CHARS = 300;
const MAX_PROVIDERS = 6;

const SAFE_APP_PATH = /^\/(?!\/)[^\s\\]{0,199}$/;
/** The same shape the engine accepts for a stock symbol. */
const SYMBOL = /^[A-Za-z0-9&-]{1,15}$/;

/** A path inside this app: it starts with one slash and carries no address of another site. */
export function isSafeAppPath(path: unknown): path is string {
  return typeof path === "string" && SAFE_APP_PATH.test(path);
}

export function isValidSymbol(symbol: unknown): symbol is string {
  return typeof symbol === "string" && SYMBOL.test(symbol.trim());
}

/** The last few turns, starting with something the person said, and the screen they are on. */
export function buildChatRequest(turns: readonly ChatTurn[], page: string | null): ChatRequest {
  const recent = turns
    .filter((t) => t.content.trim() !== "")
    .slice(-HISTORY_LIMIT)
    .map((t): ChatTurn => ({ role: t.role, content: t.content.slice(0, MAX_MESSAGE_CHARS) }));
  while (recent.length > 0 && recent[0]?.role !== "user") recent.shift();
  return { messages: recent, page: isSafeAppPath(page) ? page : null, agent_id: null };
}

export function buildVerifyRequest(
  symbol: string,
  providers: readonly string[],
  pickNote: string | null,
  chained?: boolean,
): VerifyRequest {
  const note = pickNote?.trim().slice(0, MAX_PICK_NOTE_CHARS);
  const modelList = chained ? [...providers] : providers.slice(0, MAX_PROVIDERS);
  const base: VerifyRequest = {
    symbol: symbol.trim().toUpperCase(),
    providers: modelList,
    recheck: true,
  };
  if (chained === false) {
    base.chained = false;
  }
  return note ? { ...base, pick_note: note } : base;
}

/** The ready providers to tick at first: up to three, in the order the engine listed them. */
export function defaultSelection(models: readonly ProviderOption[], limit = 3): string[] {
  return models.filter((m) => m.ready).slice(0, limit).map((m) => m.id);
}

const thousands = (n: number) => n.toLocaleString("en-IN");

/** A quiet counter near the limit and a plain sentence at it; nothing for an ordinary message. */
export function lengthNote(count: number): string | null {
  if (count >= MAX_MESSAGE_CHARS) {
    return `You have reached the limit of ${thousands(MAX_MESSAGE_CHARS)} characters. Shorten the message to add more.`;
  }
  return count > COUNT_FROM ? `${thousands(count)} of ${thousands(MAX_MESSAGE_CHARS)}` : null;
}

// ------------------------------------------------------------------------------------------------ plain wording

const PROVIDER_NAMES: Record<string, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI",
  gemini: "Google Gemini",
  groq: "Groq",
  deepseek: "DeepSeek",
  mistral: "Mistral",
  openrouter: "OpenRouter",
};

/** The company's name for an AI provider id, or null when it is not one the screen can name. Never a model id. */
export function friendlyProvider(id: string | null | undefined): string | null {
  return id ? (PROVIDER_NAMES[id] ?? null) : null;
}

export const SOMETHING_WRONG = "Something went wrong. Please try again in a moment.";
export const OFFLINE_MESSAGE = "QuantOS is not responding. Close it and open it again, then try once more.";

/** A request the engine refused comes back with one plain sentence of its own. A crash does not. */
function isRefusal(error: unknown): error is ApiError {
  const refused = error instanceof ApiError && error.status >= 400 && error.status < 500;
  return refused && error.code !== "CSRF_UNAVAILABLE" && !error.code.startsWith("HTTP_");
}

/** The engine's own sentence for a request it refused, such as a message it cannot read, or null. */
export function refusalSentence(error: unknown): string | null {
  return isRefusal(error) ? errorMessage(error).trim() || null : null;
}

/** What to tell a person about a failed call: the engine's sentence when it sent one, never a raw error. */
export function plainFailure(error: unknown): string {
  if (error instanceof ApiError && error.code === "ENGINE_OFFLINE") return OFFLINE_MESSAGE;
  return refusalSentence(error) ?? SOMETHING_WRONG;
}

// -------------------------------------------------------------------------------------------- reply cleaning

export const EMPTY_REPLY = "I do not have an answer for that. Try asking in a different way.";

function cleanProposal(raw: Partial<ChatProposal> | null | undefined): ChatProposal | null {
  if (!raw || typeof raw !== "object") return null;
  const label = typeof raw.label === "string" ? raw.label.trim() : "";
  if (raw.kind === "navigate" && isSafeAppPath(raw.path)) {
    const symbol = isValidSymbol(raw.symbol) ? raw.symbol : null;
    return { kind: "navigate", label: label || "Open", path: raw.path, symbol };
  }
  if (raw.kind === "second_opinion" && isValidSymbol(raw.symbol)) {
    const symbol = raw.symbol.trim().toUpperCase();
    return { kind: "second_opinion", label: label || `Get a second opinion on ${symbol}`, path: null, symbol };
  }
  return null;
}

function cleanSteps(raw: unknown): ChatStep[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((s): s is Partial<ChatStep> => !!s && typeof s === "object" && typeof (s as ChatStep).label === "string")
    .map((s) => ({
      label: s.label ?? "",
      summary: typeof s.summary === "string" ? s.summary : "",
      ok: s.ok !== false,
    }));
}

/** Whatever the engine sent, as a reply the screen can show without checking every field. */
export function normaliseReply(raw: Partial<ChatReply> | null | undefined): ChatReply {
  const offered = Array.isArray(raw?.proposals) ? raw.proposals : [];
  const proposals = offered.map(cleanProposal).filter((p): p is ChatProposal => p !== null);
  return {
    reply: typeof raw?.reply === "string" && raw.reply.trim() ? raw.reply : EMPTY_REPLY,
    steps: cleanSteps(raw?.steps),
    proposals: proposals.slice(0, 6),
    mode: raw?.mode === "ai" ? "ai" : "built_in",
    provider: typeof raw?.provider === "string" ? raw.provider : null,
    model: typeof raw?.model === "string" ? raw.model : null,
    error: typeof raw?.error === "string" && raw.error.trim() ? raw.error : null,
  };
}

// --------------------------------------------------------------------------------- opening the Second opinion

/** The name and detail shape are shared with the Agents screen: `{ detail: { symbol } }`. */
export const SECOND_OPINION_EVENT = "quantos:second-opinion";

export interface SecondOpinionRequest {
  symbol: string;
  pickNote?: string;
}

export function openSecondOpinion(symbol: string, pickNote?: string): void {
  const detail = pickNote ? { symbol, pickNote } : { symbol };
  window.dispatchEvent(new CustomEvent(SECOND_OPINION_EVENT, { detail }));
}

/** What a Second opinion event asks for, or null when its detail is not a usable stock symbol. */
export function readSecondOpinionRequest(event: Event): SecondOpinionRequest | null {
  const detail = (event as CustomEvent<{ symbol?: unknown; pickNote?: unknown } | null>).detail;
  if (!detail || !isValidSymbol(detail.symbol)) return null;
  const symbol = detail.symbol.trim().toUpperCase();
  const note = typeof detail.pickNote === "string" ? detail.pickNote.trim() : "";
  return note ? { symbol, pickNote: note } : { symbol };
}
