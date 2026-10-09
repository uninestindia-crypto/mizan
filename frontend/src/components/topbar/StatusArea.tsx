import { useRef, useState } from "react";
import { UpdateDialog } from "../update/UpdateDialog";
import { ChipRow } from "./Chip";
import type { StatusItem } from "./statusItems";
import { StatusPopover } from "./StatusPopover";
import { useStatusItems } from "./useStatusItems";

export type AreaLayout = "inline" | "popover" | "phone";

/**
 * Everything the bar says about the market, the prices, live prices and updates, in the shape that fits: chips side
 * by side, one "Status" button on a narrow bar, or the phone's icon button. It also owns the update window, which the
 * update chip (or its row in the list) opens.
 */
export function StatusArea({ layout }: { layout: AreaLayout }) {
  const items = useStatusItems();
  const [updateOpen, setUpdateOpen] = useState(false);
  const area = useRef<HTMLDivElement>(null);
  const onAction = (item: StatusItem) => {
    if (item.action === "update") setUpdateOpen(true);
  };
  // When the control that opened the window has gone, focus goes to the area's own button, then to its first control.
  const fallbackFocus = () =>
    area.current?.querySelector<HTMLElement>("[data-status-trigger]") ??
    area.current?.querySelector<HTMLElement>("a, button") ??
    null;
  return (
    <div ref={area} className="contents">
      {layout === "inline" ? (
        <ChipRow items={items} onAction={onAction} />
      ) : (
        <StatusPopover
          items={items}
          onAction={onAction}
          anchor={layout === "phone" ? "bar" : "button"}
          compact={layout === "phone"}
        />
      )}
      <UpdateDialog open={updateOpen} onOpenChange={setUpdateOpen} fallbackFocus={fallbackFocus} />
    </div>
  );
}
