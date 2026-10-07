import { Plus } from "lucide-react";
import { useState } from "react";
import { AgentForm } from "../components/agents/AgentForm";
import { AgentSections, type Handlers } from "../components/agents/AgentSections";
import { ConfirmDialog } from "../components/agents/ConfirmDialog";
import { findByFocusKey, MY_AGENTS, PAGE_HEADING, useFocusReturn } from "../components/agents/focus";
import { Button, Callout, PageHeader, Skeleton } from "../components/ui";
import {
  type Agent,
  type FormTarget,
  NEW_OPENER,
  newTarget,
  useAgentList,
  useAgentTools,
  useDeleteAgent,
} from "../lib/agents";
import { errorMessage } from "../lib/api";
import { useCopilotModels } from "../lib/copilot";

const PURPOSE =
  "Agents are assistants you set up once and run whenever you like. Each one follows the steps you write, " +
  "and can only look at the things you tick. No agent can place an order.";

function DeleteBody({ error }: { error: unknown }) {
  return (
    <>
      <p>This removes the agent and the answer it gave last time. It cannot be undone.</p>
      {error ? <p className="mt-2 text-down">{errorMessage(error)}</p> : null}
    </>
  );
}

function DeleteAgentDialog({ agent, onClose }: { agent: Agent | null; onClose: () => void }) {
  const remove = useDeleteAgent();
  const close = () => {
    remove.reset();
    onClose();
  };
  const answer = (confirmed: boolean) => (confirmed && agent ? remove.mutate(agent.id, { onSuccess: close }) : close());
  return (
    <ConfirmDialog
      open={agent !== null}
      title={agent ? `Delete ${agent.name}?` : "Delete this agent?"}
      body={<DeleteBody error={remove.error} />}
      choices={{ keep: "Keep it", confirm: "Delete" }}
      busy={remove.isPending}
      onAnswer={answer}
      fallbackFocus={() => findByFocusKey(MY_AGENTS) ?? findByFocusKey(PAGE_HEADING)}
    />
  );
}

function NewAgentButton({ onNew }: { onNew: () => void }) {
  return (
    <Button icon={<Plus className="size-4" aria-hidden />} data-focus-key={NEW_OPENER} onClick={onNew}>
      New agent
    </Button>
  );
}

function LoadError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const retry = <Button onClick={onRetry}>Try again</Button>;
  return (
    <Callout tone="danger" title="Your agents could not be loaded" action={retry}>
      {errorMessage(error)}
    </Callout>
  );
}

/** The page title, which can take focus (but is not a tab stop) when there is no better place to put it. */
function PageTitle({ children }: { children: string }) {
  return (
    <span tabIndex={-1} data-focus-key={PAGE_HEADING} className="outline-none">
      {children}
    </span>
  );
}

interface HomeProps {
  notice: string | null;
  onForm: (target: FormTarget) => void;
  /** The button the form was opened from, when the person has just come back from it. */
  returnTo: string | null;
  onReturned: () => void;
}

function AgentsHome({ notice, onForm, returnTo, onReturned }: HomeProps) {
  const list = useAgentList();
  const tools = useAgentTools();
  const models = useCopilotModels();
  const [running, setRunning] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Agent | null>(null);
  const handlers: Handlers = { running, onRun: setRunning, onForm, onDelete: setDeleting };
  const noAiKey = models.data !== undefined && !models.data.some((model) => model.ready);
  useFocusReturn(returnTo, list.data !== undefined, onReturned);
  return (
    <>
      <PageHeader
        title={<PageTitle>Agents</PageTitle>}
        subtitle={PURPOSE}
        actions={<NewAgentButton onNew={() => onForm(newTarget())} />}
      />
      {notice && (
        <Callout tone="success" className="mb-5">
          {notice}
        </Callout>
      )}
      {list.isPending && <Skeleton className="h-40" />}
      {list.isError && <LoadError error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && <AgentSections data={list.data} tools={tools.data} handlers={handlers} noAiKey={noAiKey} />}
      <DeleteAgentDialog agent={deleting} onClose={() => setDeleting(null)} />
    </>
  );
}

export default function Agents() {
  const [target, setTarget] = useState<FormTarget | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [returnTo, setReturnTo] = useState<string | null>(null);
  const openForm = (next: FormTarget) => {
    setNotice(null);
    setReturnTo(null);
    setTarget(next);
  };
  const closeForm = (saved: Agent | null) => {
    setReturnTo(target?.opener ?? null);
    setTarget(null);
    setNotice(saved ? `Saved ${saved.name}.` : null);
  };
  if (target) return <AgentForm target={target} onClose={closeForm} />;
  return <AgentsHome notice={notice} onForm={openForm} returnTo={returnTo} onReturned={() => setReturnTo(null)} />;
}
