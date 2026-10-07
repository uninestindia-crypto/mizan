import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { chatListKey, historyApi, isChatGone } from "../../../lib/copilotHistory";
import { useCopilot } from "../CopilotProvider";

export interface ChatActions {
  /** Throws the engine's own sentence when the name is refused. */
  rename: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  clearAll: () => Promise<void>;
}

interface OpenChat {
  chatId: string | null;
  newChat: () => void;
}

/** A chat that is already gone is as good as deleted. */
async function removeChat(id: string): Promise<void> {
  try {
    await historyApi.remove(id);
  } catch (error) {
    if (!isChatGone(error)) throw error;
  }
}

function makeActions(client: QueryClient, open: OpenChat): ChatActions {
  const refresh = () => client.invalidateQueries({ queryKey: chatListKey });
  return {
    rename: async (id, title) => {
      await historyApi.rename(id, title);
      await refresh();
    },
    remove: async (id) => {
      await removeChat(id);
      if (id === open.chatId) open.newChat();
      await refresh();
    },
    clearAll: async () => {
      await historyApi.clear();
      open.newChat();
      await refresh();
    },
  };
}

/** Renaming and deleting saved chats. Deleting the open chat also empties the thread, so nothing is sent to it. */
export function useChatActions(): ChatActions {
  const client = useQueryClient();
  const { chatId, newChat } = useCopilot();
  return useMemo(() => makeActions(client, { chatId, newChat }), [client, chatId, newChat]);
}
