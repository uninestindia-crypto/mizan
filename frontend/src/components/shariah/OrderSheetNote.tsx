import { Download } from "lucide-react";
import { Button } from "../ui";

/** The order sheet stays off while prices are samples: the number of shares worked out from one would be wrong. */
export function OrderSheetNote() {
  return (
    <div className="mt-6 space-y-2 border-t border-line pt-4">
      <h3 className="text-[13px] font-semibold text-ink">Order-sheet export</h3>
      <p className="text-xs text-ink-2">
        QuantOS does not place orders. It prepares a sheet you can use at your broker.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-ink-3">
          The sheet stays off while the prices here are samples, because the number of shares worked out from them would
          be wrong.
        </span>
        <Button size="sm" variant="secondary" icon={<Download className="size-3.5" />} disabled>
          Order sheet unavailable
        </Button>
      </div>
    </div>
  );
}
