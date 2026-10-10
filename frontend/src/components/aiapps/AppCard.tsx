import { CheckCircle2, Cpu, Download, LogIn, RefreshCw } from "lucide-react";
import type { AgentCli } from "../../lib/types";
import { AiSourceTest } from "../settings/AiSourceTest";
import { Badge, Button, Callout } from "../ui";
import { JobProgress } from "./JobProgress";
import { canAnswer, nextStep, oneLine, plainName, type SetupAction, stateWords, testModel } from "./appWords";
import { useAppTest } from "./useAppSetup";

interface AppProps {
  agent: AgentCli;
  /** The request to start an install or sign-in is on its way. */
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
  const more = nextStep(agent) !== "done";
  if (!more && !canTest(agent)) return null;
  return (
    <div className="mt-4 space-y-2 border-t border-line/60 pt-3">
      {more && <StepRow {...props} />}
      {canTest(agent) && <TestLink agent={agent} />}
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
      <Actions agent={agent} busy={props.busy} onStep={props.onStep} onRecheck={props.onRecheck} />
      {!agent.installed && (
        <p className="mt-2 text-[11.5px] text-ink-3">
          QuantOS downloads the official app from {agent.maker} and sets it up for you. It can take a few minutes.
        </p>
      )}
    </div>
  );
}
