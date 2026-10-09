import { type ChatReply, normaliseReply } from "../../../lib/copilot";
import type { ChatDetail } from "../../../lib/copilotHistory";
import type { SavedMessage } from "../chatState";

/** An answer kept by the engine, read the way a live reply is, so it shows its steps and buttons exactly as it did. */
function assistantMessage(content: string, meta: Record<string, unknown>): SavedMessage {
  const { reply, ...rest } = normaliseReply({ ...meta, reply: content } as Partial<ChatReply>);
  return { ...rest, role: "assistant", content: reply, savedNote: null };
}

/** The messages of a saved chat, ready to put in the thread. */
export function savedMessages(detail: ChatDetail): SavedMessage[] {
  return detail.turns.map((turn) =>
    turn.role === "user" ? { role: "user", content: turn.content } : assistantMessage(turn.content, turn.meta),
  );
}
