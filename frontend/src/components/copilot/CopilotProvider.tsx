import { createContext, type ReactNode, useContext, useMemo } from "react";
import { useLocation } from "react-router";
import { type ChatSession, useChatSession } from "./useChatSession";
import { type Drawer, useDrawer } from "./useDrawer";

type CopilotContextValue = Drawer & ChatSession;

const CopilotContext = createContext<CopilotContextValue | null>(null);

export function useCopilot(): CopilotContextValue {
  const value = useContext(CopilotContext);
  if (!value) throw new Error("useCopilot needs the Copilot provider around it.");
  return value;
}

/** Holds the conversation and the open/closed state above every screen, so closing the drawer loses nothing. */
export function CopilotProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const drawer = useDrawer();
  const chat = useChatSession(pathname);
  const value = useMemo(() => ({ ...drawer, ...chat }), [drawer, chat]);
  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}
