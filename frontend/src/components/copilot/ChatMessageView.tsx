import { ArrowRight, UsersRound } from "lucide-react";
import { useNavigate } from "react-router";
import { type ChatProposal, type ChatStep, openSecondOpinion } from "../../lib/copilot";
import { answeredBy } from "../../lib/copilotHistory";
import {
  AI_PATH,
  type AssistantMessage,
  CHOOSE_AI,
  type ChatMessage,
  keyButton,
  keyHelp,
  visibleProposals,
} from "./chatState";
import { useCopilot } from "./CopilotProvider";
import { Markdown } from "./MarkdownView";

// A word with no gaps, such as a pasted address, breaks at the edge of the panel instead of widening the page.
const WRAP = "[overflow-wrap:anywhere]";
const PROPOSAL_STYLE =
  `inline-flex max-w-full items-center gap-1.5 rounded-[var(--radius-control)] border border-line bg-surface ${WRAP} ` +
  "px-3 py-1.5 text-left text-[13px] font-medium text-ink transition-colors " +
  "hover:border-line-strong hover:bg-surface-2";

const LINK_BUTTON = "font-medium text-brand hover:underline";
const USER_BUBBLE =
  `max-w-[88%] min-w-0 whitespace-pre-wrap ${WRAP} rounded-2xl rounded-tr-md bg-brand-soft px-3.5 py-2.5 ` +
  "text-[13.5px] text-ink";

/** What the Copilot looked at to answer, folded away until the person wants it. Failed lookups are marked. */
function Steps({ steps }: { steps: readonly ChatStep[] }) {
  if (steps.length === 0) return null;
  return (
    <details className="text-[12.5px] text-ink-3">
      <summary className="cursor-pointer select-none font-medium hover:text-ink-2">What I looked at</summary>
      <ul className={`mt-1.5 space-y-1 ${WRAP}`}>
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

/** One button to where an AI is chosen or its key checked, for a reply that talks about that but offered none. */
function KeyButton({ message }: { message: AssistantMessage }) {
  const openPage = useOpenPage();
  const proposal = keyButton(message);
  return <ProposalButton proposal={proposal} onChoose={() => openPage(proposal.path ?? AI_PATH)} />;
}

/**
 * Which AI answered, by the name of the AI app or company, never a model's own id; an AI it cannot name gets no line.
 * A built-in answer gets no note when its own words already say what to do about choosing an AI, so the same advice
 * is never given twice.
 */
function SourceNote({ message }: { message: AssistantMessage }) {
  const openPage = useOpenPage();
  if (message.mode === "built_in") {
    const help = keyHelp(message);
    if (help === "button") return <KeyButton message={message} />;
    if (help === "none") return null;
    return (
      <p className="text-[12.5px] text-ink-3">
        Answered from QuantOS&apos;s built-in answers.{" "}
        <button type="button" onClick={() => openPage(AI_PATH)} className={LINK_BUTTON}>
          {CHOOSE_AI}
        </button>{" "}
        for open-ended questions.
      </p>
    );
  }
  const said = answeredBy(message.provider);
  return said ? <p className="text-[12.5px] text-ink-3">{said}</p> : null;
}

/** The engine's own sentence when this answer could not be saved. The answer is still here; this is a heads-up. */
function SavedNote({ note }: { note: string | null | undefined }) {
  return note ? <p className="text-[12.5px] text-ink-3">{note}</p> : null;
}

function AssistantBubble({ message }: { message: AssistantMessage }) {
  return (
    <div className={`min-w-0 max-w-full space-y-2.5 ${WRAP}`}>
      <div className="rounded-2xl rounded-tl-md border border-line bg-surface-2 px-3.5 py-2.5">
        <Markdown text={message.content} />
      </div>
      <Steps steps={message.steps} />
      <Proposals proposals={visibleProposals(message)} />
      {message.error && <p className="text-[12.5px] text-warn">{message.error}</p>}
      <SourceNote message={message} />
      <SavedNote note={message.savedNote} />
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
