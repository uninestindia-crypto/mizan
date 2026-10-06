import { ArrowRight, UsersRound } from "lucide-react";
import { useNavigate } from "react-router";
import { type ChatProposal, type ChatStep, openSecondOpinion } from "../../lib/copilot";
import { ACCOUNTS_PATH, type AssistantMessage, type ChatMessage, visibleProposals } from "./chatState";
import { useCopilot } from "./CopilotProvider";
import { Markdown } from "./Markdown";

const PROPOSAL_STYLE =
  "inline-flex items-center gap-1.5 rounded-[var(--radius-control)] border border-line bg-surface px-3 py-1.5 " +
  "text-left text-[13px] font-medium text-ink transition-colors hover:border-line-strong hover:bg-surface-2";

const LINK_BUTTON = "font-medium text-brand hover:underline";
const USER_BUBBLE =
  "max-w-[88%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-md bg-brand-soft px-3.5 py-2.5 " +
  "text-[13.5px] text-ink";

/** What the Copilot looked at to answer, folded away until the person wants it. Failed lookups are marked. */
function Steps({ steps }: { steps: readonly ChatStep[] }) {
  if (steps.length === 0) return null;
  return (
    <details className="text-[12.5px] text-ink-3">
      <summary className="cursor-pointer select-none font-medium hover:text-ink-2">What I looked at</summary>
      <ul className="mt-1.5 space-y-1">
        {steps.map((step, index) => (
          <li key={index}>
            <span className="font-medium text-ink-2">{step.label}</span>
            {step.summary ? `: ${step.summary}` : ""}
            {!step.ok && <span className="font-medium text-warn"> (could not be checked)</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

function isNarrowScreen(): boolean {
  return typeof window.matchMedia === "function" && !window.matchMedia("(min-width: 768px)").matches;
}

/** Opens a page from the drawer. On a narrow screen the drawer would cover the page, so it steps aside. */
function useOpenPage(): (path: string) => void {
  const navigate = useNavigate();
  const { closeCopilot } = useCopilot();
  return (path) => {
    void navigate(path);
    if (isNarrowScreen()) closeCopilot();
  };
}

function ProposalButton({ proposal, onChoose }: { proposal: ChatProposal; onChoose: () => void }) {
  const Icon = proposal.kind === "second_opinion" ? UsersRound : ArrowRight;
  return (
    <button type="button" onClick={onChoose} className={PROPOSAL_STYLE}>
      <Icon className="size-4 shrink-0" aria-hidden />
      {proposal.label}
    </button>
  );
}

/** Buttons the person chooses to click. The Copilot never opens a page or starts a check by itself. */
function Proposals({ proposals }: { proposals: readonly ChatProposal[] }) {
  const openPage = useOpenPage();
  if (proposals.length === 0) return null;
  const choose = (proposal: ChatProposal) => {
    if (proposal.kind === "second_opinion" && proposal.symbol) openSecondOpinion(proposal.symbol);
    else if (proposal.path) openPage(proposal.path);
  };
  return (
    <div className="flex flex-wrap gap-2">
      {proposals.map((proposal, index) => (
        <ProposalButton key={index} proposal={proposal} onChoose={() => choose(proposal)} />
      ))}
    </div>
  );
}

function SourceNote({ message }: { message: AssistantMessage }) {
  const openPage = useOpenPage();
  if (message.mode === "built_in") {
    return (
      <p className="text-[12.5px] text-ink-3">
        Answered from QuantOS&apos;s built-in answers.{" "}
        <button type="button" onClick={() => openPage(ACCOUNTS_PATH)} className={LINK_BUTTON}>
          Add an AI key
        </button>{" "}
        for open-ended questions.
      </p>
    );
  }
  const by = [message.model, message.provider].filter(Boolean).join(" from ");
  return by ? <p className="text-[12.5px] text-ink-3">Answered by the AI model {by}.</p> : null;
}

function AssistantBubble({ message }: { message: AssistantMessage }) {
  return (
    <div className="max-w-full space-y-2.5">
      <div className="rounded-2xl rounded-tl-md border border-line bg-surface-2 px-3.5 py-2.5">
        <Markdown text={message.content} />
      </div>
      <Steps steps={message.steps} />
      <Proposals proposals={visibleProposals(message)} />
      {message.error && <p className="text-[12.5px] text-warn">{message.error}</p>}
      <SourceNote message={message} />
    </div>
  );
}

export function ChatMessageView({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className={USER_BUBBLE}>
          <span className="sr-only">You said: </span>
          {message.content}
        </p>
      </div>
    );
  }
  return (
    <div>
      <span className="sr-only">Copilot said: </span>
      <AssistantBubble message={message} />
    </div>
  );
}
