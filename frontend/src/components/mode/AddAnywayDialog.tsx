import type { ShariahStatus } from "../../lib/shariahStatus";
import { Button, Dialog } from "../ui";

/** The sentence the person answers: what the Shariah screening says about this stock, and the question. */
export function addAnywayQuestion(symbol: string, status: ShariahStatus | null): string {
  const reason = status?.short.replace(/\.+$/, "");
  const because = reason ? ` (${reason})` : "";
  const ask = `${because}. Add it anyway?`;
  if (status?.verdict === "NON_COMPLIANT") return `${symbol} is not Shariah-compliant${ask}`;
  if (status?.verdict === "QUESTIONABLE") return `${symbol} is questionable under Shariah screening${ask}`;
  return `${symbol} has not been screened for Shariah compliance${ask}`;
}

/** Asks first, in Shariah mode, before a stock that is not confirmed compliant goes on a watchlist. */
export function AddAnywayDialog({
  symbol,
  status,
  open,
  onAdd,
  onCancel,
}: {
  symbol: string;
  status: ShariahStatus | null;
  open: boolean;
  onAdd: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && onCancel()}
      title="Add to your watchlist?"
      description={addAnywayQuestion(symbol, status)}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Don't add
          </Button>
          <Button onClick={onAdd}>Add anyway</Button>
        </>
      }
    >
      <p className="text-[13px] text-ink-3">
        Watching a stock only follows its price on your Home screen. It does not buy anything.
      </p>
    </Dialog>
  );
}
