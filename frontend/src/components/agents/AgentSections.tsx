import { Plus } from "lucide-react";
import type { ReactNode } from "react";
import {
  type Agent,
  type AgentList,
  type AgentTool,
  copyTarget,
  editTarget,
  type FormTarget,
  newTarget,
} from "../../lib/agents";
import { Button, EmptyState } from "../ui";
import { AgentCard } from "./AgentCard";
import { RunPanel } from "./RunPanel";

/** Everything a card's buttons can do, so the page decides and the cards only ask. */
export interface Handlers {
  /** The agent whose run panel is open. */
  running: string | null;
  onRun: (id: string | null) => void;
  onForm: (target: FormTarget) => void;
  onDelete: (agent: Agent) => void;
}

function Actions({ agent, handlers }: { agent: Agent; handlers: Handlers }) {
  return (
    <>
      <Button size="sm" onClick={() => handlers.onRun(agent.id)}>
        Run
      </Button>
      {agent.built_in ? (
        <Button size="sm" variant="secondary" onClick={() => handlers.onForm(copyTarget(agent))}>
          Copy and edit
        </Button>
      ) : (
        <>
          <Button size="sm" variant="secondary" onClick={() => handlers.onForm(editTarget(agent))}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" onClick={() => handlers.onDelete(agent)}>
            Delete
          </Button>
        </>
      )}
    </>
  );
}

interface RowProps {
  agent: Agent;
  tools: AgentTool[] | undefined;
  handlers: Handlers;
}

function AgentRow({ agent, tools, handlers }: RowProps) {
  return (
    <AgentCard agent={agent} tools={tools} actions={<Actions agent={agent} handlers={handlers} />}>
      {handlers.running === agent.id && <RunPanel agent={agent} onClose={() => handlers.onRun(null)} />}
    </AgentCard>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <section className="mt-8 first:mt-0">
      <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      <p className="mb-3 mt-0.5 text-[13px] text-ink-3">{hint}</p>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function NoAgentsYet({ onForm }: { onForm: (target: FormTarget) => void }) {
  const add = (
    <Button icon={<Plus className="size-4" aria-hidden />} onClick={() => onForm(newTarget())}>
      New agent
    </Button>
  );
  return (
    <EmptyState
      title="You have no agents yet"
      body="Pick a ready-made agent and choose Copy and edit, or choose New agent."
      action={add}
    />
  );
}

interface Props {
  data: AgentList;
  tools: AgentTool[] | undefined;
  handlers: Handlers;
}

export function AgentSections({ data, tools, handlers }: Props) {
  return (
    <>
      <Section title="My agents" hint="Assistants you made. Run one whenever you like.">
        {data.agents.length === 0 && <NoAgentsYet onForm={handlers.onForm} />}
        {data.agents.map((agent) => (
          <AgentRow key={agent.id} agent={agent} tools={tools} handlers={handlers} />
        ))}
      </Section>
      <Section title="Ready-made" hint="Run one as it is, or copy it and change it to suit you.">
        {data.recipes.map((recipe) => (
          <AgentRow key={recipe.id} agent={recipe} tools={tools} handlers={handlers} />
        ))}
      </Section>
    </>
  );
}
