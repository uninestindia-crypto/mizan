// Shared set-up for the Copilot chat screen tests: the drawer with its button, and a fake engine that answers chat.

import { fireEvent, screen } from "@testing-library/react";
import { CopilotButton } from "./CopilotButton";
import { CopilotDrawer } from "./CopilotDrawer";
import { CopilotProvider } from "./CopilotProvider";
import { routeApi } from "./testHarness";

export const CHAT = "/api/v2/copilot/chat";

export function Shell() {
  return (
    <CopilotProvider>
      <CopilotButton />
      <CopilotDrawer />
    </CopilotProvider>
  );
}

export const reply = (over: Record<string, unknown> = {}) => ({
  reply: "TCS passes both standards.",
  steps: [],
  proposals: [],
  mode: "ai",
  provider: "openai",
  model: "gpt-x",
  error: null,
  ...over,
});

export function chatWith(...replies: unknown[]) {
  const queue = [...replies];
  routeApi({ [`POST ${CHAT}`]: () => queue.shift() ?? reply() });
}

export const openDrawer = () => fireEvent.click(screen.getByRole("button", { name: /Copilot/ }));
export const box = () => screen.getByRole("textbox", { name: "Your message to the Copilot" });
export async function say(text: string) {
  fireEvent.change(box(), { target: { value: text } });
  fireEvent.keyDown(box(), { key: "Enter" });
}
