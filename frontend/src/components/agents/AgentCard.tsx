import type { ReactNode } from "react";
import { Link } from "react-router";
import { type Agent, type AgentTool, toolLabels } from "../../lib/agents";
import { plural } from "../../lib/format";
import { Badge, Card } from "../ui";

function AiNote() {
  return (
    <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-ink-3">
      <Badge tone="warn">Works best with an AI key</Badge>
      <Link to="/settings/accounts" className="font-medium text-brand hover:underline">
        Add a key
      </Link>
    </p>
  );
}

interface Props {
  agent: Agent;
  tools: AgentTool[] | undefined;
  actions: ReactNode;
  children?: ReactNode;
}

/** One agent: its name, what it is for, what it may look at, and buttons. A run panel can open under it. */
export function AgentCard({ agent, tools, actions, children }: Props) {
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
          {needsAi && <AiNote />}
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
      {children}
    </Card>
  );
}
