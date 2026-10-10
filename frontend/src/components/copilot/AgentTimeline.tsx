import { CheckCircle2, HelpCircle, Loader2, Search, Users, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { type AgentEvent, progressWords } from "../../lib/agentRun";
import { Button } from "../ui";
import { useCopilot } from "./CopilotProvider";

const ICON = "mt-0.5 size-3.5 shrink-0";

function Line({ event }: { event: AgentEvent }) {
  let icon: ReactNode;
  let text = event.text;
  if (!event.ok) icon = <XCircle className={`${ICON} text-warn`} aria-hidden />;
  else if (event.kind === "action_request") {
    icon = <HelpCircle className={`${ICON} text-brand`} aria-hidden />;
    text = `Asked: ${event.text}`;
  } else if (event.kind === "action_result") icon = <CheckCircle2 className={`${ICON} text-up`} aria-hidden />;
  else if (event.kind === "helper" || event.kind === "helper_done") icon = <Users className={`${ICON} text-ink-3`} aria-hidden />;
  else icon = <Search className={`${ICON} text-ink-3`} aria-hidden />;
  return (
    <li className="flex items-start gap-2 text-[12.5px] text-ink-2">
      {icon}
      <span className="min-w-0 [overflow-wrap:anywhere]">{text}</span>
    </li>
  );
}

/** One change the Copilot asked for. Nothing happens until the person presses Approve. */
function Change({ id }: { id: string }) {
  const { agent, decideChange } = useCopilot();
  const change = agent?.pending.find((item) => item.id === id);
  if (!agent || !change) return null;
  const busy = agent.answering.includes(id);
  return (
    <div role="group" aria-label={`Change to decide: ${change.title}`} className="space-y-2 rounded-xl border border-brand/30 bg-surface p-3">
      <p className="text-[13.5px] font-semibold text-ink [overflow-wrap:anywhere]">{change.title}</p>
      {change.detail && <p className="text-[12.5px] text-ink-2">{change.detail}</p>}
      {change.note && <p className="rounded-lg bg-warn-soft px-2.5 py-1.5 text-[12.5px] text-ink">{change.note}</p>}
      {change.why && <p className="text-[12px] text-ink-3">Why the Copilot asks: {change.why}</p>}
      <div className="flex gap-2 pt-0.5">
        <Button size="sm" disabled={busy} onClick={() => decideChange(id, true)} aria-label={`Approve: ${change.title}`}>
          Approve
        </Button>
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => decideChange(id, false)} aria-label={`Skip: ${change.title}`}>
          Skip
        </Button>
      </div>
    </div>
  );
}

/** What the Copilot is doing on a task right now, and the changes that wait for the person's word. */
export function AgentTimeline() {
  const { agent, stopRun } = useCopilot();
  if (!agent) return null;
  return (
    <section aria-label="What the Copilot is doing" className="space-y-3 rounded-2xl border border-line bg-surface-2/60 p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p role="status" className="flex items-center gap-2 text-[13px] font-medium text-ink">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {progressWords(agent)}
        </p>
        <Button size="sm" variant="ghost" disabled={agent.stopping || agent.runId === null} onClick={stopRun}>
          Stop
        </Button>
      </div>
      {agent.events.length > 0 && (
        <ol className="space-y-1.5" aria-label="Steps so far">
          {agent.events.map((event) => (
            <Line key={event.n} event={event} />
          ))}
        </ol>
      )}
      {agent.pending.map((change) => (
        <Change key={change.id} id={change.id} />
      ))}
      <p className="text-[11.5px] text-ink-3">Nothing changes unless you press Approve. It never places an order.</p>
    </section>
  );
}
