import { type QueryClient, useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "./api";
import { keys, useStatus } from "./queries";
import type { Settings, Status } from "./types";

// The app's mode is the saved setting `shariah_mode`, nothing else. The address bar does not decide it, so opening a
// Shariah page while in Institutional mode does not flip it; the switch does.

export type AppMode = "quant" | "shariah";

/** Where each mode starts. The switch goes here after it changes the mode. */
export const MODE_HOME: Record<AppMode, string> = { quant: "/", shariah: "/shariah" };

/** What a person reads for each mode. */
export const MODE_NAME: Record<AppMode, string> = { quant: "Institutional QuantOS", shariah: "Mizan Shariah" };

const MODE_KEY = ["app-mode"] as const;

export function modeFromSettings(settings: Pick<Settings, "shariah_mode"> | undefined | null): AppMode {
  return settings?.shariah_mode ? "shariah" : "quant";
}

function withMode(status: Status, mode: AppMode): Status {
  return { ...status, settings: { ...status.settings, shariah_mode: mode === "shariah" } };
}

/** Puts the mode into the cached settings, so the screen shows it before the engine has answered. */
function showMode(qc: QueryClient, mode: AppMode): void {
  qc.setQueryData<Status>(keys.status, (old) => (old ? withMode(old, mode) : old));
}

async function rememberMode(qc: QueryClient, next: AppMode): Promise<AppMode> {
  await qc.cancelQueries({ queryKey: keys.status });
  const before = modeFromSettings(qc.getQueryData<Status>(keys.status)?.settings);
  showMode(qc, next);
  return before;
}

async function refreshAfterSave(qc: QueryClient): Promise<void> {
  await Promise.all([
    qc.invalidateQueries({ queryKey: keys.status }),
    qc.invalidateQueries({ queryKey: keys.portfolio }),
    qc.invalidateQueries({ queryKey: keys.paperUpdates }),
  ]);
}

/** Saves the mode. The screen shows the new mode at once; if saving fails it goes back and the failure is recorded. */
function useModeMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: MODE_KEY,
    mutationFn: (mode: AppMode) => api<Settings>("/api/v2/settings", "PUT", { shariah_mode: mode === "shariah" }),
    onMutate: (mode) => rememberMode(qc, mode),
    onError: (_error, _mode, before) => showMode(qc, before ?? "quant"),
    onSettled: () => refreshAfterSave(qc),
  });
}

export interface AppModeApi {
  mode: AppMode;
  isShariah: boolean;
  /** Resolves true when the mode was saved, false when it could not be (the screen has already gone back). */
  setMode: (mode: AppMode) => Promise<boolean>;
}

export function useAppMode(): AppModeApi {
  const status = useStatus();
  const save = useModeMutation();
  const mode = modeFromSettings(status.data?.settings);
  const { mutateAsync } = save;
  const setMode = useCallback((next: AppMode) => mutateAsync(next).then(() => true, () => false), [mutateAsync]);
  return { mode, isShariah: mode === "shariah", setMode };
}

export interface ModeFailure {
  /** When the failed attempt was made. Lets a screen tell one failure from the next. */
  at: number;
  /** The mode the person was trying to reach. */
  wanted: AppMode;
}

/** The most recent mode change, if it failed. Null when the latest attempt worked or none was made. */
export function useModeFailure(): ModeFailure | null {
  const attempts = useMutationState({
    filters: { mutationKey: MODE_KEY },
    select: (m) => ({ at: m.state.submittedAt, ok: m.state.status !== "error", wanted: m.state.variables as AppMode }),
  });
  const last = attempts.at(-1);
  return last && !last.ok ? { at: last.at, wanted: last.wanted } : null;
}
