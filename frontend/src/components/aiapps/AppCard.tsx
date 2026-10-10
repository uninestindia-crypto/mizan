import { ArrowUpCircle, CheckCircle2, Cpu, Download, LogIn, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useDeleteCustomCli, useSetCustomCliAutoUpdate } from "../../lib/queries";
import { versionNumber } from "../../lib/thinking";
import type { AgentCli } from "../../lib/types";
import { AiSourceTest } from "../settings/AiSourceTest";
import { Badge, Button, Callout } from "../ui";
import { JobProgress } from "./JobProgress";
import { ModelsPanel } from "./ModelsPanel";
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
  const version = agent.installed ? versionNumber(agent.version) : null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-ink">
          <Cpu className="size-4" aria-hidden />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <h3 className="text-[14px] font-semibold text-ink">{plainName(agent)}</h3>
            {agent.is_custom && <Badge tone="brand">Company app</Badge>}
          </div>
          <div className="text-[11.5px] text-ink-3">
            <span>by {agent.maker}</span>
            {version && <span> · version {version}</span>}
          </div>
        </div>
      </div>
      <Badge tone={state.tone}>
        {state.tone === "up" && <CheckCircle2 className="size-3" aria-hidden />}
        {state.text}
      </Badge>
    </div>
  );
}

/** How long a finished step stays on the card before it is let go. */
const RESULT_SHOWN_SECONDS = 600;

/** What a step that just finished says. A person can dismiss it. */
function Finished({ job }: { job: NonNullable<AgentCli["job"]> }) {
  const [dismissed, setDismissed] = useState<string | null>(null);
  if (dismissed === job.id) return null;
  return (
    <Callout
      tone="success"
      className="mt-3"
      action={
        <Button size="sm" variant="ghost" onClick={() => setDismissed(job.id)}>
          Dismiss
        </Button>
      }
    >
      {job.message}
    </Callout>
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
          variant="secondary"
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

function CustomCliControls({ agent }: { agent: AgentCli }) {
  const toggleAutoUpdate = useSetCustomCliAutoUpdate();
  const deleteCli = useDeleteCustomCli();
  const isAuto = Boolean(agent.auto_update);

  if (!agent.is_custom) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between border-t border-line/60 pt-2.5 text-[12px]">
      <label className="flex items-center gap-1.5 cursor-pointer text-ink-2 select-none hover:text-ink">
        <input
          type="checkbox"
          checked={isAuto}
          disabled={toggleAutoUpdate.isPending}
          onChange={(e) => toggleAutoUpdate.mutate({ cliId: agent.id, enabled: e.target.checked })}
          className="size-3.5 rounded border-line text-brand focus:ring-brand"
        />
        <span>Update this app automatically</span>
      </label>
      <Button
        size="sm"
        variant="ghost"
        icon={<Trash2 className="size-3 text-red-500" aria-hidden />}
        className="text-red-500 hover:text-red-600 hover:bg-red-500/10 text-[11px] h-6 px-2"
        loading={deleteCli.isPending}
        onClick={() => {
          if (window.confirm(`Are you sure you want to remove ${agent.name}?`)) {
            deleteCli.mutate(agent.id);
          }
        }}
      >
        Remove
      </Button>
    </div>
  );
}

/** One AI app on this computer: what it is, where it stands, and the one thing to do next. */
export function AppCard(props: CardProps) {
  const { agent, note } = props;
  const running = agent.job?.state === "RUNNING";
  const failed = agent.job?.state === "FAILED" ? agent.job : null;
  const finished =
    agent.job?.state === "DONE" && (agent.job.ended_seconds_ago ?? RESULT_SHOWN_SECONDS) < RESULT_SHOWN_SECONDS
      ? agent.job
      : null;
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
        {finished && <Finished job={finished} />}
        {note && !running && (
          <Callout tone="info" className="mt-3">
            {note}
          </Callout>
        )}
      </div>
      <div>
        <Actions agent={agent} busy={props.busy} onStep={props.onStep} onRecheck={props.onRecheck} />
        <ModelsPanel agentId={agent.id} name={plainName(agent)} installed={agent.installed} />
        <CustomCliControls agent={agent} />
      </div>
      {!agent.installed && !agent.is_custom && (
        <p className="mt-2 text-[11.5px] text-ink-3">
          QuantOS downloads the official app from {agent.maker} and sets it up for you. It can take a few minutes.
        </p>
      )}
    </div>
  );
}
