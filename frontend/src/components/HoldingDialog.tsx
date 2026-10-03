import { useEffect, useState } from "react";
import { errorMessage } from "../lib/api";
import { inr } from "../lib/format";
import { type HoldingInput, useSaveHolding } from "../lib/queries";
import { SymbolSearch } from "./common";
import { Button, Callout, Dialog, Field, Input } from "./ui";

export interface HoldingDraft {
  id?: number;
  symbol: string;
  quantity: string;
  avg_price: string;
  buy_date: string;
  note: string;
}

const today = () => new Date().toISOString().slice(0, 10);

export function HoldingDialog({
  open,
  onOpenChange,
  initial,
  lockSymbol = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: Partial<HoldingDraft>;
  lockSymbol?: boolean;
}) {
  const [draft, setDraft] = useState<HoldingDraft>({ symbol: "", quantity: "", avg_price: "", buy_date: today(), note: "" });
  const save = useSaveHolding();

  useEffect(() => {
    if (open) {
      setDraft({ symbol: "", quantity: "", avg_price: "", buy_date: today(), note: "", ...initial });
      save.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const quantity = Number(draft.quantity);
  const price = Number(draft.avg_price);
  const valid = draft.symbol && Number.isInteger(quantity) && quantity > 0 && price > 0 && draft.buy_date;
  const submit = () => {
    const input: HoldingInput = {
      symbol: draft.symbol,
      quantity,
      avg_price: draft.avg_price,
      buy_date: draft.buy_date,
      note: draft.note,
    };
    save.mutate({ id: draft.id, input }, { onSuccess: () => onOpenChange(false) });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={draft.id ? `Edit ${draft.symbol}` : "Add a holding"}
      description="Enter what you bought. QuantOS values it at the latest close and compares it with NIFTY bought on the same day."
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid} loading={save.isPending}>
            {draft.id ? "Save changes" : "Add holding"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <Field label="Stock or ETF">
          {lockSymbol || draft.id ? (
            <div className="flex h-10 items-center rounded-[var(--radius-control)] border border-line bg-surface-2 px-3 text-sm font-semibold text-ink">{draft.symbol}</div>
          ) : draft.symbol ? (
            <div className="flex items-center justify-between rounded-[var(--radius-control)] border border-line bg-surface-2 px-3 py-2 text-sm">
              <span className="font-semibold text-ink">{draft.symbol}</span>
              <button type="button" className="text-[13px] font-medium text-brand hover:underline" onClick={() => setDraft({ ...draft, symbol: "" })}>
                Change
              </button>
            </div>
          ) : (
            <SymbolSearch onPick={(symbol) => setDraft({ ...draft, symbol })} autoFocus />
          )}
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Quantity" htmlFor="h-qty">
            <Input id="h-qty" inputMode="numeric" value={draft.quantity} onChange={(e) => setDraft({ ...draft, quantity: e.target.value.replace(/\D/g, "") })} />
          </Field>
          <Field label="Average price" htmlFor="h-price">
            <Input id="h-price" prefix="₹" inputMode="decimal" value={draft.avg_price} onChange={(e) => setDraft({ ...draft, avg_price: e.target.value.replace(/[^\d.]/g, "") })} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Bought on" htmlFor="h-date">
            <Input id="h-date" type="date" max={today()} value={draft.buy_date} onChange={(e) => setDraft({ ...draft, buy_date: e.target.value })} />
          </Field>
          <Field label="Note (optional)" htmlFor="h-note">
            <Input id="h-note" maxLength={200} value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} />
          </Field>
        </div>
        {valid && <p className="text-[13px] text-ink-3">Cost {inr(quantity * price)}</p>}
        {save.isError && <Callout tone="danger">{errorMessage(save.error)}</Callout>}
      </div>
    </Dialog>
  );
}
