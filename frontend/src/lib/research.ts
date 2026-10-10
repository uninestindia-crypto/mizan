import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ApiError } from "./api";

// The Research screen: find finance research papers by meaning, and turn on EmbeddingGemma 2 with one button.
// Kept apart from queries.ts and types.ts on purpose, so the screen can change without touching shared files.

export type SetupState = "IDLE" | "DOWNLOADING" | "PREPARING" | "DONE" | "FAILED" | "CANCELLED";

export interface ResearchSetup {
  state: SetupState;
  percent: number;
  mb_done: number;
  mb_total: number;
  message: string;
  error: { code: string; message: string } | null;
}

export interface ResearchStatus {
  engine: {
    state: "READY" | "NEEDS_DOWNLOAD" | "NOT_INSTALLED";
    by_meaning: boolean;
    label: string;
    download_mb: number;
  };
  library: { papers: number };
  setup: ResearchSetup;
}

export interface ResearchPaper {
  id: string;
  title: string;
  authors: string[];
  more_authors: number;
  year: number;
  field: string;
  summary: string;
  link: string;
  match_percent: number;
}

export interface ResearchAnswer {
  question: string;
  results: ResearchPaper[];
  engine: { by_meaning: boolean; label: string };
  library: { papers: number };
  notes: string[];
}

const STATUS_KEY = ["research-status"] as const;
const WORKING: SetupState[] = ["DOWNLOADING", "PREPARING"];

/** The kind of matching in use and the set-up progress. Checks every second while a download is running. */
export function useResearchStatus() {
  return useQuery({
    queryKey: STATUS_KEY,
    queryFn: () => api<ResearchStatus>("/api/v2/research/status"),
    refetchInterval: (query) => (query.state.data && WORKING.includes(query.state.data.setup.state) ? 1000 : false),
  });
}

export function useResearchSearch() {
  const qc = useQueryClient();
  return useMutation<ResearchAnswer, ApiError, { question: string; online: boolean }>({
    mutationFn: ({ question, online }) =>
      api<ResearchAnswer>("/api/v2/research/search", "POST", { question, top_k: 5, online }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });
}

export function useStartResearchSetup() {
  const qc = useQueryClient();
  return useMutation<ResearchSetup, ApiError>({
    mutationFn: () => api<ResearchSetup>("/api/v2/research/setup", "POST"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });
}

export function useCancelResearchSetup() {
  const qc = useQueryClient();
  return useMutation<ResearchSetup, ApiError>({
    mutationFn: () => api<ResearchSetup>("/api/v2/research/setup/cancel", "POST"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });
}
