import type { ReactNode } from "react";
import { Link } from "react-router";
import { type Agent, type AgentTool, toolLabels } from "../../lib/agents";
import { plural } from "../../lib/format";
import { Card } from "../ui";

/** Says what really happens: with no AI set up this agent stops at once and points here. */
function AiNote() {
  return (
    <p className="mt-2 text-[12.5px] text-warn">
      Needs an AI. Choose one in{" "}
      <Link to="/settings/ai" className="font-medium underline">
        Settings, then AI assistants
      </Link>
      .
    </p>
  );
}

interface Props {
  agent: Agent;
  tools: AgentTool[] | undefined;
  actions: ReactNode;
  /** True only once the engine has said that no AI is set up. Until then the note is not shown. */
  noAiKey: boolean;
  children?: ReactNode;
}

/** One agent: its name, what it is for, what it may look at, and buttons. A run panel can open under it. */
export function AgentCard(props: Props) {
  const { agent, tools, actions, noAiKey, children } = props;
  const looksAt = toolLabels(agent.tools, tools);
  const needsAi = "needs_ai" in agent && agent.needs_ai === true;
  return (
    <Card as="article">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-semibold text-ink">{agent.name}</h3>
          {agent.description && <p className="mt-0.5 text-sm text-ink-2">{agent.description}</p>}
          <p className="mt-1.5 text-[12.5px] text-ink-3">
            {plural(agent.steps.length, "step")}
            {looksAt.length > 0 && ` · Looks at: ${looksAt.join(", ")}`}
          </p>
          {needsAi && noAiKey && <AiNote />}
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
      {children}
    </Card>
  );
}
