import { type NavigateFunction, useNavigate } from "react-router";
import {
  type LookedAt,
  type Proposal,
  type ProposalAction,
  proposalAction,
  requestSecondOpinion,
  type RunResult,
  type RunStep,
} from "../../lib/agents";
import { friendlyDates } from "../../lib/plainDates";
import { Badge, Button, Callout } from "../ui";
import { NumberBadge } from "./fields";
import { Reply } from "./Reply";

function LookedAtList({ items }: { items: LookedAt[] }) {
  if (items.length === 0) return null;
  return (
    <details className="text-[13px] text-ink-2">
      <summary className="cursor-pointer select-none font-medium text-ink-3 hover:text-ink">
        What it looked at ({items.length})
      </summary>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium text-ink">{item.label}</span>
            {!item.ok && <Badge tone="warn">Could not be looked up</Badge>}
            <span className="text-ink-3">{friendlyDates(item.summary)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function StepView({ step }: { step: RunStep }) {
  return (
    <li className="flex gap-3">
      <NumberBadge number={step.number} className="mt-0.5" />
      <div className="min-w-0 flex-1 space-y-2">
        <p className="text-[13px] font-medium text-ink-2">{friendlyDates(step.text)}</p>
        {step.error && (
          <p role="alert" className="text-[13px] text-down">
            {friendlyDates(step.error)}
          </p>
        )}
        {step.reply && step.reply !== step.error && (
          <div className="rounded-xl bg-surface-2 p-3">
            <Reply text={step.reply} />
          </div>
        )}
        <LookedAtList items={step.looked_at} />
      </div>
    </li>
  );
}

interface Usable {
  label: string;
  action: ProposalAction;
}

/** Only the buttons that are complete and safe. */
function usableButtons(proposals: Proposal[]): Usable[] {
  return proposals.flatMap((proposal) => {
    const action = proposalAction(proposal);
    return action ? [{ label: proposal.label, action }] : [];
  });
}

function perform(action: ProposalAction, navigate: NavigateFunction): void {
  if (action.type === "navigate") navigate(action.path);
  else requestSecondOpinion(action.symbol);
}

/** Buttons the person clicks. The agent never opens anything by itself. */
function ProposalButtons({ proposals }: { proposals: Proposal[] }) {
  const navigate = useNavigate();
  const buttons = usableButtons(proposals);
  if (buttons.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {buttons.map(({ label, action }, i) => (
        <Button key={i} variant="secondary" size="sm" onClick={() => perform(action, navigate)}>
          {label}
        </Button>
      ))}
    </div>
  );
}

function StepList({ steps }: { steps: RunStep[] }) {
  if (steps.length === 0) return null;
  return (
    <ol className="space-y-4">
      {steps.map((step) => (
        <StepView key={step.number} step={step} />
      ))}
    </ol>
  );
}

/** Why the run ended where it did: the engine's own note, or a plain line when it stopped without one. */
function Outcome({ result }: { result: RunResult }) {
  const ranSome = result.steps.length > 0;
  return (
    <>
      {!result.completed && !result.note && (
        <Callout tone="warn">{ranSome ? "The agent stopped before its last step." : "The agent did not run."}</Callout>
      )}
      {result.note && <Callout tone="info">{friendlyDates(result.note)}</Callout>}
    </>
  );
}

/** What an agent wrote, step by step. It is information to look into, never advice. */
export function RunResultView({ result }: { result: RunResult }) {
  const heading = result.symbol ? `${result.name}: ${result.symbol}` : result.name;
  return (
    <div className="mt-4 space-y-4">
      <h4 className="text-sm font-semibold text-ink">{heading}</h4>
      <StepList steps={result.steps} />
      <Outcome result={result} />
      <ProposalButtons proposals={result.proposals} />
      <p className="text-[12px] text-ink-3">
        This is information to help you look into a stock yourself. It is not advice.
        {result.model ? " Written with an AI model." : ""}
      </p>
    </div>
  );
}
