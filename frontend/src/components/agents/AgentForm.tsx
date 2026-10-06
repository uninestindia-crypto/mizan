import { type FormEvent, useState } from "react";
import {
  type Agent,
  type AgentInput,
  type FormField,
  type FormTarget,
  groupProblems,
  isDirty,
  type Problem,
  problemsFromError,
  toInput,
  useAgentTools,
  useSaveAgent,
  usesSymbol,
  validateForm,
} from "../../lib/agents";
import { errorMessage } from "../../lib/api";
import { Button, Callout, Card, Field, Input, PageHeader, Skeleton } from "../ui";
import { ConfirmDialog } from "./ConfirmDialog";
import { FieldGroup, invalidClass, problemText, TextArea } from "./fields";
import { STEPS_HELP, StepsEditor } from "./StepsEditor";
import { ToolPicker } from "./ToolPicker";

type Messages = Record<FormField | "other", string[]>;

interface SectionProps {
  form: AgentInput;
  messages: Messages;
  change: (patch: Partial<AgentInput>) => void;
}

const SUMMARY = "Check the highlighted fields.";

function BasicsFields({ form, messages, change }: SectionProps) {
  const bad = (field: FormField) => messages[field].length > 0;
  return (
    <>
      <Field label="Name" htmlFor="agent-name" error={problemText(messages.name)}>
        <Input
          id="agent-name"
          value={form.name}
          placeholder="For example: My halal check"
          aria-invalid={bad("name") || undefined}
          className={invalidClass(bad("name"))}
          onChange={(e) => change({ name: e.target.value })}
        />
      </Field>
      <Field label="What is it for?" htmlFor="agent-description" error={problemText(messages.description)}>
        <Input
          id="agent-description"
          value={form.description}
          aria-invalid={bad("description") || undefined}
          className={invalidClass(bad("description"))}
          onChange={(e) => change({ description: e.target.value })}
        />
      </Field>
      <Field
        label="How should it behave?"
        htmlFor="agent-instructions"
        hint="Optional. For example: keep answers short"
        error={problemText(messages.instructions)}
      >
        <TextArea
          id="agent-instructions"
          rows={3}
          value={form.instructions}
          invalid={bad("instructions")}
          onChange={(e) => change({ instructions: e.target.value })}
        />
      </Field>
    </>
  );
}

function ToolsError({ onRetry }: { onRetry: () => void }) {
  return (
    <p className="text-sm text-ink-2">
      The list could not be loaded.{" "}
      <button type="button" className="font-medium text-brand hover:underline" onClick={onRetry}>
        Try again
      </button>
    </p>
  );
}

function ToolsField({ form, messages, change }: SectionProps) {
  const tools = useAgentTools();
  const pick = (names: string[]) => change({ tools: names });
  return (
    <FieldGroup legend="What may it look at?" error={problemText(messages.tools)}>
      {tools.isPending && <Skeleton className="h-24" />}
      {tools.isError && <ToolsError onRetry={() => void tools.refetch()} />}
      {tools.data && <ToolPicker tools={tools.data} selected={form.tools} onChange={pick} />}
    </FieldGroup>
  );
}

function StepsField({ form, messages, change }: SectionProps) {
  const setSteps = (steps: string[]) => change({ steps });
  return (
    <FieldGroup legend="Steps" hint={STEPS_HELP} error={problemText(messages.steps)}>
      <StepsEditor steps={form.steps} messages={messages.steps} onChange={setSteps} />
      {usesSymbol(form) && (
        <p className="text-[12.5px] text-ink-3">When you run this agent, it will ask which stock to use.</p>
      )}
    </FieldGroup>
  );
}

/** The form's own state: what is typed, what to fix, and sending it. */
function useAgentFormState(target: FormTarget, onClose: (saved: Agent | null) => void) {
  const save = useSaveAgent();
  const [form, setForm] = useState(target.initial);
  const [problems, setProblems] = useState<Problem[]>([]);

  const change = (patch: Partial<AgentInput>) => {
    setForm((old) => ({ ...old, ...patch }));
    setProblems((old) => old.filter((p) => !(p.field in patch)));
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateForm(form);
    setProblems(found);
    if (found.length > 0) return;
    const onError = (error: unknown) => setProblems(problemsFromError(error) ?? []);
    const onSuccess = (saved: Agent) => onClose(saved);
    save.mutate({ id: target.id, input: toInput(form) }, { onSuccess, onError });
  };
  const failure = problems.length === 0 && save.isError ? errorMessage(save.error) : null;
  return { form, problems, change, submit, failure, saving: save.isPending, dirty: isDirty(form, target.initial) };
}

function Banners({ problems, messages, failure }: { problems: Problem[]; messages: Messages; failure: string | null }) {
  return (
    <>
      {problems.length > 0 && (
        <Callout tone="danger" title={SUMMARY}>
          {messages.other.join(" ")}
        </Callout>
      )}
      {failure && <Callout tone="danger">{failure}</Callout>}
    </>
  );
}

/** Create or change an agent: a name, what it may look at, and the steps it follows. */
export function AgentForm({ target, onClose }: { target: FormTarget; onClose: (saved: Agent | null) => void }) {
  const state = useAgentFormState(target, onClose);
  const [asking, setAsking] = useState(false);
  const messages = groupProblems(state.problems);
  const section = { form: state.form, messages, change: state.change };
  const answer = (discard: boolean) => {
    setAsking(false);
    if (discard) onClose(null);
  };
  return (
    <form onSubmit={state.submit} noValidate className="space-y-5">
      <PageHeader title={target.heading} subtitle="Agents can only look. No agent can place an order." />
      <Banners problems={state.problems} messages={messages} failure={state.failure} />
      <Card className="space-y-5">
        <BasicsFields {...section} />
        <ToolsField {...section} />
        <StepsField {...section} />
      </Card>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={state.saving}>
          Save
        </Button>
        <Button type="button" variant="secondary" onClick={() => (state.dirty ? setAsking(true) : onClose(null))}>
          Cancel
        </Button>
      </div>
      <ConfirmDialog
        open={asking}
        title="Leave without saving?"
        body="Your changes to this agent will be lost."
        choices={{ keep: "Keep editing", confirm: "Discard changes" }}
        onAnswer={answer}
      />
    </form>
  );
}
