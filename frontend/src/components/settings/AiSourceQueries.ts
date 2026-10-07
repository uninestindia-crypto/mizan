import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../../lib/api";
import {
  type AiSettings,
  type AiSettingsPatch,
  type AiStatus,
  type AiTestResult,
  choiceFrom,
} from "../../lib/aiSource";
import { useAgentClis } from "../../lib/queries";

export const aiStatusKey = ["copilot", "status"] as const;

/** Which AIs are ready and what the person chose. Looks again every few seconds and whenever the window is entered. */
export function useAiStatus() {
  return useQuery({
    queryKey: aiStatusKey,
    queryFn: () => api<AiStatus>("/api/v2/copilot/status"),
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });
}

/**
 * The install and sign-in cards below keep their own check going. When one of them sees an app change (a sign-in
 * finished in the browser), this screen looks again at once rather than waiting for its own turn.
 */
export function useRefreshWhenAppsChange(): void {
  const qc = useQueryClient();
  const apps = useAgentClis().data;
  const signature = apps?.map((app) => `${app.id}:${app.state}`).join("|");
  const seen = useRef(signature);
  useEffect(() => {
    const before = seen.current;
    seen.current = signature;
    const changed = before !== undefined && signature !== undefined && before !== signature;
    if (changed) void qc.invalidateQueries({ queryKey: aiStatusKey });
  }, [signature, qc]);
}

/** What the engine saved becomes what the screen shows at once; the next look confirms it. */
function rememberSaved(qc: QueryClient, saved: AiSettings): void {
  const withChoice = (old: AiStatus | undefined) => (old ? { ...old, ai: choiceFrom(saved) } : old);
  qc.setQueryData<AiStatus>(aiStatusKey, withChoice);
  void qc.invalidateQueries({ queryKey: aiStatusKey });
}

/** Saves a change of AI at once. The engine answers with the settings as saved. */
export function useSaveAiChoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: AiSettingsPatch) => api<AiSettings>("/api/v2/settings", "PUT", patch),
    onSuccess: (saved) => rememberSaved(qc, saved),
  });
}

/** One small question to one AI, or to whichever the Copilot would use. A finished test refreshes the chips. */
export function useTestAi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model: string | null) =>
      api<AiTestResult>("/api/v2/copilot/ai/test", "POST", model === null ? {} : { model }),
    onSettled: () => void qc.invalidateQueries({ queryKey: aiStatusKey }),
  });
}
