import { ArrowUpCircle, CheckCircle2, ChevronDown, ChevronUp, Cpu, Download, LogIn, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { useCliCapabilities } from "../../lib/queries";
import type { AgentCli } from "../../lib/types";
import { AiSourceTest } from "../settings/AiSourceTest";
import { Badge, Button, Callout } from "../ui";
import { JobProgress } from "./JobProgress";
import { canAnswer, nextStep, oneLine, plainName, type SetupAction, stateWords, testModel } from "./appWords";
import { useAppTest } from "./useAppSetup";

interface AppProps {
  agent: AgentCli;
  /** The request to start an install, sign-in, or update is on its way. */
  busy: boolean;
  onStep: (action: SetupAction) => void;
  onRecheck: () => void;
}

interface CardProps extends AppProps {
  /** A line to show under the app, such as what to do in the sign-in window that opened. */
  note: string | null;
}

function Heading({ agent }: { agent: AgentCli }) {
  const state = stateWords(agent);
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-ink">
          <Cpu className="size-4" aria-hidden />
        </div>
        <div>
          <h3 className="text-[14px] font-semibold text-ink">{plainName(agent)}</h3>
          <div className="text-[11.5px] text-ink-3">by {agent.maker}</div>
        </div>
      </div>
      <Badge tone={state.tone}>
        {state.tone === "up" && <CheckCircle2 className="size-3" aria-hidden />}
        {state.text}
      </Badge>
    </div>
  );
}

function Failure({ job }: { job: NonNullable<AgentCli["job"]> }) {
  const pre = "mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-ink-2";
  return (
    <Callout tone="danger" className="mt-3" title={job.message}>
      {job.output.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-[12px] text-ink-3">Show details</summary>
          <pre className={pre}>{job.output.join("\n")}</pre>
        </details>
      )}
    </Callout>
  );
}

/** The one next step: Install, or Sign in. A signed-in app has none. */
interface StepButtonProps {
  agent: AgentCli;
  loading: boolean;
  onStep: AppProps["onStep"];
}

function NextStepButton({ agent, loading, onStep }: StepButtonProps) {
  const step = nextStep(agent);
  const name = plainName(agent);
  if (step === "done") return null;
  const install = step === "install";
  const Icon = install ? Download : LogIn;
  return (
    <Button
      size="sm"
      icon={<Icon className="size-3.5" aria-hidden />}
      loading={loading}
      aria-label={install ? `Install ${name}` : `Sign in to ${name}`}
      onClick={() => onStep(step)}
    >
      {install ? "Install" : "Sign in"}
    </Button>
  );
}

/** The quiet "Test this AI" link: the same test the AI choice above uses, aimed at this app. */
function TestLink({ agent }: { agent: AgentCli }) {
  const run = useAppTest();
  return <AiSourceTest run={run} target={testModel(agent)} quiet />;
}

function StepRow(props: AppProps) {
  const { agent } = props;
  const loading = agent.job?.state === "RUNNING" || props.busy;
  const asksAgain = agent.signin_mode === "terminal" && nextStep(agent) === "signin";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <NextStepButton agent={agent} loading={loading} onStep={props.onStep} />
      {agent.installed && (
        <Button
          size="sm"
          variant="outline"
          icon={<ArrowUpCircle className="size-3.5" aria-hidden />}
          loading={loading && agent.job?.action === "update"}
          aria-label={`Update ${plainName(agent)}`}
          onClick={() => props.onStep("update")}
        >
          Update
        </Button>
      )}
      {asksAgain && (
        <Button
          size="sm"
          variant="ghost"
          icon={<RefreshCw className="size-3.5" aria-hidden />}
          onClick={props.onRecheck}
        >
          Check again
        </Button>
      )}
    </div>
  );
}

/** An installed app that is signed in, or cannot say, can be asked a small question to see that it works. */
function canTest(agent: AgentCli): boolean {
  return agent.installed && agent.state !== "NEEDS_SIGN_IN" && canAnswer(agent);
}

function Actions(props: AppProps) {
  const { agent } = props;
  const more = nextStep(agent) !== "done" || agent.installed;
  if (!more && !canTest(agent)) return null;
  return (
    <div className="mt-4 space-y-2 border-t border-line/60 pt-3">
      {more && <StepRow {...props} />}
      {canTest(agent) && <TestLink agent={agent} />}
    </div>
  );
}

function CliCapabilitiesSection({ agentId, name, installed }: { agentId: string; name: string; installed: boolean }) {
  const [open, setOpen] = useState(false);
  const caps = useCliCapabilities(agentId, open && installed);

  if (!installed) return null;

  return (
    <div className="mt-3 border-t border-line/60 pt-2.5">
      <button
        type="button"
        aria-label={`Inspect models and features of ${name}`}
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between py-1 text-[12px] font-medium text-ink-2 hover:text-ink transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Sparkles className="size-3.5 text-brand" aria-hidden />
          <span>Live Models & Features</span>
        </span>
        <span className="flex items-center gap-1 text-[11px] text-ink-3">
          {caps.data?.models ? `${caps.data.models.length} models` : "Inspect"}
          {open ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-3 rounded-lg bg-surface-2/60 p-2.5 text-[12px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
              Supported Models
            </span>
            <button
              type="button"
              disabled={caps.isFetching}
              onClick={() => void caps.refetch()}
              className="flex items-center gap-1 text-[11px] text-brand hover:underline disabled:opacity-50"
            >
              <RefreshCw className={`size-3 ${caps.isFetching ? "animate-spin" : ""}`} />
              <span>{caps.isFetching ? "Fetching..." : "Fetch Live"}</span>
            </button>
          </div>

          {caps.isLoading ? (
            <div className="py-2 text-center text-[11px] text-ink-3">Fetching live models...</div>
          ) : caps.data?.models && caps.data.models.length > 0 ? (
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {caps.data.models.map((m) => (
                <div key={m.id} className="rounded border border-line/60 bg-surface p-2 text-[11.5px]">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-ink">{m.name}</span>
                    {m.recommended && (
                      <span className="rounded bg-brand/10 px-1.5 py-0.5 text-[10px] font-medium text-brand">
                        Recommended
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-ink-3 leading-snug">{m.description}</p>
                  {m.context_window && (
                    <div className="mt-1 text-[10px] text-ink-3">Context: {m.context_window}</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-ink-3">No models loaded. Click "Fetch Live" to query.</div>
          )}

          <div className="pt-2 border-t border-line/40">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3 mb-1.5">
              CLI Features
            </div>
            <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
              {caps.data?.features?.map((f, i) => (
                <div key={i} className="flex items-start gap-1.5 text-[11px]">
                  <CheckCircle2 className="size-3 text-emerald-500 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-medium text-ink">{f.name}: </span>
                    <span className="text-ink-3">{f.description}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** One AI app on this computer: what it is, where it stands, and the one thing to do next. */
export function AppCard(props: CardProps) {
  const { agent, note } = props;
  const running = agent.job?.state === "RUNNING";
  const failed = agent.job?.state === "FAILED" ? agent.job : null;
  return (
    <div
      data-app-name={agent.name}
      className="flex flex-col justify-between rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-card)]"
    >
      <div>
        <Heading agent={agent} />
        <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2">{oneLine(agent)}</p>
        {agent.job && running && <JobProgress agentId={agent.id} job={agent.job} />}
        {failed && <Failure job={failed} />}
        {note && !running && (
          <Callout tone="info" className="mt-3">
            {note}
          </Callout>
        )}
      </div>
      <div>
        <Actions agent={agent} busy={props.busy} onStep={props.onStep} onRecheck={props.onRecheck} />
        <CliCapabilitiesSection agentId={agent.id} name={plainName(agent)} installed={agent.installed} />
      </div>
      {!agent.installed && (
        <p className="mt-2 text-[11.5px] text-ink-3">
          QuantOS downloads the official app from {agent.maker} and sets it up for you. It can take a few minutes.
        </p>
      )}
    </div>
  );
}
