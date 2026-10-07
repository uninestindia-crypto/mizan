import { Plus } from "lucide-react";
import type { ReactNode } from "react";
import {
  type Agent,
  type AgentList,
  type AgentTool,
  copyOpener,
  copyTarget,
  editOpener,
  editTarget,
  type FormTarget,
  newTarget,
} from "../../lib/agents";
import { Button, EmptyState } from "../ui";
import { AgentCard } from "./AgentCard";
import { MY_AGENTS } from "./focus";
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
        <Button
          size="sm"
          variant="secondary"
          data-focus-key={copyOpener(agent.id)}
          onClick={() => handlers.onForm(copyTarget(agent))}
        >
          Copy and edit
        </Button>
      ) : (
        <>
          <Button
            size="sm"
            variant="secondary"
            data-focus-key={editOpener(agent.id)}
            onClick={() => handlers.onForm(editTarget(agent))}
          >
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
  /** True only once the engine has said that no AI is set up. */
  noAiKey: boolean;
}

function AgentRow({ agent, tools, handlers, noAiKey }: RowProps) {
  const actions = <Actions agent={agent} handlers={handlers} />;
  return (
    <AgentCard agent={agent} tools={tools} actions={actions} noAiKey={noAiKey}>
      {handlers.running === agent.id && <RunPanel agent={agent} onClose={() => handlers.onRun(null)} />}
    </AgentCard>
  );
}

interface SectionProps {
  title: string;
  hint: string;
  children: ReactNode;
  /** Marks the heading, so focus has somewhere to land when a card in the section is deleted. */
  focusKey?: string;
}

function Section({ title, hint, children, focusKey }: SectionProps) {
  return (
    <section className="mt-8 first:mt-0">
      <h2 tabIndex={-1} data-focus-key={focusKey} className="text-[15px] font-semibold text-ink outline-none">
        {title}
      </h2>
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
  noAiKey: boolean;
}

export function AgentSections({ data, tools, handlers, noAiKey }: Props) {
  return (
    <>
      <Section title="My agents" hint="Assistants you made. Run one whenever you like." focusKey={MY_AGENTS}>
        {data.agents.length === 0 && <NoAgentsYet onForm={handlers.onForm} />}
        {data.agents.map((agent) => (
          <AgentRow key={agent.id} agent={agent} tools={tools} handlers={handlers} noAiKey={noAiKey} />
        ))}
      </Section>
      <Section title="Ready-made" hint="Run one as it is, or copy it and change it to suit you.">
        {data.recipes.map((recipe) => (
          <AgentRow key={recipe.id} agent={recipe} tools={tools} handlers={handlers} noAiKey={noAiKey} />
        ))}
      </Section>
    </>
  );
}
