import { errorMessage } from "../../lib/api";
import { date } from "../../lib/format";
import { useDeleteHolding } from "../../lib/queries";
import type { PortfolioRow } from "../../lib/types";
import { Button, Callout, Dialog } from "../ui";

/** Asks before a purchase is taken off the Portfolio. It is removed from QuantOS only; nothing is sold. */
export function RemoveLotDialog({ row, onClose }: { row: PortfolioRow | null; onClose: () => void }) {
  const remove = useDeleteHolding();
  const where = row?.account_name ? ` in ${row.account_name}` : "";
  const bought = row ? ` bought ${date(row.buy_date)}` : "";
  const confirm = () => {
    if (row) remove.mutate(row.id, { onSuccess: onClose });
  };
  return (
    <Dialog
      open={row !== null}
      onOpenChange={(open) => !open && onClose()}
      title={`Remove ${row?.symbol ?? ""}${where}?`}
      description={`This removes the holding${bought} from QuantOS only. Nothing is sold.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Keep
          </Button>
          <Button variant="danger" loading={remove.isPending} onClick={confirm}>
            Remove
          </Button>
        </>
      }
    >
      {remove.isError ? <Callout tone="danger">{errorMessage(remove.error)}</Callout> : <span />}
    </Dialog>
  );
}
