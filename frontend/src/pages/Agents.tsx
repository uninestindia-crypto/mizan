import { Plus } from "lucide-react";
import { useState } from "react";
import { AgentForm } from "../components/agents/AgentForm";
import { AgentSections, type Handlers } from "../components/agents/AgentSections";
import { ConfirmDialog } from "../components/agents/ConfirmDialog";
import { Button, Callout, PageHeader, Skeleton } from "../components/ui";
import { type Agent, type FormTarget, newTarget, useAgentList, useAgentTools, useDeleteAgent } from "../lib/agents";
import { errorMessage } from "../lib/api";

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
    />
  );
}

function NewAgentButton({ onNew }: { onNew: () => void }) {
  return (
    <Button icon={<Plus className="size-4" aria-hidden />} onClick={onNew}>
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

function AgentsHome({ notice, onForm }: { notice: string | null; onForm: (target: FormTarget) => void }) {
  const list = useAgentList();
  const tools = useAgentTools();
  const [running, setRunning] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Agent | null>(null);
  const handlers: Handlers = { running, onRun: setRunning, onForm, onDelete: setDeleting };
  return (
    <>
      <PageHeader title="Agents" subtitle={PURPOSE} actions={<NewAgentButton onNew={() => onForm(newTarget())} />} />
      {notice && (
        <Callout tone="success" className="mb-5">
          {notice}
        </Callout>
      )}
      {list.isPending && <Skeleton className="h-40" />}
      {list.isError && <LoadError error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && <AgentSections data={list.data} tools={tools.data} handlers={handlers} />}
      <DeleteAgentDialog agent={deleting} onClose={() => setDeleting(null)} />
    </>
  );
}

export default function Agents() {
  const [target, setTarget] = useState<FormTarget | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const openForm = (next: FormTarget) => {
    setNotice(null);
    setTarget(next);
  };
  const closeForm = (saved: Agent | null) => {
    setTarget(null);
    setNotice(saved ? `Saved ${saved.name}.` : null);
  };
  return target ? <AgentForm target={target} onClose={closeForm} /> : <AgentsHome notice={notice} onForm={openForm} />;
}
