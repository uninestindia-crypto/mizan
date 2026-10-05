import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  AiTool,
  Bars,
  CostsResult,
  LabResult,
  LabRunSummary,
  Overview,
  PaperBook,
  PaperBookDetail,
  PaperBookInput,
  PaperBookSummary,
  PaperUpdates,
  PayoffResult,
  Portfolio,
  PositionSizeResult,
  Screener,
  SearchResult,
  Secret,
  Settings,
  Status,
  StockProfile,
  Templates,
  UpdateInfo,
  WatchRow,
  ChangelogEntry,
} from "./types";

const MARKET = 5 * 60_000;

export const keys = {
  status: ["status"] as const,
  overview: ["overview"] as const,
  screener: (u: string) => ["screener", u] as const,
  search: (q: string) => ["search", q] as const,
  bars: (s: string) => ["bars", s] as const,
  stock: (s: string) => ["stock", s] as const,
  templates: ["templates"] as const,
  runs: ["runs"] as const,
  run: (id: string) => ["run", id] as const,
  portfolio: ["portfolio"] as const,
  watchlist: ["watchlist"] as const,
  paper: ["paper"] as const,
  paperMine: ["paper-mine"] as const,
  paperUpdates: ["paper-updates"] as const,
  paperBook: (id: string) => ["paper-book", id] as const,
  secrets: ["secrets"] as const,
  aiTools: ["ai-tools"] as const,
};

export function useStatus() {
  return useQuery({
    queryKey: keys.status,
    queryFn: () => api<Status>("/api/v2/status"),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.index.job.state === "RUNNING") return 800;
      if (data?.data_folder.scan === "RUNNING" || data?.download.state === "RUNNING") return 1_000;
      return 30_000;
    },
  });
}

export function useOverview(enabled = true) {
  return useQuery({ queryKey: keys.overview, queryFn: () => api<Overview>("/api/v2/market/overview"), staleTime: MARKET, enabled });
}

export function useScreener(universe: string) {
  return useQuery({
    queryKey: keys.screener(universe),
    queryFn: () => api<Screener>(`/api/v2/market/screener?universe=${universe}`),
    staleTime: MARKET,
    placeholderData: keepPreviousData,
  });
}

export function useSearch(q: string) {
  const text = q.trim();
  return useQuery({
    queryKey: keys.search(text),
    queryFn: () => api<SearchResult[]>(`/api/v2/market/search?q=${encodeURIComponent(text)}`),
    enabled: text.length > 0,
    staleTime: MARKET,
    placeholderData: keepPreviousData,
  });
}

export function useBars(symbol: string) {
  return useQuery({ queryKey: keys.bars(symbol), queryFn: () => api<Bars>(`/api/v2/market/bars/${encodeURIComponent(symbol)}`), staleTime: MARKET });
}

export function useStock(symbol: string) {
  return useQuery({ queryKey: keys.stock(symbol), queryFn: () => api<StockProfile>(`/api/v2/stocks/${encodeURIComponent(symbol)}`), staleTime: MARKET });
}

export function useTemplates() {
  return useQuery({ queryKey: keys.templates, queryFn: () => api<Templates>("/api/v2/lab/templates") });
}

export function useLabRuns() {
  return useQuery({ queryKey: keys.runs, queryFn: () => api<LabRunSummary[]>("/api/v2/lab/runs") });
}

export function useLabRun(id: string) {
  return useQuery({ queryKey: keys.run(id), queryFn: () => api<LabResult>(`/api/v2/lab/runs/${id}`), staleTime: Infinity });
}

export function usePortfolio(enabled = true) {
  return useQuery({ queryKey: keys.portfolio, queryFn: () => api<Portfolio>("/api/v2/portfolio"), enabled });
}

export function useWatchlist(enabled = true) {
  return useQuery({ queryKey: keys.watchlist, queryFn: () => api<WatchRow[]>("/api/v2/watchlist"), enabled });
}

export function usePaperBooks() {
  return useQuery({ queryKey: keys.paper, queryFn: () => api<PaperBook[]>("/api/v2/paper/books"), refetchInterval: 60_000 });
}

export function usePaperMine(enabled = true) {
  return useQuery({
    queryKey: keys.paperMine,
    queryFn: () => api<PaperBookSummary[]>("/api/v2/paper/mine"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function usePaperUpdates(enabled = true) {
  return useQuery({
    queryKey: keys.paperUpdates,
    queryFn: () => api<PaperUpdates>("/api/v2/paper/updates"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function usePaperBook(id: string) {
  return useQuery({ queryKey: keys.paperBook(id), queryFn: () => api<PaperBookDetail>(`/api/v2/paper/mine/${id}`), refetchInterval: 30_000 });
}

export function useStartPaperBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PaperBookInput) => api<PaperBookDetail>("/api/v2/paper/mine", "POST", input),
    onSuccess: (book) => {
      qc.setQueryData(keys.paperBook(book.id), book);
      void qc.invalidateQueries({ queryKey: keys.paperMine });
    },
  });
}

export function useStopPaperBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<PaperBookDetail>(`/api/v2/paper/mine/${id}/stop`, "POST"),
    onSuccess: (book) => {
      qc.setQueryData(keys.paperBook(book.id), book);
      void qc.invalidateQueries({ queryKey: keys.paperMine });
    },
  });
}

export function useSecrets() {
  return useQuery({ queryKey: keys.secrets, queryFn: () => api<{ available: boolean; secrets: Secret[] }>("/api/v2/credentials") });
}

export function useAiTools() {
  return useQuery({ queryKey: keys.aiTools, queryFn: () => api<AiTool[]>("/api/v2/ai-tools"), staleTime: 60_000 });
}

// ---------------------------------------------------------------------------- mutations

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Record<keyof Settings, unknown>>) => api<Settings>("/api/v2/settings", "PUT", patch),
    // Returning the promise makes callers' own onSuccess run only after fresh settings have loaded,
    // so navigation that depends on them (leaving onboarding) never sees the old values.
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: keys.status }),
        qc.invalidateQueries({ queryKey: keys.portfolio }),
        qc.invalidateQueries({ queryKey: keys.paperUpdates }),
      ]);
    },
  });
}

export function useAcceptDisclaimer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<Settings>("/api/v2/settings/disclaimer", "POST"),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.status }),
  });
}

export function useSetDataFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => api<{ data_folder: string }>("/api/v2/data/folder", "POST", { path }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.status }),
  });
}

export function usePickFolder() {
  return useMutation({
    mutationFn: (body: { title?: string; initial?: string | null }) =>
      api<{ path: string | null }>("/api/v2/system/pick-folder", "POST", body),
  });
}

export function useScanForData() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ state: string }>("/api/v2/data/scan", "POST"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.status }),
  });
}

export function useStartDownload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (mode: "auto" | "full" | "update" = "auto") => api<{ started: boolean }>("/api/v2/data/download", "POST", { mode }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.status }),
  });
}

export function useCancelDownload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<unknown>("/api/v2/data/download/cancel", "POST"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.status }),
  });
}

export function useBuildIndex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ started: boolean }>("/api/v2/data/index/build", "POST"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.status }),
  });
}

export interface LabRunInput {
  template_id: string;
  params: Record<string, number | boolean>;
  scope: "stocks" | "universe";
  symbols: string[];
  universe: string | null;
  start: string | null;
  end: string | null;
  capital: string | null;
  slippage_bps: string;
}

export function useRunLab() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: LabRunInput) => api<LabResult>("/api/v2/lab/runs", "POST", input),
    onSuccess: (result) => {
      qc.setQueryData(keys.run(result.id), result);
      void qc.invalidateQueries({ queryKey: keys.runs });
      void qc.invalidateQueries({ queryKey: keys.templates });
      void qc.invalidateQueries({ queryKey: keys.status });
    },
  });
}

export function useWatchlistToggle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, add }: { symbol: string; add: boolean }) =>
      add ? api<string[]>("/api/v2/watchlist", "POST", { symbol }) : api<string[]>(`/api/v2/watchlist/${encodeURIComponent(symbol)}`, "DELETE"),
    onSuccess: (_data, { symbol }) => {
      void qc.invalidateQueries({ queryKey: keys.watchlist });
      void qc.invalidateQueries({ queryKey: keys.stock(symbol) });
    },
  });
}

export interface HoldingInput {
  symbol: string;
  quantity: number;
  avg_price: string;
  buy_date: string;
  note: string;
}

export function useSaveHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id?: number; input: HoldingInput }) =>
      id ? api("/api/v2/portfolio/holdings/" + id, "PUT", input) : api("/api/v2/portfolio/holdings", "POST", input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.portfolio });
      void qc.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}

export function useDeleteHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/api/v2/portfolio/holdings/${id}`, "DELETE"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.portfolio }),
  });
}

export function useSecretMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, value }: { name: string; value: string | null }) =>
      value === null
        ? api<{ available: boolean; secrets: Secret[] }>(`/api/v2/credentials/${name}`, "DELETE")
        : api<{ available: boolean; secrets: Secret[] }>(`/api/v2/credentials/${name}`, "PUT", { value }),
    onSuccess: (data) => qc.setQueryData(keys.secrets, data),
  });
}

export function useAgentClis() {
  return useQuery({
    queryKey: ["agent-clis"],
    queryFn: () => api<import("./types").AgentCli[]>("/api/v2/cli/status"),
    // Check quickly while an install or sign-in is running, lazily otherwise.
    refetchInterval: (query) => (query.state.data?.some((a) => a.job?.state === "RUNNING") ? 1_500 : 15_000),
  });
}

export function useRefreshAgentClis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<import("./types").AgentCli[]>("/api/v2/cli/status?refresh=true"),
    onSuccess: (data) => qc.setQueryData(["agent-clis"], data),
  });
}

export function useLaunchCli() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { agent_id: string; action?: "run" | "signin" | "install" | "custom"; custom_command?: string }) =>
      api<{ success: boolean; command?: string; launcher?: string; message: string; job?: import("./types").AgentCliJob }>(
        "/api/v2/cli/launch",
        "POST",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-clis"] });
    },
  });
}

export function useSendCliCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ agentId, text }: { agentId: string; text: string }) =>
      api<{ sent: boolean }>(`/api/v2/cli/jobs/${agentId}/input`, "POST", { text }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["agent-clis"] }),
  });
}

export function useAiModels(provider: string, enabled: boolean) {
  return useQuery({
    queryKey: ["ai-models", provider],
    queryFn: () => api<import("./types").AiModels>(`/api/v2/ai/models/${provider}`),
    enabled,
    retry: false,
    staleTime: 10 * 60_000,
  });
}

export function useTestCredential() {
  return useMutation({
    mutationFn: (body: { provider: string; credentials: Record<string, string> }) =>
      api<import("./types").CredentialTestResult>("/api/v2/credentials/test", "POST", body),
  });
}

export const tools = {
  costs: (body: unknown) => api<CostsResult>("/api/v2/tools/costs", "POST", body),
  positionSize: (body: unknown) => api<PositionSizeResult>("/api/v2/tools/position-size", "POST", body),
  payoff: (body: unknown) => api<PayoffResult>("/api/v2/tools/options-payoff", "POST", body),
};

const SIX_HOURS = 6 * 60 * 60_000;

/** Is a newer QuantOS release out? Quiet by design: a failed check is just "no". */
export function useUpdate() {
  return useQuery({
    queryKey: ["update"],
    queryFn: () => api<UpdateInfo>("/api/v2/update"),
    staleTime: SIX_HOURS,
    refetchInterval: SIX_HOURS,
    retry: false,
  });
}

export function useCheckUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<UpdateInfo>("/api/v2/update?refresh=true"),
    onSuccess: (info) => qc.setQueryData(["update"], info),
  });
}

/** Full release history and changelog showing what was updated and what was preserved across versions. */
export function useChangelog() {
  return useQuery({
    queryKey: ["changelog"],
    queryFn: () => api<ChangelogEntry[]>("/api/v2/changelog"),
    staleTime: SIX_HOURS,
    retry: false,
  });
}
