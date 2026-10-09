import { useEffect, useRef } from "react";
import { forgetChat, rememberChat, rememberedChat } from "../../../lib/copilotHistory";
import type { OpenResult } from "./useOpenChat";

/** Remembers which chat is open, so the next time the Copilot opens it can pick up where it was. */
export function useRememberedChat(chatId: string | null): void {
  useEffect(() => {
    if (chatId) rememberChat(chatId);
  }, [chatId]);
}

/**
 * The first time the drawer opens after QuantOS starts, reopens the chat that was open last time. A chat that is gone
 * is forgotten without a word, and the person simply sees a fresh chat.
 */
export function useReopenLastChat(open: boolean, openChat: (id: string) => Promise<OpenResult>): void {
  const tried = useRef(false);
  useEffect(() => {
    if (!open || tried.current) return;
    tried.current = true;
    const id = rememberedChat();
    if (!id) return;
    void openChat(id).then((result) => {
      if (result === "missing" && rememberedChat() === id) forgetChat();
    });
  }, [open, openChat]);
}
