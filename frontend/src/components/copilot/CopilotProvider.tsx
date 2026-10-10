import { createContext, type ReactNode, useContext, useMemo } from "react";
import { useLocation } from "react-router";
import { type HistoryView, useHistoryView } from "./history/useHistoryView";
import { useReopenLastChat } from "./history/useRememberedChat";
import { type ChatSession, useChatSession } from "./useChatSession";
import { type Drawer, useDrawer } from "./useDrawer";

type CopilotContextValue = Drawer & ChatSession & HistoryView;

const CopilotContext = createContext<CopilotContextValue | null>(null);

export function useCopilot(): CopilotContextValue {
  const value = useContext(CopilotContext);
  if (!value) throw new Error("useCopilot needs the Copilot provider around it.");
  return value;
}

/**
 * Holds the conversation, the list of saved chats' panel and the open/closed state above every screen, so closing the
 * drawer loses nothing. The first time the drawer opens, it reopens the chat that was open last time.
 */
export function CopilotProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const drawer = useDrawer();
  const chat = useChatSession(pathname);
  const history = useHistoryView(drawer.open);
  useReopenLastChat(drawer.open, chat.openChat);
  const value = useMemo(() => ({ ...drawer, ...chat, ...history }), [drawer, chat, history]);
  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}
