import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, errorMessage } from "../../lib/api";
import { int } from "../../lib/format";
import type { Account, AccountInput } from "../../lib/types";
import { Button, Callout, Field, Select } from "../ui";
import { useDeleteAccount, useSaveAccount } from "./accountQueries";
import { holdingsText } from "./accountText";
import { AccountForm, ACCOUNT_FORM_ID, canSave, startDraft } from "./AccountForm";

// The three steps inside the Manage accounts window. Each owns its buttons, so each can show its own progress and
// the plain sentence the server gave when it refused.

const FOOTER = "mt-6 flex flex-wrap justify-end gap-2";

export const ADD_BUTTON_ID = "accounts-add";
export function editButtonId(id: number): string {
  return `accounts-edit-${id}`;
}

export function deleteButtonId(id: number): string {
  return `accounts-delete-${id}`;
}

interface ListProps {
  accounts: readonly Account[];
  notice: string | null;
  focusId: string | null;
  onAdd: () => void;
  onEdit: (account: Account) => void;
  onDelete: (account: Account) => void;
  onDone: () => void;
}

export function ListStep(props: ListProps) {
  useEffect(() => {
    if (props.focusId) document.getElementById(props.focusId)?.focus();
  }, [props.focusId]);
  const onlyOne = props.accounts.length === 1;
  return (
    <div>
      {props.notice && (
        <Callout tone="success" className="mb-3">
          {props.notice}
        </Callout>
      )}
      <ul aria-label="Your accounts" className="divide-y divide-line rounded-xl border border-line">
        {props.accounts.map((account) => (
          <AccountRow
            key={account.id}
            account={account}
            canDelete={!onlyOne}
            onEdit={() => props.onEdit(account)}
            onDelete={() => props.onDelete(account)}
          />
        ))}
      </ul>
      {onlyOne && <p className="mt-2 text-[12.5px] text-ink-3">You always keep at least one account.</p>}
      <div className={FOOTER}>
        <Button variant="secondary" onClick={props.onDone}>
          Done
        </Button>
        <Button id={ADD_BUTTON_ID} icon={<Plus className="size-4" aria-hidden />} onClick={props.onAdd}>
          Add an account
        </Button>
      </div>
    </div>
  );
}

function AccountRow(props: { account: Account; canDelete: boolean; onEdit: () => void; onDelete: () => void }) {
  const { account } = props;
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <AccountSummary account={account} />
      <div className="flex shrink-0 gap-1">
        <IconButton id={editButtonId(account.id)} label={`Edit ${account.name}`} onClick={props.onEdit}>
          <Pencil className="size-4" aria-hidden />
        </IconButton>
        {props.canDelete && (
          <IconButton id={deleteButtonId(account.id)} label={`Delete ${account.name}`} danger onClick={props.onDelete}>
            <Trash2 className="size-4" aria-hidden />
          </IconButton>
        )}
      </div>
    </li>
  );
}

function AccountSummary({ account }: { account: Account }) {
  const detail = [account.owner, account.kind, account.broker].filter(Boolean).join(" · ");
  return (
    <div className="min-w-0">
      <div className="truncate text-sm font-semibold text-ink">{account.name}</div>
      <div className="truncate text-[12.5px] text-ink-3">{detail}</div>
      <div className="text-[12.5px] text-ink-3">{holdingsText(account.holdings)}</div>
    </div>
  );
}

function IconButton(props: { id: string; label: string; danger?: boolean; onClick: () => void; children: ReactNode }) {
  const tone = props.danger ? "hover:bg-down-soft hover:text-down" : "hover:bg-surface-2 hover:text-ink";
  return (
    <button
      id={props.id}
      type="button"
      aria-label={props.label}
      onClick={props.onClick}
      className={`rounded-lg p-2 text-ink-3 ${tone}`}
    >
      {props.children}
    </button>
  );
}

export function FormStep(props: {
  account?: Account;
  kinds: readonly string[];
  onSaved: (account: Account) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<AccountInput>(() => startDraft(props.account, props.kinds));
  const save = useSaveAccount();
  const submit = () => save.mutate({ id: props.account?.id, input: draft }, { onSuccess: props.onSaved });
  return (
    <div>
      <AccountForm draft={draft} kinds={props.kinds} onChange={setDraft} onSubmit={submit} />
      {save.isError && (
        <Callout tone="danger" className="mt-4">
          {errorMessage(save.error)}
        </Callout>
      )}
      <div className={FOOTER}>
        <Button variant="secondary" onClick={props.onCancel}>
          Cancel
        </Button>
        <Button type="submit" form={ACCOUNT_FORM_ID} disabled={!canSave(draft)} loading={save.isPending}>
          {props.account ? "Save changes" : "Add account"}
        </Button>
      </div>
    </div>
  );
}

export function DeleteStep(props: {
  account: Account;
  others: readonly Account[];
  onDeleted: (account: Account, movedTo: Account | undefined, moved: number) => void;
  onCancel: () => void;
}) {
  const remove = useDeleteAccount();
  const [choice, setChoice] = useState("");
  const code = remove.error instanceof ApiError ? remove.error.code : "";
  const needsMove = props.account.holdings > 0 || code === "ACCOUNT_HAS_HOLDINGS";
  const target = props.others.find((a) => String(a.id) === choice) ?? props.others[0];
  const submit = () =>
    remove.mutate(
      { id: props.account.id, moveTo: needsMove ? target?.id : undefined },
      { onSuccess: (done) => props.onDeleted(props.account, needsMove ? target : undefined, done.moved) },
    );
  return (
    <div className="grid gap-4">
      {needsMove ? (
        <MoveChoice account={props.account} others={props.others} value={target?.id} onChange={setChoice} />
      ) : (
        <p className="text-sm text-ink-2">Nothing is held in {props.account.name}. Nothing is sold.</p>
      )}
      {remove.isError && <Callout tone="danger">{errorMessage(remove.error)}</Callout>}
      <div className={FOOTER}>
        <Button variant="secondary" onClick={props.onCancel}>
          Keep it
        </Button>
        <Button variant="danger" loading={remove.isPending} onClick={submit} disabled={needsMove && !target}>
          Delete account
        </Button>
      </div>
    </div>
  );
}

function moveText(count: number): string {
  return `${int(count)} ${count === 1 ? "holding moves" : "holdings move"}`;
}

function MoveChoice(props: {
  account: Account;
  others: readonly Account[];
  value: number | undefined;
  onChange: (id: string) => void;
}) {
  const target = props.others.find((a) => a.id === props.value);
  return (
    <>
      <p className="text-sm text-ink-2">
        {props.account.name} still has holdings in it. Choose where they should go first. Nothing is sold.
      </p>
      <Field label="Move holdings to" htmlFor="account-move-to">
        <Select id="account-move-to" value={props.value ?? ""} onChange={(e) => props.onChange(e.target.value)}>
          {props.others.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.owner})
            </option>
          ))}
        </Select>
      </Field>
      {target && props.account.holdings > 0 && (
        <p className="text-[12.5px] text-ink-3">
          {moveText(props.account.holdings)} to {target.name}.
        </p>
      )}
    </>
  );
}
