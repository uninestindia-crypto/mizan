import { CheckCircle2, Cpu, Download, ExternalLink, LogIn, RefreshCw, Terminal } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "../lib/api";
import { useAgentClis, useLaunchCli, useRefreshAgentClis, useSendCliCode } from "../lib/queries";
import type { AgentCli } from "../lib/types";
import { Badge, Button, Callout, Card, CardHeader, Input, Skeleton, Spinner } from "./ui";

type Action = "run" | "signin" | "install" | "custom";

function StateBadge({ agent }: { agent: AgentCli }) {
  if (agent.job?.state === "RUNNING") return <Badge tone="brand">{agent.job.action === "install" ? "Installing" : "Signing in"}</Badge>;
  switch (agent.state) {
    case "CONNECTED":
      return <Badge tone="up">Connected</Badge>;
    case "NEEDS_SIGN_IN":
      return <Badge tone="warn">Sign in needed</Badge>;
    case "UNKNOWN":
      return <Badge>Not checked</Badge>;
    default:
      return <Badge>Not installed</Badge>;
  }
}

function RunningJob({ agent }: { agent: AgentCli }) {
  const job = agent.job!;
  const send = useSendCliCode();
  const [code, setCode] = useState("");
  return (
    <div className="mt-3 rounded-lg border border-brand/30 bg-brand/5 p-3 text-[12.5px]">
      <Spinner label={job.message || "Working…"} />
      {job.action === "signin" && job.url && (
        <div className="mt-2 text-ink-3">
          Browser did not open?{" "}
          <a href={job.url} target="_blank" rel="noreferrer" className="font-medium text-brand hover:underline">
            Open the sign-in page <ExternalLink className="inline size-3" aria-hidden />
          </a>
        </div>
      )}
      {job.accepts_code && job.url && (
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.trim()) send.mutate({ agentId: agent.id, text: code.trim() }, { onSuccess: () => setCode("") });
          }}
        >
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="If the page shows a code, paste it here" spellCheck={false} aria-label="Sign-in code" className="font-mono text-[12px]" />
          <Button size="sm" type="submit" loading={send.isPending} disabled={!code.trim()}>
            Submit
          </Button>
        </form>
      )}
      {send.isError && <div className="mt-1 text-[11.5px] text-down">{errorMessage(send.error)}</div>}
      <div className="mt-1 text-[11.5px] text-ink-3">{Math.round(job.seconds)}s</div>
    </div>
  );
}

function AgentCard({
  agent,
  busy,
  note,
  onAction,
  onRecheck,
}: {
  agent: AgentCli;
  busy: boolean;
  note: string | null;
  onAction: (action: Action) => void;
  onRecheck: () => void;
}) {
  const running = agent.job?.state === "RUNNING";
  const failed = agent.job?.state === "FAILED" ? agent.job : null;
  const terminalSignin = agent.signin_mode === "terminal";

  return (
    <div className="flex flex-col justify-between rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-card)]">
      <div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-surface-2 text-ink">
              <Cpu className="size-4" aria-hidden />
            </div>
            <div>
              <span className="font-semibold text-ink">{agent.name}</span>
              <div className="text-[11.5px] text-ink-3">by {agent.maker}</div>
            </div>
          </div>
          <StateBadge agent={agent} />
        </div>
        <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2">{agent.description}</p>
        {agent.installed && (
          <div className="mt-2 text-[11.5px] text-ink-3">
            {agent.version ? `Version ${agent.version} · ` : ""}
            {agent.auth_detail}
          </div>
        )}

        {running && <RunningJob agent={agent} />}

        {failed && (
          <Callout tone="danger" className="mt-3" title={failed.message}>
            {failed.output.length > 0 && (
              <details className="mt-1">
                <summary className="cursor-pointer text-[12px] text-ink-3">Show details</summary>
                <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-ink-2">{failed.output.join("\n")}</pre>
              </details>
            )}
          </Callout>
        )}

        {note && !running && (
          <Callout tone="info" className="mt-3">
            {note}
          </Callout>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line/60 pt-3">
        {!agent.installed && (
          <Button size="sm" icon={<Download className="size-3.5" aria-hidden />} loading={running || busy} onClick={() => onAction("install")}>
            Install
          </Button>
        )}
        {agent.installed && agent.state !== "CONNECTED" && (
          <Button size="sm" icon={<LogIn className="size-3.5" aria-hidden />} loading={running || busy} onClick={() => onAction("signin")}>
            {terminalSignin ? "Sign in" : agent.state === "UNKNOWN" ? "Sign in or check" : "Sign in with browser"}
          </Button>
        )}
        {agent.installed && (
          <Button size="sm" variant={agent.state === "CONNECTED" ? "primary" : "secondary"} icon={<Terminal className="size-3.5" aria-hidden />} disabled={running} onClick={() => onAction("run")}>
            Open in terminal
          </Button>
        )}
        {terminalSignin && agent.installed && agent.state !== "CONNECTED" && (
          <Button size="sm" variant="ghost" icon={<RefreshCw className="size-3.5" aria-hidden />} onClick={onRecheck}>
            Check again
          </Button>
        )}
        {agent.state === "CONNECTED" && (
          <span className="inline-flex items-center gap-1 text-[12px] text-up">
            <CheckCircle2 className="size-3.5" aria-hidden /> Ready
          </span>
        )}
      </div>

      {!agent.installed && (
        <details className="mt-2 text-[11.5px] text-ink-3">
          <summary className="cursor-pointer">What Install will run</summary>
          <p className="mt-1">The official installer from the maker, run for you without a terminal window:</p>
          {agent.install_steps.map((step) => (
            <code key={step} className="mt-1 block break-all rounded-md border border-line bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink">
              {step}
            </code>
          ))}
        </details>
      )}
    </div>
  );
}

export function AgentCliBridge() {
  const agentQuery = useAgentClis();
  const launch = useLaunchCli();
  const refresh = useRefreshAgentClis();
  const [notes, setNotes] = useState<Record<string, string | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [customCmd, setCustomCmd] = useState("");

  const run = (agentId: string, action: Action, custom?: string) => {
    setError(null);
    setNotes((prev) => ({ ...prev, [agentId]: null }));
    launch.mutate(
      { agent_id: agentId, action, custom_command: custom },
      {
        onSuccess: (data) => {
          // A background job reports its own progress on the card; only a terminal needs a note.
          if (!data.job && action === "signin") {
            setNotes((prev) => ({
              ...prev,
              [agentId]: "A window opened. Choose “Login with Google” there and finish in your browser, then come back and press Check again.",
            }));
          }
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Coding agents"
          subtitle="Install a coding agent and sign in with your browser. No commands to type: QuantOS runs the maker's own installer and opens the sign-in page for you."
          action={
            <Button size="sm" variant="ghost" icon={<RefreshCw className="size-3.5" aria-hidden />} loading={refresh.isPending} onClick={() => refresh.mutate()}>
              Check status
            </Button>
          }
        />
        {error && (
          <Callout tone="danger" className="mb-4">
            {error}
          </Callout>
        )}
        {agentQuery.isPending ? (
          <Skeleton className="h-64" />
        ) : agentQuery.isError ? (
          <Callout tone="danger">{errorMessage(agentQuery.error)}</Callout>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {agentQuery.data.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                busy={launch.isPending && launch.variables?.agent_id === agent.id}
                note={notes[agent.id] ?? null}
                onAction={(action) => run(agent.id, action)}
                onRecheck={() => refresh.mutate()}
              />
            ))}
          </div>
        )}
      </Card>

      <details className="group">
        <summary className="cursor-pointer text-[13px] font-medium text-ink-2 hover:text-ink">Advanced: run your own command in a terminal</summary>
        <Card className="mt-3">
          <div className="flex gap-2">
            <Input
              placeholder="e.g. python -m my_agent"
              value={customCmd}
              onChange={(e) => setCustomCmd(e.target.value)}
              className="font-mono text-[12.5px]"
              aria-label="Command to run in a terminal"
            />
            <Button disabled={!customCmd.trim()} loading={launch.isPending && launch.variables?.action === "custom"} onClick={() => run("custom", "custom", customCmd.trim())}>
              Open in terminal
            </Button>
          </div>
        </Card>
      </details>
    </div>
  );
}
