import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Agent } from "../../lib/agents";
import { api } from "../../lib/api";
import Agents from "../../pages/Agents";
import { AI_APP_READY, engine, mine, needsAi, ready } from "./agentFixtures";
import { AgentCard } from "./AgentCard";
import { renderApp } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

const show = (agent: Agent, noAiKey: boolean) =>
  renderApp(<AgentCard agent={agent} tools={undefined} actions={null} noAiKey={noAiKey} />);

describe("the note on an agent that needs an AI", () => {
  it("sends a person with no AI set up to Settings, then AI assistants", () => {
    show(needsAi, true);
    const link = screen.getByRole("link", { name: "Settings, then AI assistants" });
    expect(link).toHaveAttribute("href", "/settings/ai");
    expect(screen.getByText(/Needs an AI\./)).toBeInTheDocument();
  });

  it("never sends a person to Accounts and keys to get an AI, or says AI key", () => {
    show(needsAi, true);
    expect(screen.queryByRole("link", { name: /Accounts/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/AI key/);
  });

  const NOTE_CASES = [
    ["an AI is ready", needsAi, false],
    ["the agent works without an AI", ready, true],
    ["the agent is the person's own", mine, true],
  ] as const;

  it.each(NOTE_CASES)("says nothing when %s", (_name, agent, noAi) => {
    show(agent, noAi);
    expect(screen.queryByRole("link", { name: /AI assistants/ })).toBeNull();
  });
});

describe("the Agents screen with only an AI app on this computer ready", () => {
  it("shows no note, because an AI app answers an agent as well as a key does", async () => {
    engine({ "GET /api/v2/copilot/models": AI_APP_READY });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "Read the news" });
    expect(screen.queryByText(/Needs an AI/)).toBeNull();
  });
});
