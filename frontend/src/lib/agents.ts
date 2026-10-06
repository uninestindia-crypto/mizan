import { type QueryClient, useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, errorMessage } from "./api";

// Agents are assistants a person sets up once from a form. They only read; none of them can place an order.

// ------------------------------------------------------------------------------------------- types

export interface AgentTool {
  name: string;
  label: string;
  description: string;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  instructions: string;
  tools: string[];
  steps: string[];
  needs_symbol: boolean;
  built_in: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Recipe extends Agent {
  needs_ai: boolean;
}

export interface AgentList {
  agents: Agent[];
  recipes: Recipe[];
}

export interface AgentInput {
  name: string;
  description: string;
  instructions: string;
  tools: string[];
  steps: string[];
}

export interface LookedAt {
  label: string;
  summary: string;
  ok: boolean;
}

export interface RunStep {
  number: number;
  text: string;
  reply: string;
  looked_at: LookedAt[];
  error: string | null;
}

export interface Proposal {
  kind: "navigate" | "second_opinion";
  label: string;
  path: string | null;
  symbol: string | null;
}

export interface RunResult {
  name: string;
  symbol: string | null;
  steps: RunStep[];
  proposals: Proposal[];
  model: string | null;
  completed: boolean;
  note: string | null;
}

export type RunOutcome = { ok: true; result: RunResult } | { ok: false; message: string };

// ----------------------------------------------------------------------------------------- loading

const LIST_KEY = ["copilot-agents"] as const;
const TOOLS_KEY = ["copilot-tools"] as const;
const outcomeKey = (agentId: string) => ["copilot-agent-outcome", agentId] as const;
const runKey = (agentId: string) => ["copilot-agent-run", agentId] as const;
const agentPath = (id: string) => `/api/v2/copilot/agents/${encodeURIComponent(id)}`;

export function useAgentTools() {
  return useQuery({
    queryKey: TOOLS_KEY,
    queryFn: async () => (await api<{ tools: AgentTool[] }>("/api/v2/copilot/tools")).tools,
    staleTime: 5 * 60_000,
  });
}

export function useAgentList() {
  return useQuery({ queryKey: LIST_KEY, queryFn: () => api<AgentList>("/api/v2/copilot/agents") });
}

const post = (agentId: string, symbol: string | null) =>
  api<RunResult>(`${agentPath(agentId)}/run`, "POST", symbol ? { symbol } : {});

/** Creates the agent when `id` is null, otherwise replaces that agent. */
export function useSaveAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string | null; input: AgentInput }) =>
      id ? api<Agent>(agentPath(id), "PUT", input) : api<Agent>("/api/v2/copilot/agents", "POST", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

function afterDelete(qc: QueryClient, id: string): Promise<void> {
  qc.removeQueries({ queryKey: outcomeKey(id) });
  return qc.invalidateQueries({ queryKey: LIST_KEY });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<{ deleted: boolean }>(agentPath(id), "DELETE"),
    onSuccess: (_done, id) => afterDelete(qc, id),
  });
}

/**
 * Runs an agent (this can take a minute). The outcome is kept in the query cache by the mutation itself, so a person
 * who leaves the screen and comes back finds the answer, or finds it still running.
 */
export function useAgentRun(agentId: string) {
  const qc = useQueryClient();
  const keep = (outcome: RunOutcome) => qc.setQueryData(outcomeKey(agentId), outcome);
  const start = useMutation({
    mutationKey: runKey(agentId),
    mutationFn: (symbol: string | null) => post(agentId, symbol),
    onSuccess: (result) => keep({ ok: true, result }),
    onError: (error) => keep({ ok: false, message: errorMessage(error) }),
  });
  const outcome = useQuery<RunOutcome | null>({
    queryKey: outcomeKey(agentId),
    queryFn: () => null,
    enabled: false,
    staleTime: Infinity,
    gcTime: 30 * 60_000,
  });
  const running = useIsMutating({ mutationKey: runKey(agentId) }) > 0;
  return { run: (symbol: string | null) => start.mutate(symbol), running, outcome: outcome.data ?? null };
}

// ----------------------------------------------------------------------------------------- the form

export interface Problem {
  field: string;
  message: string;
}

export const FORM_FIELDS = ["name", "description", "instructions", "tools", "steps"] as const;
export type FormField = (typeof FORM_FIELDS)[number];

/** The same limits the engine enforces, so most mistakes are caught before anything is sent. */
export const LIMITS = { steps: 8, name: 60, description: 200, instructions: 1500, step: 500 } as const;

export function blankForm(): AgentInput {
  return { name: "", description: "", instructions: "", tools: [], steps: [""] };
}

/** A form filled from an agent. A copy gets a new name so saving it never replaces the original. */
export function formFromAgent(agent: Agent, copy: boolean): AgentInput {
  const name = copy ? `My copy of ${agent.name}` : agent.name;
  return {
    name: name.slice(0, LIMITS.name),
    description: agent.description,
    instructions: agent.instructions,
    tools: [...agent.tools],
    steps: agent.steps.length > 0 ? [...agent.steps] : [""],
  };
}

/** What is sent to the engine: the text trimmed, the steps exactly as many as were written. */
export function toInput(form: AgentInput): AgentInput {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    instructions: form.instructions.trim(),
    tools: [...form.tools],
    steps: form.steps.map((step) => step.trim()),
  };
}

/** Which agent the form is for: null when saving makes a new one. */
export interface FormTarget {
  id: string | null;
  heading: string;
  initial: AgentInput;
}

export const newTarget = (): FormTarget => ({ id: null, heading: "New agent", initial: blankForm() });

export const editTarget = (agent: Agent): FormTarget => ({
  id: agent.id,
  heading: `Edit ${agent.name}`,
  initial: formFromAgent(agent, false),
});

/** Saving a copy always makes a new agent of the person's own; a ready-made one is never changed. */
export const copyTarget = (agent: Agent): FormTarget => ({
  id: null,
  heading: `Your copy of ${agent.name}`,
  initial: formFromAgent(agent, true),
});

export function isDirty(form: AgentInput, initial: AgentInput): boolean {
  const same = (a: string[], b: string[]) => a.length === b.length && a.every((text, i) => text === b[i]);
  return !(
    form.name === initial.name &&
    form.description === initial.description &&
    form.instructions === initial.instructions &&
    same([...form.tools].sort(), [...initial.tools].sort()) &&
    same(form.steps, initial.steps)
  );
}

export function toggleTool(tools: string[], name: string): string[] {
  return tools.includes(name) ? tools.filter((t) => t !== name) : [...tools, name];
}

export function addStep(steps: string[]): string[] {
  return steps.length >= LIMITS.steps ? steps : [...steps, ""];
}

export function removeStep(steps: string[], index: number): string[] {
  return steps.filter((_, i) => i !== index);
}

export function setStep(steps: string[], index: number, text: string): string[] {
  return steps.map((old, i) => (i === index ? text : old));
}

/** Swaps a step with its neighbour; at either end nothing moves. */
export function moveStep(steps: string[], index: number, direction: -1 | 1): string[] {
  const target = index + direction;
  if (index < 0 || index >= steps.length || target < 0 || target >= steps.length) return steps;
  const next = [...steps];
  [next[index], next[target]] = [next[target] as string, next[index] as string];
  return next;
}

function tooLong(field: FormField, text: string, limit: number, what: string): Problem | null {
  return text.length > limit ? { field, message: `Make the ${what} shorter (up to ${limit} letters).` } : null;
}

function stepProblem(number: number, text: string): Problem | null {
  const problem = (message: string): Problem => ({ field: "steps", message });
  if (!text.trim()) return problem(`Step ${number} is empty. Write what to do, or remove the step.`);
  if (text.length > LIMITS.step) return problem(`Step ${number} is too long (up to ${LIMITS.step} letters).`);
  const other = [...text.matchAll(/\{([^{}]*)\}/g)].map((m) => m[1]).find((name) => name !== "symbol");
  if (other === undefined) return null;
  return problem(`Step ${number} uses {${other}}. The only fill-in you can use is {symbol}.`);
}

const NO_STEPS = "Add at least one step, for example: Check {symbol} against the halal screener.";

function stepProblems(steps: string[]): Problem[] {
  if (steps.length === 0) return [{ field: "steps", message: NO_STEPS }];
  if (steps.length > LIMITS.steps) return [{ field: "steps", message: `Use at most ${LIMITS.steps} steps.` }];
  return steps.map((text, i) => stepProblem(i + 1, text)).filter((p): p is Problem => p !== null);
}

/** What the person should fix before anything is sent. The engine checks again and may add more. */
export function validateForm(form: AgentInput): Problem[] {
  const name = form.name.trim()
    ? tooLong("name", form.name.trim(), LIMITS.name, "name")
    : { field: "name", message: "Give your agent a name." };
  const text = [
    name,
    tooLong("description", form.description, LIMITS.description, "description"),
    tooLong("instructions", form.instructions, LIMITS.instructions, "instructions"),
  ];
  const noTools = { field: "tools", message: "Tick at least one thing this agent may look at." };
  const tools: Problem[] = form.tools.length === 0 ? [noTools] : [];
  return [...text.filter((p): p is Problem => p !== null), ...stepProblems(form.steps), ...tools];
}

/** Does one of the messages point at this step? The engine words them as "Step 2 is empty." and so on. */
export function stepHasProblem(messages: string[], number: number): boolean {
  return messages.some((message) => message.startsWith(`Step ${number} `));
}

/** Messages by field, each exactly as written. A field the form does not have goes under `other`. */
export function groupProblems(problems: Problem[]): Record<FormField | "other", string[]> {
  const grouped: Record<FormField | "other", string[]> = {
    name: [],
    description: [],
    instructions: [],
    tools: [],
    steps: [],
    other: [],
  };
  for (const { field, message } of problems) {
    const known = (FORM_FIELDS as readonly string[]).includes(field);
    grouped[known ? (field as FormField) : "other"].push(message);
  }
  return grouped;
}

function isProblem(item: unknown): item is Problem {
  if (typeof item !== "object" || item === null) return false;
  const { field, message } = item as Partial<Problem>;
  return typeof field === "string" && typeof message === "string";
}

/** The engine's list of things to fix (HTTP 422), or null when the error is some other kind. */
export function problemsFromError(error: unknown): Problem[] | null {
  if (!(error instanceof ApiError) || error.status !== 422) return null;
  const list = (error.details as { problems?: unknown } | null)?.problems;
  const found = Array.isArray(list) ? list.filter(isProblem) : [];
  return found.length > 0 ? found : null;
}

export function usesSymbol(form: AgentInput): boolean {
  return [...form.steps, form.instructions].some((text) => text.includes("{symbol}"));
}

/** The plain labels of the things an agent may look at. A name the screen has no label for is left out. */
export function toolLabels(names: string[], tools: AgentTool[] | undefined): string[] {
  const labels = new Map((tools ?? []).map((tool) => [tool.name, tool.label]));
  return names.flatMap((name) => labels.get(name) ?? []);
}

// ------------------------------------------------------------------------------ result buttons

export type ProposalAction = { type: "navigate"; path: string } | { type: "second_opinion"; symbol: string };

/** A path inside this app (starting with one slash). Anything else, such as a web address, is never followed. */
export function appPath(path: string | null): string | null {
  return path && /^\/(?![/\\])[^\s\u0000-\u001f\u007f\\]*$/.test(path) ? path : null;
}

/** What a result button does, or null when the button is not safe or not complete (then it is not shown). */
export function proposalAction(proposal: Proposal): ProposalAction | null {
  if (proposal.kind === "navigate") {
    const path = appPath(proposal.path);
    return path ? { type: "navigate", path } : null;
  }
  const symbol = normalizeSymbol(proposal.symbol ?? "");
  const usable = proposal.kind === "second_opinion" && symbol !== "" && symbolProblem(symbol) === null;
  return usable ? { type: "second_opinion", symbol } : null;
}

/** The fixed contract with the Second opinion window, which listens for this event on the page. */
export const SECOND_OPINION_EVENT = "quantos:second-opinion";

export function requestSecondOpinion(symbol: string): void {
  window.dispatchEvent(new CustomEvent(SECOND_OPINION_EVENT, { detail: { symbol } }));
}

// -------------------------------------------------------------------------------------- the stock

/** The engine's own rule for a stock symbol. */
const VALID_SYMBOL = /^[A-Z0-9&-]{1,15}$/;

export const SYMBOL_HINT = "Type the stock's NSE symbol, for example TCS.";

/** Upper-case with no spaces, the way NSE symbols are written. */
export function normalizeSymbol(text: string): string {
  return text.replace(/\s+/g, "").toUpperCase();
}

export function symbolProblem(text: string): string | null {
  const symbol = normalizeSymbol(text);
  if (!symbol) return SYMBOL_HINT;
  return VALID_SYMBOL.test(symbol) ? null : "Use letters and numbers only, for example TCS or M&M.";
}
