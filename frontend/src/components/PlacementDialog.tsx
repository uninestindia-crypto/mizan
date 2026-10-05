import { useEffect, useId, useState } from "react";
import { errorMessage } from "../lib/api";
import { parsePlacementFields } from "../lib/orderTicket";
import { useClearPlacement, useRecordPlacement } from "../lib/queries";
import type { Placement, PlacementStatus } from "../lib/types";
import { Button, Dialog, Field, Input, Segmented } from "./ui";

export interface PlacementTarget {
  bookId: string;
  asOf: string;
  symbol: string;
  side: "BUY" | "SELL";
  /** The share count scaled to the person's own account, offered as the starting value. */
  suggestedShares: number;
  existing: Placement | null;
}

/** "I placed this" / "I skipped this": a note you keep, never an instruction sent anywhere. */
export function PlacementDialog({ target, onClose }: { target: PlacementTarget | null; onClose: () => void }) {
  const sharesId = useId();
  const priceId = useId();
  const [status, setStatus] = useState<PlacementStatus>("PLACED");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const record = useRecordPlacement(target?.bookId ?? "");
  const clear = useClearPlacement(target?.bookId ?? "");

  useEffect(() => {
    if (!target) return;
    setStatus(target.existing?.status ?? "PLACED");
    setShares(String(target.existing?.quantity ?? target.suggestedShares));
    setPrice(target.existing?.price != null ? String(target.existing.price) : "");
    setProblem(null);
    record.reset();
    clear.reset();
    // Reset only when a different order is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target?.bookId, target?.asOf, target?.symbol, target?.side]);

  if (!target) return null;

  const save = () => {
    const fields = parsePlacementFields(status, shares, price);
    if (!fields.ok) {
      setProblem(fields.error);
      return;
    }
    setProblem(null);
    record.mutate(
      { as_of: target.asOf, symbol: target.symbol, side: target.side, status, quantity: fields.quantity, price: fields.price },
      { onSuccess: onClose },
    );
  };

  const remove = () =>
    clear.mutate({ as_of: target.asOf, symbol: target.symbol, side: target.side }, { onSuccess: onClose });

  const failure = problem ?? (record.isError ? errorMessage(record.error) : clear.isError ? errorMessage(clear.error) : null);

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={`${target.side === "BUY" ? "Buy" : "Sell"} ${target.symbol}`}
      description="Note what you did, so QuantOS can show how your copy compares with the paper book. It places nothing and checks nothing with your broker."
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <div>
            {target.existing && (
              <Button variant="ghost" onClick={remove} loading={clear.isPending}>
                Clear note
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={save} loading={record.isPending}>
              Save
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Segmented<PlacementStatus>
          label="What you did"
          value={status}
          onChange={setStatus}
          options={[
            { value: "PLACED", label: "I placed it" },
            { value: "SKIPPED", label: "I skipped it" },
          ]}
        />
        {status === "PLACED" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Shares you placed" htmlFor={sharesId}>
              <Input id={sharesId} inputMode="numeric" value={shares} onChange={(e) => setShares(e.target.value)} />
            </Field>
            <Field label="Your price (optional)" htmlFor={priceId} hint="What you actually got per share.">
              <Input id={priceId} prefix="₹" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
            </Field>
          </div>
        )}
        {failure && (
          <p role="alert" className="text-[13px] text-down">
            {failure}
          </p>
        )}
      </div>
    </Dialog>
  );
}
