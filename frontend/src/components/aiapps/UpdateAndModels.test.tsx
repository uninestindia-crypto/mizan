import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { CliCapabilities, CliModel } from "../../lib/types";
import { callsTo } from "../agents/testHarness";
import { app, cardOf, job, LAUNCH, shown, startsJob } from "./appFixtures";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const click = (element: HTMLElement) => fireEvent.click(element);
const CAPS_PATH = "/api/v2/cli/codex/capabilities";
const AUTO = "/api/v2/cli/auto-update";

function model(over: Partial<CliModel> = {}): CliModel {
  return {
    id: "gpt-6-luna",
    name: "GPT-6-Luna",
    description: "Fast and affordable.",
    context_window: 272000,
    released: null,
    newest: true,
    recommended: true,
    thinking: { levels: ["low", "xhigh", "max"], default: "medium" },
    variants: null,
    ...over,
  };
}

function caps(over: Partial<CliCapabilities> = {}): CliCapabilities {
  return {
    agent_id: "codex",
    name: "Codex",
    maker: "OpenAI",
    installed: true,
    authenticated: true,
    version: "codex-cli 0.162.1",
    is_custom: false,
    models: [model()],
    thinking_levels: ["low", "xhigh", "max"],
    features: [{ name: "Models", description: "1 found. The newest is GPT-6-Luna." }],
    source: "app",
    source_note: "Read from the app on this computer just now.",
    saved_list_checked: null,
    note: null,
    last_fetched: "2026-10-10T10:00:00Z",
    ...over,
  };
}

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("the version and the result of an update", () => {
  it("shows the version a person recognises beside who makes the app", async () => {
    await shown([app("codex", "CONNECTED", { version: "codex-cli 0.162.1" })]);
    expect(cardOf("Codex").getByText(/version 0\.162\.1/)).toBeInTheDocument();
    expect(cardOf("Codex").queryByText(/codex-cli/)).toBeNull();
  });

  it("asks for an update and shows what it is doing", async () => {
    await shown([app("codex")], startsJob("codex", job({ action: "update", message: "Checking for a newer Codex..." })));
    click(cardOf("Codex").getByRole("button", { name: "Update Codex" }));
    expect(await cardOf("Codex").findByText("Checking for a newer Codex...")).toBeInTheDocument();
    expect(callsTo("POST", LAUNCH)).toEqual([{ agent_id: "codex", action: "update" }]);
  });

  it("keeps the finished result on the card until it is dismissed", async () => {
    const done = job({
      action: "update",
      state: "DONE",
      message: "Codex was updated from version 0.162.1 to 0.170.0.",
      ended_seconds_ago: 4,
    });
    await shown([app("codex", "CONNECTED", { job: done })]);
    expect(await cardOf("Codex").findByText("Codex was updated from version 0.162.1 to 0.170.0.")).toBeInTheDocument();
    click(cardOf("Codex").getByRole("button", { name: "Dismiss" }));
    expect(cardOf("Codex").queryByText(/was updated from/)).toBeNull();
  });

  it("says plainly when nothing needed updating", async () => {
    const done = job({
      action: "update",
      state: "DONE",
      message: "Codex is already up to date (version 0.162.1).",
      ended_seconds_ago: 2,
    });
    await shown([app("codex", "CONNECTED", { job: done })]);
    expect(await cardOf("Codex").findByText(/already up to date/)).toBeInTheDocument();
  });

  it("lets an old result go", async () => {
    const old = job({ action: "update", state: "DONE", message: "Codex is up to date.", ended_seconds_ago: 5000 });
    await shown([app("codex", "CONNECTED", { job: old })]);
    expect(cardOf("Codex").queryByText("Codex is up to date.")).toBeNull();
  });

  it("tells the person when the click joined a different step that is still running", async () => {
    const busy = "Codex is busy signing in. Try again when it has finished.";
    await shown([app("codex")], () => ({
      [`POST ${LAUNCH}`]: { success: true, joined: true, message: busy, job: job({ action: "signin" }) },
    }));
    click(cardOf("Codex").getByRole("button", { name: "Update Codex" }));
    expect(await screen.findByText(busy)).toBeInTheDocument();
  });
});

describe("the automatic update box", () => {
  it("sends the choice as an object and shows a plain note when it is refused", async () => {
    await shown([app("codex")], () => ({
      [`GET ${AUTO}`]: { auto_update_cli: false },
      [`POST ${AUTO}`]: () => {
        throw new Error("Please try again.");
      },
    }));
    click(screen.getByLabelText("Update apps automatically"));
    expect(await screen.findByText(/Automatic updating could not be changed/)).toBeInTheDocument();
    expect(callsTo("POST", AUTO)).toEqual([{ enabled: true }]);
  });
});

describe("the models an app can use", () => {
  const open = async () =>
    click(await cardOf("Codex").findByRole("button", { name: "Models and thinking levels of Codex" }));

  it("lists the live models newest first with their thinking levels, in plain words", async () => {
    await shown([app("codex")], () => ({ [`GET ${CAPS_PATH}`]: caps() }));
    await open();
    expect(await screen.findByText("GPT-6-Luna")).toBeInTheDocument();
    expect(screen.getByText("Newest")).toBeInTheDocument();
    for (const level of ["Low", "Extra high", "Maximum"]) expect(screen.getByText(level)).toBeInTheDocument();
    expect(screen.getByText("Reads about 2,04,000 words at once")).toBeInTheDocument();
    expect(screen.getByText(/Read from the app on this computer just now/)).toBeInTheDocument();
  });

  it("marks the level a model usually runs at when it is one of the choices", async () => {
    const usual = model({ thinking: { levels: ["low", "medium"], default: "medium" } });
    await shown([app("codex")], () => ({ [`GET ${CAPS_PATH}`]: caps({ models: [usual] }) }));
    await open();
    expect(await screen.findByText("Medium (its usual)")).toBeInTheDocument();
  });

  it("asks again, past anything remembered, when Refresh models is pressed", async () => {
    const newer = caps({ models: [model({ id: "gpt-7", name: "GPT-7" })] });
    await shown([app("codex")], () => ({
      [`GET ${CAPS_PATH}`]: caps(),
      [`GET ${CAPS_PATH}?refresh=true`]: newer,
    }));
    await open();
    await screen.findByText("GPT-6-Luna");
    click(screen.getByRole("button", { name: /Refresh models/ }));
    expect(await screen.findByText("GPT-7")).toBeInTheDocument();
    expect(screen.queryByText("GPT-6-Luna")).toBeNull();
  });

  it("shows the reason instead of a made-up list when the app could not be asked", async () => {
    const empty = caps({
      models: [],
      thinking_levels: [],
      features: [],
      source: "none",
      source_note: "No models could be read.",
      note: "The app did not list its models. Make sure you are signed in, then refresh.",
    });
    await shown([app("codex")], () => ({ [`GET ${CAPS_PATH}`]: empty }));
    await open();
    expect(await screen.findByText(/did not list its models/)).toBeInTheDocument();
    expect(screen.queryByText("Newest")).toBeNull();
  });

  it("says plainly when the engine could not read the models", async () => {
    await shown([app("codex")], () => ({
      [`GET ${CAPS_PATH}`]: () => {
        throw new Error("Could not read the models just now.");
      },
    }));
    await open();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not read the models just now."));
  });
});
