import { useState } from "react";
import { Confirm } from "./Confirm";
import type { ChatActions } from "./useChatActions";

/** The one way to remove every saved chat at once. It asks first, and says plainly what is lost. */
export function ClearAll({ clearAll }: { clearAll: ChatActions["clearAll"] }) {
  const [asking, setAsking] = useState(false);
  if (asking) {
    return (
      <div className="px-1">
        <Confirm
          question="Clear all history? Every saved chat will be deleted. This cannot be undone."
          confirmLabel="Clear all"
          onConfirm={clearAll}
          onKeep={() => setAsking(false)}
        />
      </div>
    );
  }
  return (
    <div className="px-4 py-2.5">
      <button
        type="button"
        onClick={() => setAsking(true)}
        className="rounded text-[13px] text-ink-3 underline underline-offset-2 hover:text-ink"
      >
        Clear all history
      </button>
    </div>
  );
}
