import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type AiApp,
  type AiChoice,
  type AiSettings,
  type AiStatus,
  APPS_ANCHOR,
  applyPatch,
  type OrderEntry,
} from "../../lib/aiSource";
import { ApiError, api } from "../../lib/api";
import type { CliCapabilities } from "../../lib/types";
import { callsTo, deferred, renderApp, routeApi } from "../agents/testHarness";
import { AiSource } from "./AiSource";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const CLAUDE_OK = "Claude Code (sign-in) answered, so it is ready to use.";
const GOES_TO_CLAUDE = "Right now your questions go to Claude Code, with your saved OpenAI key as a backup.";
const FALLBACK_LINE =
  "Your question is only ever sent to an AI you have set up. Turn this off to ask only the first one on your list.";
const FALLBACK_SWITCH = "If an AI can't answer, try the next one on my list";
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
  defaults: { speed: "balanced", helpers: 1 },
};

const entry = (id: string, model: string | null = null, thinking: string | null = null): OrderEntry => ({
  id,
  model,
  thinking,
});

function settingsOf(ai: AiChoice, defaults?: AiStatus["defaults"]): AiSettings {
  return {
    ai_source: ai.source,
    ai_cli: ai.cli,
    ai_api: ai.api,
    ai_fallback: ai.fallback,
    ai_order: ai.order ?? [],
    ai_defaults: defaults,
  };
}

/** A fake engine that keeps what a save sends, so the screen shows it back as the real one does. */
function engine(over: Partial<AiStatus> = {}, extra: Record<string, unknown> = {}) {
  const state: AiStatus = { ...BASE, ...over };
  routeApi({
    [`GET ${STATUS}`]: () => structuredClone(state),
    "GET /api/v2/cli/status": [],
    [`PUT ${SETTINGS}`]: (body: unknown) => {
      const patch = body as Partial<AiSettings>;
      state.ai = applyPatch(state.ai, patch);
      if (patch.ai_defaults) state.defaults = { ...state.defaults!, ...patch.ai_defaults };
      return settingsOf(state.ai, state.defaults);
    },
    [`POST ${TEST}`]: { ok: true, who: "Claude Code (sign-in)", message: CLAUDE_OK },
    ...extra,
  });
  return state;
}

const OPENAI_OK = "OpenAI answered, so it is ready to use.";
const click = (element: HTMLElement) => fireEvent.click(element);
const sent = (method: string, path: string) => callsTo(method, path);
const rowFor = (id: string) => within(document.querySelector(`[data-ai="${id}"]`) as HTMLElement);
const names = () => Array.from(document.querySelectorAll("[data-ai]")).map((li) => li.getAttribute("data-ai"));
const order = (...entries: OrderEntry[]) => ({ ai_order: entries });

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
    const removed = (a: AiApp): AiApp => ({ ...a, state: "NOT_INSTALLED", installed: false, ready: false });
    await shown({ apps: BASE.apps.map(removed), providers: keys() });
    expect(screen.getByText("No AI is set up yet.")).toBeInTheDocument();
    expect(screen.getByText("No AI is on your list yet.")).toBeInTheDocument();
  });

  it("follows a change of the order", async () => {
    await shown();
    click(screen.getByRole("button", { name: "Move Claude Code down" })); // Codex, which is signed out, is now first
    expect(
      await screen.findByText(
        "Codex is not signed in, so right now your questions go to Claude Code, with your saved OpenAI key as a backup.",
      ),
    ).toBeInTheDocument();
  });

  it("follows the backup being turned off", async () => {
    await shown();
    click(screen.getByRole("switch", { name: FALLBACK_SWITCH }));
    expect(await screen.findByText("Right now your questions go to Claude Code and nowhere else.")).toBeInTheDocument();
  });
});

describe("your AIs, in the order they are asked", () => {
  it("lists the apps and the saved keys together, in the order the Copilot asks them, each with a chip", async () => {
    await shown();
    expect(names()).toEqual(["cli:claude", "cli:codex", "openai"]);
    expect(rowFor("cli:claude").getByText("Ready")).toBeInTheDocument();
    expect(rowFor("cli:codex").getByText("Not signed in")).toBeInTheDocument();
    expect(rowFor("openai").getByText("Key saved")).toBeInTheDocument();
  });

  it("shows what is not set up with a way to fix it, and nothing else is offered a Set up button", async () => {
    await shown();
    expect(screen.getByText("Not set up yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set up Antigravity" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set up Codex" })).toBeInTheDocument(); // signed out: its card signs in
    expect(rowFor("cli:claude").queryByRole("button", { name: /^Set up/ })).toBeNull();
    const add = screen.getByRole("link", { name: "Add a key for Groq" });
    expect(add).toHaveAttribute("href", "/settings/accounts");
  });

  it("says an app that cannot report its sign-in has not been checked yet", async () => {
    await shown({ apps: [app("antigravity", "Antigravity", "UNKNOWN")] });
    expect(screen.getByText("Not checked yet. Press Test this AI.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Set up/ })).toBeNull();
  });

  it("saves the whole order at once when one is moved down, and the first cannot go up", async () => {
    await shown();
    expect(screen.getByRole("button", { name: "Move Claude Code up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move OpenAI down" })).toBeDisabled();
    click(screen.getByRole("button", { name: "Move Claude Code down" }));
    await waitFor(() =>
      expect(sent("PUT", SETTINGS)).toEqual([order(entry("cli:codex"), entry("cli:claude"), entry("openai"))]),
    );
    await waitFor(() => expect(names()).toEqual(["cli:codex", "cli:claude", "openai"]));
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("puts a saved key ahead of an app when asked to", async () => {
    await shown();
    click(screen.getByRole("button", { name: "Move OpenAI up" }));
    click(await screen.findByRole("button", { name: "Move OpenAI up" }));
    await waitFor(() => expect(names()).toEqual(["openai", "cli:claude", "cli:codex"]));
    expect(sent("PUT", SETTINGS).at(-1)).toEqual(order(entry("openai"), entry("cli:claude"), entry("cli:codex")));
  });

  it("takes an AI off the list, saves that, and offers it back", async () => {
    await shown();
    click(screen.getByRole("button", { name: "Take Codex off the list" }));
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([order(entry("cli:claude"), entry("openai"))]));
    expect(await screen.findByText("Ready, but not on your list")).toBeInTheDocument();
    click(screen.getByRole("button", { name: "Add Codex to the list" }));
    await waitFor(() =>
      expect(sent("PUT", SETTINGS).at(-1)).toEqual(order(entry("cli:claude"), entry("openai"), entry("cli:codex"))),
    );
  });

  it("keeps the choice saved for an AI that is not set up right now", async () => {
    await shown({ ai: { ...AUTO, order: [entry("cli:claude"), entry("anthropic", "claude-x", "high")] } });
    expect(names()).toEqual(["cli:claude"]); // no Anthropic key: it is not offered as an AI to ask
    click(screen.getByRole("button", { name: "Add OpenAI to the list" }));
    await waitFor(() =>
      expect(sent("PUT", SETTINGS)).toEqual([
        order(entry("cli:claude"), entry("openai"), entry("anthropic", "claude-x", "high")),
      ]),
    );
  });

  it("keeps the person's click if the save fails, says so plainly, and puts the order back", async () => {
    await shown(
      {},
      {
        [`PUT ${SETTINGS}`]: () => {
          throw new ApiError("INVALID_SETTINGS", "ai_order: Input should be a valid list", 422);
        },
      },
    );
    click(screen.getByRole("button", { name: "Move Claude Code down" }));
    const note = await screen.findByRole("alert");
    expect(note).toHaveTextContent("That choice could not be saved, so nothing was changed. Please try again.");
    expect(document.body.textContent).not.toMatch(/INVALID_SETTINGS|Input should be/);
    await waitFor(() => expect(names()).toEqual(["cli:claude", "cli:codex", "openai"]));
  });

  it("follows the person's own saved order, not the built-in one", async () => {
    await shown({ ai: { ...AUTO, order: [entry("openai"), entry("cli:claude")] } });
    expect(names()).toEqual(["openai", "cli:claude"]);
    expect(screen.getByText("Right now your questions go to your saved OpenAI key, with Claude Code as a backup.")).toBeInTheDocument();
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

  it("lands on Antigravity's card too", async () => {
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

describe("the model and the thinking level of each AI", () => {
  const CODEX_PATH = "/api/v2/cli/codex/capabilities";
  const AGY_PATH = "/api/v2/cli/antigravity/capabilities";
  const OPENAI_PATH = "/api/v2/ai/models/openai";
  const model = (id: string, name: string, over: Partial<CliCapabilities["models"][number]> = {}) => ({
    id,
    name,
    description: "",
    context_window: null,
    released: null,
    newest: false,
    recommended: false,
    thinking: null,
    variants: null,
    ...over,
  });
  const caps = (models: CliCapabilities["models"], levels: string[] = []): Partial<CliCapabilities> => ({
    models,
    thinking_levels: levels,
    features: [],
    note: null,
  });
  const CODEX = caps(
    [
      model("gpt-6-luna", "GPT-6-Luna", { newest: true, thinking: { levels: ["low", "high", "max"], default: "medium" } }),
      model("gpt-5.6-luna", "GPT-5.6-Luna", { thinking: { levels: ["low", "high"], default: "medium" } }),
    ],
    ["low", "high", "max"],
  );
  const openRow = (name: string) => click(screen.getByRole("button", { name: `Model and thinking for ${name}` }));
  const select = (label: RegExp | string) => screen.getByRole("combobox", { name: label });

  const codexListed = (): Partial<AiStatus> => ({
    apps: [app("codex", "Codex", "CONNECTED")],
    providers: keys("openai"),
    ai: { ...AUTO, order: [entry("cli:codex"), entry("openai")] },
  });

  it("starts on the AI's own choices and reads the live models only when a row is opened", async () => {
    await shown(codexListed(), { [`GET ${CODEX_PATH}`]: CODEX });
    expect(sent("GET", CODEX_PATH)).toHaveLength(0);
    expect(screen.getAllByText("Model and thinking: Automatic")).toHaveLength(2); // Codex and OpenAI
    openRow("Codex");
    expect(await screen.findByRole("option", { name: /GPT-6-Luna · newest/ })).toBeInTheDocument();
    expect(select(/^Model/)).toHaveValue("");
    expect(sent("GET", CODEX_PATH)).toHaveLength(1);
  });

  it("saves the model that is picked, with nothing about thinking until it is chosen", async () => {
    await shown(codexListed(), { [`GET ${CODEX_PATH}`]: CODEX });
    openRow("Codex");
    await screen.findByRole("option", { name: /GPT-6-Luna/ }); // the live list has arrived
    fireEvent.change(select(/^Model/), { target: { value: "gpt-6-luna" } });
    await waitFor(() =>
      expect(sent("PUT", SETTINGS)).toEqual([order(entry("cli:codex", "gpt-6-luna"), entry("openai"))]),
    );
  });

  it("offers only the thinking levels that model takes, in plain words, and saves the choice", async () => {
    await shown(codexListed(), { [`GET ${CODEX_PATH}`]: CODEX });
    openRow("Codex");
    await screen.findByRole("option", { name: /GPT-5.6-Luna/ });
    fireEvent.change(select(/^Model/), { target: { value: "gpt-5.6-luna" } });
    const levels = select(/How hard it thinks/);
    await waitFor(() =>
      expect(within(levels).getAllByRole("option").map((o) => o.textContent)).toEqual(["Its usual", "Low", "High"]),
    );
    fireEvent.change(levels, { target: { value: "high" } });
    await waitFor(() =>
      expect(sent("PUT", SETTINGS).at(-1)).toEqual(order(entry("cli:codex", "gpt-5.6-luna", "high"), entry("openai"))),
    );
  });

  it("lets a level be chosen without picking a model", async () => {
    await shown(codexListed(), { [`GET ${CODEX_PATH}`]: CODEX });
    openRow("Codex");
    const levels = await screen.findByRole("combobox", { name: /How hard it thinks/ });
    expect(within(levels).getAllByRole("option").map((o) => o.textContent)).toEqual(["Its usual", "Low", "High", "Maximum"]);
    fireEvent.change(levels, { target: { value: "max" } });
    await waitFor(() =>
      expect(sent("PUT", SETTINGS)).toEqual([order(entry("cli:codex", null, "max"), entry("openai"))]),
    );
  });

  it("keeps a level when the new model takes it, and drops it when it does not", async () => {
    const start = { ...codexListed(), ai: { ...AUTO, order: [entry("cli:codex", "gpt-6-luna", "max"), entry("openai")] } };
    await shown(start, { [`GET ${CODEX_PATH}`]: CODEX });
    openRow("Codex");
    await screen.findByRole("option", { name: /GPT-5.6-Luna/ });
    fireEvent.change(select(/^Model/), { target: { value: "gpt-5.6-luna" } });
    await waitFor(() => expect(sent("PUT", SETTINGS).at(-1)).toEqual(order(entry("cli:codex", "gpt-5.6-luna"), entry("openai"))));
  });

  it("puts the level into the model's name where the app works that way", async () => {
    const agy = caps(
      [
        model("gemini-3.8-flash", "Gemini 3.8 Flash", {
          newest: true,
          thinking: { levels: ["low", "medium", "high"], default: null },
          variants: { low: "gemini-3.8-flash-low", medium: "gemini-3.8-flash-medium", high: "gemini-3.8-flash-high" },
        }),
      ],
      ["low", "medium", "high"],
    );
    await shown(
      { apps: [app("antigravity", "Antigravity", "CONNECTED")], providers: keys(), ai: { ...AUTO, order: [entry("cli:antigravity")] } },
      { [`GET ${AGY_PATH}`]: agy },
    );
    openRow("Antigravity");
    await screen.findByRole("option", { name: /Gemini 3.8 Flash/ });
    fireEvent.change(select(/^Model/), { target: { value: "gemini-3.8-flash" } });
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([order(entry("cli:antigravity", "gemini-3.8-flash-medium"))]));
    const levels = await screen.findByRole("combobox", { name: /How hard it thinks/ });
    expect(levels).toHaveValue("medium");
    expect(within(levels).queryByRole("option", { name: "Its usual" })).toBeNull();
    fireEvent.change(levels, { target: { value: "high" } });
    await waitFor(() => expect(sent("PUT", SETTINGS).at(-1)).toEqual(order(entry("cli:antigravity", "gemini-3.8-flash-high"))));
  });

  it("shows a saved model the live list no longer has, under the name it was saved with", async () => {
    const start = { ...codexListed(), ai: { ...AUTO, order: [entry("cli:codex", "gpt-old"), entry("openai")] } };
    await shown(start, { [`GET ${CODEX_PATH}`]: CODEX });
    openRow("Codex");
    expect(await screen.findByRole("option", { name: "gpt-old (chosen earlier)" })).toBeInTheDocument();
    expect(select(/^Model/)).toHaveValue("gpt-old");
  });

  it("works the same for a saved key, with the levels such a provider takes", async () => {
    const found = { provider: "openai", total: 2, newest: [{ id: "gpt-9", name: "gpt-9", created: 1 }] };
    await shown(codexListed(), { [`GET ${CODEX_PATH}`]: CODEX, [`GET ${OPENAI_PATH}`]: found });
    openRow("OpenAI");
    await screen.findByRole("option", { name: "gpt-9" });
    fireEvent.change(select(/^Model/), { target: { value: "gpt-9" } });
    const levels = select(/How hard it thinks/);
    await waitFor(() =>
      expect(within(levels).getAllByRole("option").map((o) => o.textContent)).toEqual(["Its usual", "Low", "Medium", "High", "Extra high"]),
    );
    fireEvent.change(levels, { target: { value: "xhigh" } });
    await waitFor(() =>
      expect(sent("PUT", SETTINGS).at(-1)).toEqual(order(entry("cli:codex"), entry("openai", "gpt-9", "xhigh"))),
    );
  });

  it("says why when an AI's models cannot be read, and still lets the level be chosen", async () => {
    const none = { ...caps([]), note: "The app did not list its models. Make sure you are signed in, then refresh." };
    await shown(codexListed(), { [`GET ${CODEX_PATH}`]: none });
    openRow("Codex");
    expect(await screen.findByText(/did not list its models/)).toBeInTheDocument();
    expect(select(/^Model/)).toHaveValue("");
  });

  it("tests an AI exactly as it is set up", async () => {
    const start = { ...codexListed(), ai: { ...AUTO, order: [entry("cli:codex", "gpt-6-luna", "high"), entry("openai")] } };
    await shown(start, { [`GET ${CODEX_PATH}`]: CODEX });
    openRow("Codex");
    const row = rowFor("cli:codex");
    click(await row.findByRole("button", { name: "Test this AI" }));
    await waitFor(() =>
      expect(sent("POST", TEST)).toEqual([{ model: "cli:codex", chosen_model: "gpt-6-luna", thinking: "high" }]),
    );
  });
});

describe("how answers are made", () => {
  it("starts on Balanced and says what each choice means in plain words", async () => {
    await shown();
    expect(screen.getByRole("radio", { name: /Balanced/ })).toBeChecked();
    expect(screen.getByText("Looks things up more and thinks harder. Takes longer.")).toBeInTheDocument();
  });

  it("saves the speed at once, without touching anything else", async () => {
    await shown();
    click(screen.getByRole("radio", { name: /Careful/ }));
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([{ ai_defaults: { speed: "careful" } }]));
    await waitFor(() => expect(screen.getByRole("radio", { name: /Careful/ })).toBeChecked());
  });
});

describe("who works on a task", () => {
  it("starts with just the Copilot and saves a larger team at once", async () => {
    await shown();
    const team = screen.getByRole("combobox", { name: "Who works on a task in agent mode" });
    expect(team).toHaveValue("1");
    expect(within(team).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Just the Copilot",
      "The Copilot and one helper",
      "The Copilot and two helpers",
    ]);
    fireEvent.change(team, { target: { value: "2" } });
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([{ ai_defaults: { helpers: 2 } }]));
    await waitFor(() => expect(team).toHaveValue("2"));
  });

  it("keeps a quick change of speed and then team size, both saved", async () => {
    await shown();
    click(screen.getByRole("radio", { name: /Careful/ }));
    fireEvent.change(screen.getByRole("combobox", { name: "Who works on a task in agent mode" }), { target: { value: "3" } });
    await waitFor(() => expect(sent("PUT", SETTINGS)).toHaveLength(2));
    await waitFor(() => expect(screen.getByRole("radio", { name: /Careful/ })).toBeChecked());
    expect(screen.getByRole("combobox", { name: "Who works on a task in agent mode" })).toHaveValue("3");
  });
});

describe("the backup", () => {
  it("is on by default and explains itself in one line", async () => {
    await shown();
    expect(screen.getByRole("switch", { name: FALLBACK_SWITCH })).toBeChecked();
    expect(screen.getByText(FALLBACK_LINE)).toBeInTheDocument();
  });

  it("is saved when turned off", async () => {
    await shown();
    click(screen.getByRole("switch", { name: FALLBACK_SWITCH }));
    await waitFor(() => expect(sent("PUT", SETTINGS)).toEqual([{ ai_fallback: false }]));
  });
});

describe("Test this AI", () => {
  it("asks whichever AI the Copilot would use when no order is saved, and shows the answer", async () => {
    await shown();
    expect(screen.getByText("Tests whichever AI your questions go to first.")).toBeInTheDocument();
    click(screen.getByRole("button", { name: "Test this AI" }));
    expect(await screen.findByText("Claude Code (sign-in) answered, so it is ready to use.")).toBeInTheDocument();
    expect(sent("POST", TEST)).toEqual([{}]);
  });

  const TEST_TARGET_CASES = [
    ["an app", { ...AUTO, order: [entry("cli:codex")] }, { model: "cli:codex" }],
    ["a key", { ...AUTO, order: [entry("openai", "gpt-9", "low")] }, { model: "openai", chosen_model: "gpt-9", thinking: "low" }],
  ] as const;

  it.each(TEST_TARGET_CASES)("asks the first %s on the list by name, as it is set up", async (_name, ai, body) => {
    await shown({ ai: { ...ai, order: [...ai.order] } });
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
    await shown(
      {},
      {
        [`POST ${TEST}`]: () => {
          throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
        },
      },
    );
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
    await waitFor(() => expect(rowFor("cli:codex").getByText("Ready")).toBeInTheDocument());
    expect(sent("GET", STATUS).length).toBeGreaterThan(before);
  });

  it("forgets an old answer when the order changes", async () => {
    await shown();
    click(screen.getByRole("button", { name: "Test this AI" }));
    await screen.findByText(/answered, so it is ready/);
    click(screen.getByRole("button", { name: "Move Claude Code down" }));
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
  it("uses no developer word, closed or with every row open", async () => {
    await shown({ ai: { ...AUTO, order: [entry("cli:claude"), entry("openai")] } }, { "GET /api/v2/cli/claude/capabilities": { models: [], thinking_levels: [], features: [], note: null } });
    expect(document.body.textContent).not.toMatch(/\b(API|token|terminal|command|install script|CLI)\b/i);
  });
});
