import type { Account, AccountInput } from "../../lib/types";
import { Field, Input, Select } from "../ui";

export const ACCOUNT_FORM_ID = "account-form";
const DEFAULT_KIND = "Demat account";

/** The fields to start from: the account being changed, or a new account that is the person's own Demat account. */
export function startDraft(initial: Account | undefined, kinds: readonly string[]): AccountInput {
  if (initial) return { name: initial.name, owner: initial.owner, kind: initial.kind, broker: initial.broker };
  return { name: "", owner: "Me", kind: kinds.includes(DEFAULT_KIND) ? DEFAULT_KIND : (kinds[0] ?? ""), broker: "" };
}

export function canSave(draft: AccountInput): boolean {
  return draft.name.trim() !== "" && draft.owner.trim() !== "" && draft.kind !== "";
}

interface FormProps {
  draft: AccountInput;
  kinds: readonly string[];
  onChange: (draft: AccountInput) => void;
  onSubmit: () => void;
}

/**
 * The fields of an account: its name, whose it is, what kind it is, and the broker. Saved by the button in the
 * window's footer, which points at this form, so Enter in any field saves too.
 */
export function AccountForm({ draft, kinds, onChange, onSubmit }: FormProps) {
  const set = (patch: Partial<AccountInput>) => onChange({ ...draft, ...patch });
  return (
    <form
      id={ACCOUNT_FORM_ID}
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSave(draft)) onSubmit();
      }}
    >
      <Field label="Name" htmlFor="account-name" hint="A name you will recognise, such as “Asha's Zerodha”.">
        <Input id="account-name" autoFocus value={draft.name} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Whose account is it?" htmlFor="account-owner">
          <Input id="account-owner" value={draft.owner} onChange={(e) => set({ owner: e.target.value })} />
        </Field>
        <Field label="Kind of account" htmlFor="account-kind">
          <Select id="account-kind" value={draft.kind} onChange={(e) => set({ kind: e.target.value })}>
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field
        label="Broker (optional)"
        htmlFor="account-broker"
        hint="For example Zerodha, Groww, Upstox or HDFC Securities. You can leave it empty."
      >
        <Input id="account-broker" value={draft.broker} onChange={(e) => set({ broker: e.target.value })} />
      </Field>
    </form>
  );
}
