import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../lib/api";
import { keys, useLaunchCli } from "../../lib/queries";
import type { AgentCli } from "../../lib/types";
import { aiStatusKey, useTestAi } from "../settings/AiSourceQueries";
import { type SetupAction, signInNote } from "./appWords";

/** Starts an install or a sign-in. A background job reports itself on the card; only a sign-in window needs a note. */
export function useAppSetup() {
  const launch = useLaunchCli();
  const [notes, setNotes] = useState<Record<string, string | null>>({});
  const [error, setError] = useState<string | null>(null);
  const setNote = (agentId: string, text: string | null) => setNotes((before) => ({ ...before, [agentId]: text }));

  const start = (agentId: string, action: SetupAction) => {
    setError(null);
    setNote(agentId, null);
    launch.mutate(
      { agent_id: agentId, action },
      {
        onSuccess: (data) => setNote(agentId, signInNote(action, data.job)),
        onError: (err) => setError(errorMessage(err)),
      },
    );
  };
  const busyId = launch.isPending ? (launch.variables?.agent_id ?? null) : null;
  return { start, notes, error, busyId };
}

/** The ids of the jobs that have ended (done or failed) in this answer from the engine. */
function endedJobs(apps: readonly AgentCli[]): Set<string> {
  const ended = apps.flatMap((app) => (app.job && app.job.state !== "RUNNING" ? [app.job.id] : []));
  return new Set(ended);
}

/**
 * When an install or a sign-in ends, the Copilot's own check of which AI is ready looks again at once, so the card
 * above and this one agree within a moment. This adds no polling: it acts on the answer the cards already fetch.
 * Jobs that had already ended when the screen opened are not news.
 */
export function useRefreshWhenJobEnds(apps: readonly AgentCli[] | undefined): void {
  const qc = useQueryClient();
  const known = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!apps) return;
    const now = endedJobs(apps);
    const before = known.current;
    known.current = now;
    if (before && [...now].some((id) => !before.has(id))) void qc.invalidateQueries({ queryKey: aiStatusKey });
  }, [apps, qc]);
}

/**
 * The existing "Test this AI" run for one app. A finished test can change what is known about an app that cannot say
 * whether it is signed in, so this card looks again too, as the card above already does.
 */
export function useAppTest() {
  const qc = useQueryClient();
  const run = useTestAi();
  const finished = run.isSuccess || run.isError;
  useEffect(() => {
    if (finished) void qc.invalidateQueries({ queryKey: keys.agentClis });
  }, [finished, qc]);
  return run;
}
