import { type ChangeEvent, useEffect, useState } from "react";
import { errorMessage } from "../../lib/api";
import { inr } from "../../lib/format";
import { useSaveHolding } from "../../lib/queries";
import type { Account, PortfolioRow } from "../../lib/types";
import { SymbolSearch } from "../common";
import { Button, Callout, Dialog, Field, Input, Select } from "../ui";
import { type AccountChoice, useAccounts } from "./accountQueries";

export interface LotDraft {
  id?: number;
  symbol: string;
  quantity: string;
  avg_price: string;
  buy_date: string;
  note: string;
  /** The account the person picked, as the select holds it. Empty until they pick one. */
  account: string;
}

const today = () => new Date().toISOString().slice(0, 10);
const blank = (): LotDraft => ({ symbol: "", quantity: "", avg_price: "", buy_date: today(), note: "", account: "" });

/** The form fields for a purchase already on the Portfolio, to change it or move it to another account. */
export function draftFromRow(row: PortfolioRow): Partial<LotDraft> {
  return {
    id: row.id,
    symbol: row.symbol,
    quantity: String(row.quantity),
    avg_price: String(row.avg_price),
    buy_date: row.buy_date,
    note: row.note,
    account: String(row.account_id),
  };
}

/** The account a purchase goes to: the one picked, else the one in view, else the first account. */
export function accountToUse(
  draft: LotDraft,
  viewing: AccountChoice,
  accounts: readonly Account[],
): number | undefined {
  const wanted = draft.account || (viewing === "all" ? "" : viewing);
  const found = accounts.find((a) => String(a.id) === wanted);
  if (found) return found.id;
  const notHereYet = accounts.length === 0 && /^\d+$/.test(wanted); // the list of accounts is still on its way
  return notHereYet ? Number(wanted) : accounts[0]?.id;
}

interface FormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: Partial<LotDraft>;
  /** The account being viewed, which a new purchase goes to unless another is picked. */
  viewing: AccountChoice;
  /** Keep the stock as it is given (the stock's own page): no search, no "Change". */
  lockSymbol?: boolean;
}

/** The draft being filled in, whether it can be saved, and the save itself. */
function useLotForm({ open, initial, viewing, onOpenChange }: FormProps) {
  const [draft, setDraft] = useState<LotDraft>(blank);
  const save = useSaveHolding();
  const accounts = useAccounts(open).data?.accounts ?? [];
  useEffect(() => {
    if (!open) return;
    setDraft({ ...blank(), ...initial });
    save.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const quantity = Number(draft.quantity);
  const price = Number(draft.avg_price);
  const counted = Number.isInteger(quantity) && quantity > 0 && price > 0;
  const valid = Boolean(draft.symbol) && counted && draft.buy_date !== "";
  const chosen = accountToUse(draft, viewing, accounts);
  const submit = () => {
    const { symbol, avg_price, buy_date, note } = draft;
    const input = { symbol, quantity, avg_price, buy_date, note, account_id: chosen };
    save.mutate({ id: draft.id, input }, { onSuccess: () => onOpenChange(false) });
  };
  const set = (patch: Partial<LotDraft>) => setDraft({ ...draft, ...patch });
  return { draft, set, accounts, chosen, valid, quantity, price, save, submit };
}

type LotForm = ReturnType<typeof useLotForm>;

export function HoldingFormDialog(props: FormProps) {
  const form = useLotForm(props);
  const { draft, save } = form;
  return (
    <Dialog
      open={props.open}
      onOpenChange={props.onOpenChange}
      title={draft.id ? `Edit ${draft.symbol}` : "Add a holding"}
      description={DESCRIPTION}
      footer={
        <>
          <Button variant="secondary" onClick={() => props.onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={form.submit} disabled={!form.valid} loading={save.isPending}>
            {draft.id ? "Save changes" : "Add holding"}
          </Button>
        </>
      }
    >
      <LotFields form={form} lockSymbol={props.lockSymbol === true} />
    </Dialog>
  );
}

const DESCRIPTION =
  "Enter what you bought. QuantOS values it at the latest close and compares it with NIFTY bought on the same day.";

function LotFields({ form, lockSymbol }: { form: LotForm; lockSymbol: boolean }) {
  const { draft, set, accounts } = form;
  return (
    <div className="grid gap-4">
      <SymbolField draft={draft} locked={Boolean(draft.id) || lockSymbol} onSymbol={(symbol) => set({ symbol })} />
      {accounts.length > 1 && <AccountField accounts={accounts} value={form.chosen} set={set} />}
      <AmountFields draft={draft} set={set} />
      <DateFields draft={draft} set={set} />
      {form.valid && <p className="text-[13px] text-ink-3">Cost {inr(form.quantity * form.price)}</p>}
      {form.save.isError && <Callout tone="danger">{errorMessage(form.save.error)}</Callout>}
    </div>
  );
}

function AccountField(props: { accounts: readonly Account[]; value: number | undefined; set: PartProps["set"] }) {
  return (
    <Field label="Account" htmlFor="h-account" hint="Which account holds this purchase.">
      <Select id="h-account" value={props.value ?? ""} onChange={(e) => props.set({ account: e.target.value })}>
        {props.accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name} ({a.owner})
          </option>
        ))}
      </Select>
    </Field>
  );
}

interface PartProps {
  draft: LotDraft;
  set: (patch: Partial<LotDraft>) => void;
}

function AmountFields({ draft, set }: PartProps) {
  const quantity = (e: ChangeEvent<HTMLInputElement>) => set({ quantity: e.target.value.replace(/\D/g, "") });
  const price = (e: ChangeEvent<HTMLInputElement>) => set({ avg_price: e.target.value.replace(/[^\d.]/g, "") });
  return (
    <div className="grid grid-cols-2 gap-4">
      <Field label="Quantity" htmlFor="h-qty">
        <Input id="h-qty" inputMode="numeric" value={draft.quantity} onChange={quantity} />
      </Field>
      <Field label="Average price" htmlFor="h-price">
        <Input id="h-price" prefix="₹" inputMode="decimal" value={draft.avg_price} onChange={price} />
      </Field>
    </div>
  );
}

function DateFields({ draft, set }: PartProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Field label="Bought on" htmlFor="h-date">
        <Input
          id="h-date"
          type="date"
          max={today()}
          value={draft.buy_date}
          onChange={(e) => set({ buy_date: e.target.value })}
        />
      </Field>
      <Field label="Note (optional)" htmlFor="h-note">
        <Input id="h-note" maxLength={200} value={draft.note} onChange={(e) => set({ note: e.target.value })} />
      </Field>
    </div>
  );
}

const CHANGE = "text-[13px] font-medium text-brand hover:underline";
const CHOSEN =
  "flex items-center rounded-[var(--radius-control)] border border-line bg-surface-2 px-3 text-sm";

function SymbolField(props: { draft: LotDraft; locked: boolean; onSymbol: (symbol: string) => void }) {
  const { symbol } = props.draft;
  if (props.locked) {
    return (
      <Field label="Stock or ETF">
        <div className={`${CHOSEN} h-10 font-semibold text-ink`}>{symbol}</div>
      </Field>
    );
  }
  return (
    <Field label="Stock or ETF">
      {symbol ? (
        <div className={`${CHOSEN} justify-between py-2`}>
          <span className="font-semibold text-ink">{symbol}</span>
          <button type="button" className={CHANGE} onClick={() => props.onSymbol("")}>
            Change
          </button>
        </div>
      ) : (
        <SymbolSearch onPick={props.onSymbol} autoFocus />
      )}
    </Field>
  );
}
