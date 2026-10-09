import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type AiApp, type AiChoice, type AiSettings, type AiStatus, APPS_ANCHOR, applyPatch } from "../../lib/aiSource";
import { ApiError, api } from "../../lib/api";
import { callsTo, deferred, renderApp, routeApi } from "../agents/testHarness";
import { AiSource } from "./AiSource";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const CLAUDE_OK = "Claude Code (sign-in) answered, so it is ready to use.";
const GOES_TO_CLAUDE = "Right now your questions go to Claude Code, with your saved OpenAI key as a backup.";
const GOES_TO_KEY = "Right now your questions go to your saved OpenAI key, with Claude Code as a backup.";
const FALLBACK_LINE =
  "Your question is only ever sent to an AI you have set up. Turn this off to keep it to one kind.";
const STATUS = "/api/v2/copilot/status";
const SETTINGS = "/api/v2/settings";
const TEST = "/api/v2/copilot/ai/test";

const app = (id: AiApp["id"], name: string, state: AiApp["state"]): AiApp => ({
  id,
  name,
  label: `${name} (sign-in)`,
  state,
  installed: state !== "NOT_INSTALLED",
  ready: state === "CONNECTED",
});

const LABELS = ["Anthropic (Claude)", "OpenAI", "Google Gemini", "Groq", "DeepSeek", "Mistral", "OpenRouter"];
const IDS = ["anthropic", "openai", "gemini", "groq", "deepseek", "mistral", "openrouter"];
const keys = (...saved: string[]) => IDS.map((id, at) => ({ id, label: LABELS[at] ?? id, ready: saved.includes(id) }));

const AUTO: AiChoice = { source: "cli", cli: null, api: null, fallback: true };
const BASE: AiStatus = {
  ai_ready: true,
  apps: [
    app("claude", "Claude Code", "CONNECTED"),
    app("codex", "Codex", "NEEDS_SIGN_IN"),
    app("antigravity", "Antigravity", "NOT_INSTALLED"),
  ],
  ai: AUTO,
  providers: keys("openai"),
};

function settingsOf(ai: AiChoice): AiSettings {
  return { ai_source: ai.source, ai_cli: ai.cli, ai_api: ai.api, ai_fallback: ai.fallback };
}

/** A fake engine that keeps the choice a save sends, so the screen shows it back as the real one does. */
function engine(over: Partial<AiStatus> = {}, extra: Record<string, unknown> = {}) {
  const state: AiStatus = { ...BASE, ...over };
  routeApi({
    [`GET ${STATUS}`]: () => structuredClone(state),
    "GET /api/v2/cli/status": [],
    [`PUT ${SETTINGS}`]: (body: unknown) => {
      state.ai = applyPatch(state.ai, body as Partial<AiSettings>);
      return settingsOf(state.ai);
    },
    [`POST ${TEST}`]: { ok: true, who: "Claude Code (sign-in)", message: CLAUDE_OK },
    ...extra,
  });
  return state;
}

const OPENAI_OK = "OpenAI answered, so it is ready to use.";
const removed = (a: AiApp): AiApp => ({ ...a, state: "NOT_INSTALLED", installed: false, ready: false });
const radio = (name: RegExp | string) => screen.getByRole("radio", { name });
const rowOf = (name: RegExp) => within(radio(name).closest("li") as HTMLElement);
const click = (element: HTMLElement) => fireEvent.click(element);
const sent = (method: string, path: string) => callsTo(method, path);

async function shown(over: Partial<AiStatus> = {}, extra: Record<string, unknown> = {}) {
  const state = engine(over, extra);
  const view = renderApp(<AiSource />);
  await screen.findByRole("heading", { name: "Which AI should answer your questions?" });
  await screen.findByRole("button", { name: "Test this AI" });
  return { state, ...view };
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the summary at the top", () => {
  it("says where questions go right now", async () => {
    await shown();
    expect(screen.getByText(GOES_TO_CLAUDE)).toBeInTheDocument();
  });

  it("says plainly when no AI is set up", async () => {
    await shown({ apps: BASE.apps.map(removed), providers: keys() });
    expect(screen.getByText("No AI is set up yet.")).toBeInTheDocument();
  });

  it("follows a change of source", async () => {
    await shown();
    click(radio(/An AI key I saved/));
    expect(await screen.findByText(GOES_TO_KEY)).toBeInTheDocument();
  });

  it("follows the backup being turned off", async () => {
    await shown();
    click(screen.getByRole("switch", { name: /try the other kind/ }));
    expect(await screen.findByText("Right now your questions go to Claude Code and nowhere else.")).toBeInTheDocument();
  });
});

describe("the two kinds of AI", () => {
  it("offers the AI app on this computer first, recommended and selected, in a labelled group", async () => {
    await shown();
    const group = screen.getByRole("group", { name: "Where your answers come from" });
    expect(within(group).getAllByRole("radio")).toHaveLength(2);
    expect(radio(/The AI app on this computer/)).toBeChecked();
    expect(radio(/The AI app on this computer/)).toHaveAccessibleDescription(/No key needed/);
    expect(within(group).getByText("Recommended")).toBeInTheDocument();
    expect(radio(/An AI key I saved/)).not.toBeChecked();
  });

  it("points to Accounts and keys for the saved key", async () => {
    await shown();
    expect(screen.getByRole("link", { name: "Open Accounts & keys" })).toHaveAttribute("href", "/settings/accounts");
  });

  it("is saved at once, with a small confirmation", async () => {
    await shown();
    click(radio(/An AI key I saved/));
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(sent("PUT", SETTINGS)).toEqual([{ ai_source: "api" }]);
  });

  it("keeps the person's click if the save fails, says so plainly, and puts the choice back", async () => {
    await shown({}, {
      [`PUT ${SETTINGS}`]: () => {
        throw new ApiError("INVALID_SETTINGS", "ai_source: Input should be 'cli' or 'api'", 422);
      },
    });
    click(radio(/An AI key I saved/));
    const note = await screen.findByRole("alert");
    expect(note).toHaveTextContent("That choice could not be saved, so nothing was changed. Please try again.");
    expect(document.body.textContent).not.toMatch(/INVALID_SETTINGS|Input should be/);
    await waitFor(() => expect(radio(/The AI app on this computer/)).toBeChecked());
  });
});

describe("which AI to prefer", () => {
  const PREFER_CASES = [
    ["Codex", () => radio(/^Codex/), { ai_cli: "codex" }],
    ["Claude Code", () => radio(/^Claude Code/), { ai_cli: "claude" }],
  ] as const;

  it.each(PREFER_CASES)("choosing %s saves it", async (_name, pick, body) => {
    await shown();
    click(pick());
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([body]));
  });

  it("leaves it to the first one that is ready when Automatic is chosen", async () => {
    await shown({ ai: { ...AUTO, cli: "claude" } });
    click(radio("Automatic (first one that is ready)"));
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([{ ai_cli: null }]));
  });

  it("starts on Automatic, and on the favourite when there is one", async () => {
    await shown({ ai: { ...AUTO, cli: "codex" } });
    expect(radio(/^Codex/)).toBeChecked();
    expect(radio("Automatic (first one that is ready)")).not.toBeChecked();
  });

  it("names the apps with a chip each and a Set up button only where something is missing", async () => {
    await shown();
    expect(rowOf(/^Claude Code/).getByText("Ready")).toBeInTheDocument();
    expect(rowOf(/^Codex/).getByText("Not signed in")).toBeInTheDocument();
    expect(rowOf(/^Antigravity/).getByText("Not installed")).toBeInTheDocument();
    expect(rowOf(/^Claude Code/).queryByRole("button")).toBeNull();
    const setUp = screen.getAllByRole("button", { name: /^Set up/ });
    expect(setUp.map((b) => b.getAttribute("aria-label"))).toEqual(["Set up Antigravity", "Set up Codex"]);
  });

  it("says an app that cannot report its sign-in has not been checked yet", async () => {
    await shown({ apps: [app("antigravity", "Antigravity", "UNKNOWN")] });
    expect(screen.getByText("Not checked yet. Press Test this AI.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Set up/ })).toBeNull();
  });

  it("lists the saved keys instead, with a chip each, once the key kind is chosen", async () => {
    await shown({ ai: { ...AUTO, source: "api" } });
    expect(rowOf(/^OpenAI/).getByText("Key saved")).toBeInTheDocument();
    expect(rowOf(/^Groq/).getByText("No key yet")).toBeInTheDocument();
    const add = screen.getByRole("link", { name: "Add a key under Accounts & keys" });
    expect(add).toHaveAttribute("href", "/settings/accounts");
    expect(screen.queryByRole("radio", { name: /^Codex/ })).toBeNull();
  });

  it("saves a favourite key", async () => {
    await shown({ ai: { ...AUTO, source: "api" } });
    click(radio(/^OpenAI/));
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([{ ai_api: "openai" }]));
  });

  it("takes a person to that app's own card with Set up", async () => {
    engine();
    renderApp(
      <>
        <AiSource />
        <div id={APPS_ANCHOR} tabIndex={-1}>
          <div className="rounded-xl" data-app-name="Codex">
            <h3>Codex</h3>
            <button>Sign in with browser</button>
          </div>
        </div>
      </>,
    );
    click(await screen.findByRole("button", { name: "Set up Codex" }));
    expect(screen.getByRole("button", { name: "Sign in with browser" })).toHaveFocus();
  });

  it("lands on Antigravity's card too, now that its name no longer carries the developer's word", async () => {
    engine();
    renderApp(
      <>
        <AiSource />
        <div id={APPS_ANCHOR} tabIndex={-1}>
          <div className="rounded-xl" data-app-name="Codex">
            <button>Sign in with browser</button>
          </div>
          <div className="rounded-xl" data-app-name="Antigravity">
            <h3>Antigravity</h3>
            <button>Install Antigravity</button>
          </div>
        </div>
      </>,
    );
    click(await screen.findByRole("button", { name: "Set up Antigravity" }));
    expect(screen.getByRole("button", { name: "Install Antigravity" })).toHaveFocus();
  });
});

describe("the backup", () => {
  it("is on by default and explains itself in one line", async () => {
    await shown();
    expect(screen.getByRole("switch", { name: "If that AI can't answer, try the other kind" })).toBeChecked();
    expect(screen.getByText(FALLBACK_LINE)).toBeInTheDocument();
  });

  it("is saved when turned off", async () => {
    await shown();
    click(screen.getByRole("switch", { name: /try the other kind/ }));
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([{ ai_fallback: false }]));
  });
});

describe("Test this AI", () => {
  it("asks whichever AI the Copilot would use when none is preferred, and shows the answer", async () => {
    await shown();
    expect(screen.getByText("Tests whichever AI your questions go to first.")).toBeInTheDocument();
    click(screen.getByRole("button", { name: "Test this AI" }));
    expect(await screen.findByText("Claude Code (sign-in) answered, so it is ready to use.")).toBeInTheDocument();
    expect(sent("POST", TEST)).toEqual([{}]);
  });

  const TEST_TARGET_CASES = [
    ["an app", { ...AUTO, cli: "codex" as const }, { model: "cli:codex" }],
    ["a key", { ...AUTO, source: "api" as const, api: "openai" }, { model: "openai" }],
  ] as const;

  it.each(TEST_TARGET_CASES)("asks the preferred %s by name", async (_name, ai, body) => {
    await shown({ ai });
    click(screen.getByRole("button", { name: "Test this AI" }));
    await waitFor(() => expect(sent("POST", TEST)).toEqual([body]));
  });

  it("shows a failed test inline, in the engine's own words, never as an alert", async () => {
    const message = "Codex is not signed in yet. Open Settings, then AI assistants, and choose Sign in.";
    await shown({}, { [`POST ${TEST}`]: { ok: false, who: "Codex (sign-in)", message } });
    click(screen.getByRole("button", { name: "Test this AI" }));
    expect(await screen.findByText(`Codex (sign-in): ${message}`)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says in plain words when the test itself could not be run", async () => {
    await shown({}, {
      [`POST ${TEST}`]: () => {
        throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
      },
    });
    click(screen.getByRole("button", { name: "Test this AI" }));
    expect(await screen.findByText(/QuantOS is not responding/)).toBeInTheDocument();
    expect(screen.queryByText(/engine/i)).toBeNull();
  });

  it("waits with a spinner and says an app can be slow to start", async () => {
    const answer = deferred<unknown>();
    await shown({}, { [`POST ${TEST}`]: () => answer.promise });
    click(screen.getByRole("button", { name: "Test this AI" }));
    expect(await screen.findByText("This can take up to a minute while the AI app starts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test this AI" })).toBeDisabled();
    await act(async () => answer.resolve({ ok: true, who: "OpenAI", message: OPENAI_OK }));
    expect(await screen.findByText(OPENAI_OK)).toBeInTheDocument();
    expect(screen.queryByText("This can take up to a minute while the AI app starts.")).toBeNull();
  });

  it("looks at what is ready again afterwards, so a chip can change", async () => {
    const { state } = await shown();
    const before = sent("GET", STATUS).length;
    state.apps = state.apps.map((a) => (a.id === "codex" ? app("codex", "Codex", "CONNECTED") : a));
    click(screen.getByRole("button", { name: "Test this AI" }));
    await waitFor(() => expect(rowOf(/^Codex/).getByText("Ready")).toBeInTheDocument());
    expect(sent("GET", STATUS).length).toBeGreaterThan(before);
  });

  it("forgets an old answer when the choice changes", async () => {
    await shown();
    click(screen.getByRole("button", { name: "Test this AI" }));
    await screen.findByText(/answered, so it is ready/);
    click(radio(/^Codex/));
    await waitFor(() => expect(screen.queryByText(/answered, so it is ready/)).toBeNull());
  });
});

describe("keeping up with the apps", () => {
  it("asks once when the screen opens, not again because the app cards loaded", async () => {
    await shown();
    await waitFor(() => expect(sent("GET", "/api/v2/cli/status")).toHaveLength(1));
    expect(sent("GET", STATUS)).toHaveLength(1);
  });

  it("looks again at once when an install or sign-in card sees an app change", async () => {
    engine({}, { "GET /api/v2/cli/status": [{ id: "codex", state: "NEEDS_SIGN_IN" }] });
    const { client } = renderApp(<AiSource />);
    await screen.findByRole("button", { name: "Test this AI" });
    await waitFor(() => expect(client.getQueryData(["agent-clis"])).toBeDefined());
    const before = sent("GET", STATUS).length;
    act(() => client.setQueryData(["agent-clis"], [{ id: "codex", state: "CONNECTED" }]));
    await waitFor(() => expect(sent("GET", STATUS).length).toBeGreaterThan(before));
  });

  it("says plainly when it cannot check, and tries again on request", async () => {
    const answers = [
      () => {
        throw new ApiError("ENGINE_OFFLINE", "offline", 0);
      },
      () => BASE,
    ];
    engine({}, { [`GET ${STATUS}`]: () => (answers.shift() ?? (() => BASE))() });
    renderApp(<AiSource />);
    expect(await screen.findByText("QuantOS could not check which AI is ready.")).toBeInTheDocument();
    click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "Test this AI" })).toBeInTheDocument();
  });
});

describe("the words on the card", () => {
  it("uses no developer word", async () => {
    await shown();
    expect(document.body.textContent).not.toMatch(/\b(API|token|terminal|command|install script|CLI)\b/i);
  });
});
