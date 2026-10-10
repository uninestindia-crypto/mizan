import { RefreshCw } from "lucide-react";
import { errorMessage } from "../lib/api";
import { useAgentClis, useRefreshAgentClis } from "../lib/queries";
import { AppCard } from "./aiapps/AppCard";
import { inOrder } from "./aiapps/appWords";
import { useAppSetup, useRefreshWhenJobEnds } from "./aiapps/useAppSetup";
import { Button, Callout, Card, CardHeader, Skeleton } from "./ui";

const SUBTITLE =
  "Install an AI app and sign in with your browser. QuantOS does the rest, " +
  "and the Copilot can answer with the app you choose above.";

type Setup = ReturnType<typeof useAppSetup>;

function Apps({ setup, recheck }: { setup: Setup; recheck: () => void }) {
  const apps = useAgentClis();
  if (apps.isPending) return <Skeleton className="h-64" />;
  if (apps.isError) return <Callout tone="danger">{errorMessage(apps.error)}</Callout>;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {inOrder(apps.data).map((agent) => (
        <AppCard
          key={agent.id}
          agent={agent}
          busy={setup.busyId === agent.id}
          note={setup.notes[agent.id] ?? null}
          onStep={(action) => setup.start(agent.id, action)}
          onRecheck={recheck}
        />
      ))}
    </div>
  );
}

/**
 * Settings, then AI assistants: install each AI app on this computer and sign in to it from here. The AI choice
 * above says which of them answers the Copilot; this card is where an app gets ready to be chosen.
 */
export function AgentCliBridge() {
  const refresh = useRefreshAgentClis();
  const setup = useAppSetup();
  useRefreshWhenJobEnds(useAgentClis().data);
  const check = (
    <Button
      size="sm"
      variant="ghost"
      icon={<RefreshCw className="size-3.5" aria-hidden />}
      loading={refresh.isPending}
      onClick={() => refresh.mutate()}
    >
      Check status
    </Button>
  );
  return (
    <Card>
      <CardHeader title="Set up AI apps on this computer" subtitle={SUBTITLE} action={check} />
      {setup.error && (
        <Callout tone="danger" className="mb-4">
          {setup.error}
        </Callout>
      )}
      <Apps setup={setup} recheck={() => refresh.mutate()} />
    </Card>
  );
}
