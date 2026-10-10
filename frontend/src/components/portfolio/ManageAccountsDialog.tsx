import { useState } from "react";
import { errorMessage } from "../../lib/api";
import type { Account } from "../../lib/types";
import { Callout, Dialog, Spinner } from "../ui";
import { plural } from "../../lib/format";
import { useAccounts } from "./accountQueries";
import { ADD_BUTTON_ID, DeleteStep, FormStep, ListStep, deleteButtonId, editButtonId } from "./ManageSteps";

type Step = { name: "list" } | { name: "form"; account?: Account } | { name: "delete"; account: Account };

const TEXT: Record<Step["name"], { title: string; description: string }> = {
  list: { title: "Your accounts", description: "Add the accounts you look after, and keep each one's holdings apart." },
  form: { title: "Account", description: "Say whose account it is and what kind it is." },
  delete: { title: "Delete this account?", description: "This removes the account from QuantOS only." },
};

function heading(step: Step): { title: string; description: string } {
  if (step.name === "form") {
    return { ...TEXT.form, title: step.account ? `Edit ${step.account.name}` : "Add an account" };
  }
  if (step.name === "delete") return { ...TEXT.delete, title: `Delete ${step.account.name}?` };
  return TEXT.list;
}

/** Which step the window is on, the sentence to show after a change, and where focus returns to. */
function useSteps() {
  const [step, setStep] = useState<Step>({ name: "list" });
  const [notice, setNotice] = useState<string | null>(null);
  const [back, setBack] = useState<string | null>(null);
  const go = (next: Step, returnTo: string | null) => {
    setBack(returnTo);
    setStep(next);
    setNotice(null);
  };
  const toList = (message: string | null, returnTo: string | null) => {
    setBack(returnTo);
    setStep({ name: "list" });
    setNotice(message);
  };
  return { step, notice, back, go, toList };
}

type Steps = ReturnType<typeof useSteps>;

/** Add, change and delete the accounts. Deleting one that holds stocks asks where they should go first. */
export function ManageAccountsDialog(props: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** An account was deleted, so a screen showing it can move to another view. */
  onDeleted: (id: number) => void;
}) {
  const list = useAccounts(props.open);
  const steps = useSteps();
  const close = (open: boolean) => {
    if (!open) steps.toList(null, null);
    props.onOpenChange(open);
  };
  const { title, description } = heading(steps.step);
  return (
    <Dialog open={props.open} onOpenChange={close} title={title} description={description} wide>
      {list.isPending && <Spinner label="Loading your accounts" />}
      {list.isError && <Callout tone="danger">{errorMessage(list.error)}</Callout>}
      {list.data && (
        <StepBody
          steps={steps}
          accounts={list.data.accounts}
          kinds={list.data.kinds}
          onDeleted={props.onDeleted}
          onDone={() => close(false)}
        />
      )}
    </Dialog>
  );
}

interface BodyProps {
  steps: Steps;
  accounts: readonly Account[];
  kinds: readonly string[];
  onDeleted: (id: number) => void;
  onDone: () => void;
}

function StepBody(props: BodyProps) {
  const { step } = props.steps;
  if (step.name === "form") return <SaveBody {...props} account={step.account} />;
  if (step.name === "delete") return <DeleteBody {...props} account={step.account} />;
  return <ListBody {...props} />;
}

function SaveBody(props: BodyProps & { account?: Account }) {
  const { toList, back } = props.steps;
  return (
    <FormStep
      account={props.account}
      kinds={props.kinds}
      onSaved={(saved) => toList(`Saved “${saved.name}”.`, ADD_BUTTON_ID)}
      onCancel={() => toList(null, back)}
    />
  );
}

function DeleteBody(props: BodyProps & { account: Account }) {
  const { toList, back } = props.steps;
  const done = (gone: Account, movedTo: Account | undefined, moved: number) => {
    props.onDeleted(gone.id);
    toList(deletedText(gone, movedTo, moved), ADD_BUTTON_ID);
  };
  return (
    <DeleteStep
      account={props.account}
      others={props.accounts.filter((a) => a.id !== props.account.id)}
      onCancel={() => toList(null, back)}
      onDeleted={done}
    />
  );
}

function ListBody(props: BodyProps) {
  const { notice, back, go } = props.steps;
  return (
    <ListStep
      accounts={props.accounts}
      notice={notice}
      focusId={back}
      onAdd={() => go({ name: "form" }, ADD_BUTTON_ID)}
      onEdit={(account) => go({ name: "form", account }, editButtonId(account.id))}
      onDelete={(account) => go({ name: "delete", account }, deleteButtonId(account.id))}
      onDone={props.onDone}
    />
  );
}

function deletedText(gone: Account, movedTo: Account | undefined, moved: number): string {
  if (!movedTo || moved === 0) return `Deleted “${gone.name}”.`;
  return `Deleted “${gone.name}”. ${plural(moved, "holding")} moved to ${movedTo.name}.`;
}
