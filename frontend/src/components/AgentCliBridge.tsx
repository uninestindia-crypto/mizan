import {
  Copy,
  Cpu,
  LogIn,
  Play,
  Terminal,
} from "lucide-react";
import { useState } from "react";
import { errorMessage } from "../lib/api";
import { useAgentClis, useLaunchCli } from "../lib/queries";
import { Badge, Button, Card, CardHeader, Input, Skeleton } from "./ui";

export function AgentCliBridge() {
  const agentQuery = useAgentClis();
  const launchMutation = useLaunchCli();
  const [copied, setCopied] = useState<string | null>(null);
  const [customCmd, setCustomCmd] = useState("");
  const [launchMessage, setLaunchMessage] = useState<string | null>(null);

  const copy = (text: string) => {
    void navigator.clipboard?.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 1500);
  };

  const handleLaunch = (agentId: string, action: "run" | "signin" | "install" | "custom", customCommand?: string) => {
    setLaunchMessage(null);
    launchMutation.mutate(
      { agent_id: agentId, action, custom_command: customCommand },
      {
        onSuccess: (data) => {
          setLaunchMessage(data.message || `Launched ${agentId} session.`);
          setTimeout(() => setLaunchMessage(null), 5000);
        },
        onError: (err) => {
          setLaunchMessage(`Error: ${errorMessage(err)}`);
        },
      }
    );
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="Coding Agent CLI Bridge"
          subtitle="One-click connect, authenticate, and launch interactive pairing sessions with Google Antigravity, OpenAI Codex, and Claude Code directly in your QuantOS project."
        />
        {launchMessage && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-brand/10 px-3.5 py-2 text-[13px] font-medium text-brand">
            <Terminal className="size-4 shrink-0" />
            <span>{launchMessage}</span>
          </div>
        )}

        {agentQuery.isPending ? (
          <Skeleton className="h-64" />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {(agentQuery.data ?? []).map((agent) => {
              const isInstalled = agent.installed;
              const isAuth = agent.authenticated;

              return (
                <div key={agent.id} className="flex flex-col justify-between rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-card)]">
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="flex size-8 items-center justify-center rounded-lg bg-surface-2 text-ink">
                          <Cpu className="size-4" />
                        </div>
                        <div>
                          <span className="font-semibold text-ink">{agent.name}</span>
                          <div className="text-[11.5px] text-ink-3">by {agent.maker}</div>
                        </div>
                      </div>
                      {isInstalled && isAuth ? (
                        <Badge tone="up">Connected</Badge>
                      ) : isInstalled ? (
                        <Badge tone="warn">Sign In Required</Badge>
                      ) : (
                        <Badge>Not Installed</Badge>
                      )}
                    </div>

                    <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2">{agent.description}</p>

                    <div className="mt-3 space-y-1 rounded-lg border border-line/70 bg-surface-2/60 p-2.5 text-[12px]">
                      <div className="flex justify-between text-ink-3">
                        <span>Binary:</span>
                        <span className="font-mono text-ink">{isInstalled ? agent.version ?? agent.command : "Not in PATH"}</span>
                      </div>
                      <div className="flex justify-between text-ink-3">
                        <span>Auth status:</span>
                        <span className="text-ink">{agent.auth_detail}</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3">
                    {isInstalled ? (
                      <div className="flex w-full flex-wrap items-center gap-2">
                        <Button
                          size="sm"
                          icon={<Play className="size-3.5" />}
                          loading={launchMutation.isPending && launchMutation.variables?.agent_id === agent.id && launchMutation.variables?.action === "run"}
                          onClick={() => handleLaunch(agent.id, "run")}
                        >
                          Launch CLI
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={<LogIn className="size-3.5" />}
                          loading={launchMutation.isPending && launchMutation.variables?.agent_id === agent.id && launchMutation.variables?.action === "signin"}
                          onClick={() => handleLaunch(agent.id, "signin")}
                        >
                          Sign In
                        </Button>
                      </div>
                    ) : (
                      <div className="flex w-full items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[12px] text-ink-3">Install</span>
                          <code className="rounded-lg border border-line bg-surface-2 px-2.5 py-1 font-mono text-[11.5px] text-ink">{agent.install_cmd}</code>
                          <button type="button" onClick={() => copy(agent.install_cmd)} aria-label={`Copy ${agent.install_cmd}`} className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink">
                            {copied === agent.install_cmd ? <span className="text-[11px] text-up">Copied</span> : <Copy className="size-3.5" aria-hidden />}
                          </button>
                        </div>
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={launchMutation.isPending && launchMutation.variables?.agent_id === agent.id && launchMutation.variables?.action === "install"}
                          onClick={() => handleLaunch(agent.id, "install")}
                        >
                          Run Install
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Custom Agent CLI Launcher */}
      <Card>
        <CardHeader
          title="Custom Agent / Script Runner"
          subtitle="1-Click execute any local AI agent script, Python runner, or CLI tool in the QuantOS workspace."
        />
        <div className="flex gap-2">
          <Input
            placeholder="e.g. python -m my_agent or agy --prompt 'analyze portfolio'"
            value={customCmd}
            onChange={(e) => setCustomCmd(e.target.value)}
            className="font-mono text-[12.5px]"
          />
          <Button
            disabled={!customCmd.trim()}
            loading={launchMutation.isPending && launchMutation.variables?.action === "custom"}
            onClick={() => handleLaunch("custom", "custom", customCmd.trim())}
          >
            Launch in Terminal
          </Button>
        </div>
      </Card>
    </div>
  );
}
