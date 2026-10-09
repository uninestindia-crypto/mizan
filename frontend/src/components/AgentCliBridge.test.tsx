import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { APPS_ANCHOR, showAppSetup } from "../lib/aiSource";
import { ApiError, api } from "../lib/api";
import type { AgentCli } from "../lib/types";
import { callsTo, renderApp, routeApi } from "./agents/testHarness";
import { AgentCliBridge } from "./AgentCliBridge";
import { app, buttonsIn, cardOf, job, LAUNCH, shown, startsJob, STATUS } from "./aiapps/appFixtures";

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return { ...original, api: vi.fn() };
});

// The engine lists them in its own order: Antigravity, Codex, Claude Code, Gemini.
const LISTED = [
  app("antigravity", "UNKNOWN"),
  app("codex", "NEEDS_SIGN_IN"),
  app("claude"),
  app("gemini", "NOT_INSTALLED"),
];
const click = (element: HTMLElement) => fireEvent.click(element);
const bodyText = () => document.body.textContent ?? "";

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

const LINES = [
  ["Claude Code", "by Anthropic", "Anthropic's AI assistant. Sign in with your Claude account."],
  ["Codex", "by OpenAI", "OpenAI's AI assistant. Sign in with your ChatGPT account."],
  ["Gemini", "by Google", "Google's AI assistant. Sign in with your Google account."],
  ["Antigravity", "by Google", "Google's AI app. It cannot answer Copilot questions yet."],
] as const;

describe("the words on the card", () => {
  it("is titled in plain words and lists the apps without the word CLI, the AI choice's order first", async () => {
    await shown(LISTED);
    expect(screen.getByRole("heading", { level: 2, name: "Set up AI apps on this computer" })).toBeInTheDocument();
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names).toEqual(["Claude Code", "Codex", "Gemini", "Antigravity"]);
  });

  it.each(LINES)("%s: says who makes it and what it is in one plain line", async (name, maker, line) => {
    await shown(LISTED);
    const card = cardOf(name);
    expect(card.getByText(maker)).toBeInTheDocument();
    expect(card.getByText(line)).toBeInTheDocument();
  });

  it("uses its own plain words, not the engine's words for programmers", async () => {
    await shown(LISTED);
    expect(bodyText()).not.toMatch(/\bCLI\b|terminal|command|npm|PowerShell|ANTHROPIC_API_KEY|coding agent/i);
  });

  it("no longer tells people the apps are optional extras", async () => {
    await shown(LISTED);
    expect(bodyText()).not.toMatch(/Coding agents|nothing in QuantOS needs it|Optional/);
  });

  it("explains an install in one plain sentence instead of printing the installer's steps", async () => {
    await shown(LISTED);
    const sentence =
      "QuantOS downloads the official app from Google and sets it up for you. It can take a few minutes.";
    expect(cardOf("Gemini").getByText(sentence)).toBeInTheDocument();
    expect(document.querySelector("code")).toBeNull();
    expect(screen.queryByText(/What Install will run/)).toBeNull();
  });
});

const STATES: [string, AgentCli["state"], string, string[]][] = [
  ["not installed", "NOT_INSTALLED", "Not installed", ["Install Codex"]],
  ["installed but not signed in", "NEEDS_SIGN_IN", "Installed, not signed in", ["Sign in to Codex"]],
  ["installed and not checked yet", "UNKNOWN", "Installed, not checked yet", ["Sign in to Codex", "Test this AI"]],
  ["signed in", "CONNECTED", "Signed in", ["Test this AI"]],
];

describe("the state of an app and its one next step", () => {
  it.each(STATES)("%s", async (_name, state, badge, buttons) => {
    await shown([app("codex", state)]);
    const card = cardOf("Codex");
    expect(card.getByText(badge)).toBeInTheDocument();
    expect(buttonsIn(card)).toEqual(buttons);
  });

  it("offers Antigravity the same steps, but no test, because it cannot answer Copilot questions yet", async () => {
    await shown([app("antigravity", "UNKNOWN")]);
    expect(buttonsIn(cardOf("Antigravity"))).toEqual(["Sign in to Antigravity"]);
  });

  it("leaves a signed-in Antigravity with nothing to press", async () => {
    await shown([app("antigravity", "CONNECTED")]);
    expect(buttonsIn(cardOf("Antigravity"))).toEqual([]);
    expect(cardOf("Antigravity").getByText("Signed in")).toBeInTheDocument();
  });
});

describe("nothing here needs a terminal", () => {
  it("has no button, link or box for a terminal, a launch or a command of one's own", async () => {
    await shown(LISTED);
    const names = [...buttonsIn(cardOf("Claude Code")), ...buttonsIn(cardOf("Codex")), ...buttonsIn(cardOf("Gemini"))];
    expect(names.filter((n) => /terminal|launch|command|advanced/i.test(n))).toEqual([]);
    expect(screen.queryAllByRole("textbox")).toEqual([]);
    expect(document.querySelector("details")).toBeNull();
  });

  it("only ever asks the engine to install or to sign in", async () => {
    await shown(LISTED, startsJob("gemini", job({ action: "install" })));
    click(cardOf("Gemini").getByRole("button", { name: "Install Gemini" }));
    await waitFor(() => expect(callsTo("POST", LAUNCH)).toHaveLength(1));
    click(cardOf("Codex").getByRole("button", { name: "Sign in to Codex" }));
    await waitFor(() => expect(callsTo("POST", LAUNCH)).toHaveLength(2));
    expect(callsTo("POST", LAUNCH)).toEqual([
      { agent_id: "gemini", action: "install" },
      { agent_id: "codex", action: "signin" },
    ]);
  });
});

const JUMPS = [
  ["Codex", "Sign in to Codex"],
  ["Gemini", "Install Gemini"],
] as const;

describe("the Set up button on the AI choice above", () => {
  it.each(JUMPS)("lands on that app's own card (%s) and focuses its button", async (engineName, button) => {
    const anchored = (
      <div id={APPS_ANCHOR} tabIndex={-1}>
        <AgentCliBridge />
      </div>
    );
    await shown(LISTED, undefined, anchored);
    showAppSetup(engineName);
    expect(screen.getByRole("button", { name: button })).toHaveFocus();
  });
});

describe("when the engine cannot list the apps", () => {
  it("says so in the engine's own plain words", async () => {
    routeApi({
      [`GET ${STATUS}`]: () => {
        throw new ApiError("ENGINE_OFFLINE", "QuantOS is still starting. Try again in a moment.", 0);
      },
    });
    renderApp(<AgentCliBridge />);
    expect(await screen.findByRole("alert")).toHaveTextContent("QuantOS is still starting. Try again in a moment.");
  });
});
