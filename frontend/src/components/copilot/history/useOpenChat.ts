import { useCallback, useRef, useState } from "react";
import { historyApi, isChatGone } from "../../../lib/copilotHistory";
import type { Apply, ChatStore } from "./chatStore";
import { savedMessages } from "./savedChat";

/** "ignored": the person did something else first (typed a question, opened another chat), so this one was dropped. */
export type OpenResult = "opened" | "missing" | "failed" | "ignored";

/** Fetches a saved chat and puts it in the thread, unless the person has moved on (`wanted` says so) by then. */
async function load(id: string, wanted: () => boolean, apply: Apply): Promise<OpenResult> {
  try {
    const detail = await historyApi.get(id);
    if (!wanted()) return "ignored";
    apply({ type: "opened", chatId: id, messages: savedMessages(detail) });
    return "opened";
  } catch (error) {
    if (!wanted()) return "ignored";
    return isChatGone(error) ? "missing" : "failed";
  }
}

/** Puts a saved chat in the thread. It reports what happened and shows nothing; the screen that asked decides. */
export function useOpenChat({ live, apply }: ChatStore) {
  const [openingChat, setOpening] = useState(false);
  const inFlight = useRef(0);

  const openChat = useCallback(
    async (id: string): Promise<OpenResult> => {
      const mine = ++live.current.opening;
      inFlight.current += 1;
      setOpening(true);
      try {
        return await load(id, () => live.current.opening === mine, apply);
      } finally {
        inFlight.current -= 1;
        setOpening(inFlight.current > 0);
      }
    },
    [live, apply],
  );
  return { openChat, openingChat };
}
