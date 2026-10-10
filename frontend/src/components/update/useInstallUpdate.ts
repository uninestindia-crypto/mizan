import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../lib/api";
import { IDLE, type InstallStatus, isPolling, isWorking } from "./updateInstall";

const INSTALL_PATH = "/api/v2/updates/install";
const POLL_MS = 1_000;

export const installKey = ["update", "install"] as const;

/**
 * How far an update has got. Looked at once a second while it downloads or is being checked, and left alone otherwise:
 * once the engine says it is installing, QuantOS is about to close, the connection will drop, and that is expected, so
 * nothing is asked again and no error is ever shown for it.
 */
export function useInstallStatus(enabled = true) {
  return useQuery({
    queryKey: installKey,
    queryFn: () => api<InstallStatus>(INSTALL_PATH),
    enabled,
    refetchInterval: (query) => (isPolling(query.state.data) ? POLL_MS : false),
    refetchOnWindowFocus: false,
    retry: false,
    staleTime: Infinity,
  });
}

export interface InstallUpdate {
  status: InstallStatus;
  /** Starts the update. It sends no address: the engine uses the one from its own check of QuantOS's releases. */
  start: () => void;
  starting: boolean;
  /** The engine's own plain sentence when it would not start (for example, there is no newer version). */
  refusal: string | null;
  working: boolean;
}

export function useInstallUpdate(): InstallUpdate {
  const qc = useQueryClient();
  const query = useInstallStatus();
  const begin = useMutation({
    mutationFn: () => api<InstallStatus>(INSTALL_PATH, "POST"),
    onSuccess: (status) => qc.setQueryData(installKey, status),
  });
  const status = query.data ?? IDLE;
  return {
    status,
    start: () => begin.mutate(),
    starting: begin.isPending,
    refusal: begin.isError ? errorMessage(begin.error) : null,
    working: begin.isPending || isWorking(status),
  };
}
