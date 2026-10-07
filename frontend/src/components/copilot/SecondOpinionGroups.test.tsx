import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { openSecondOpinion } from "../../lib/copilot";
import { SecondOpinionHost } from "./SecondOpinionHost";
import { SecondOpinionReady } from "./SecondOpinionReady";
import { callsTo, renderApp, routeApi } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

// The engine lists the AI apps on this computer first, then the saved keys.
const MODELS = [
  { id: "cli:claude", label: "Claude Code (your Claude sign-in)", ready: true },
  { id: "cli:codex", label: "Codex (your ChatGPT sign-in)", ready: false },
  { id: "cli:gemini", label: "Gemini CLI (your Google sign-in)", ready: true },
  { id: "anthropic", label: "Anthropic (Claude)", ready: false },
  { id: "openai", label: "OpenAI", ready: true },
  { id: "groq", label: "Groq", ready: true },
];

const RUNNING = { status: "running", progress: { done: 0, total: 8 }, result: null, error: null };

function fakeEngine(models = MODELS) {
  routeApi({
    "GET /api/v2/copilot/models": () => ({ models }),
    "POST /api/v2/copilot/verify": () => ({ job_id: "job1" }),
    "GET /api/v2/copilot/verify/job1": () => RUNNING,
    "DELETE /api/v2/copilot/verify/job1": () => ({ cancelled: true }),
  });
}

async function openDialog() {
  renderApp(
    <>
      <SecondOpinionHost />
      <SecondOpinionReady />
    </>,
  );
  act(() => openSecondOpinion("TCS"));
  await screen.findByRole("dialog");
}

const group = (name: string) => screen.getByRole("group", { name });
const boxOf = (name: RegExp) => screen.getByRole("checkbox", { name }) as HTMLInputElement;

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("choosing the AIs for a second opinion", () => {
  it("shows the apps on this computer first and the saved keys second, each under its own heading", async () => {
    fakeEngine();
    await openDialog();
    const apps = await screen.findByRole("group", { name: "AI apps on this computer" });
    const keys = group("AI keys you saved");
    expect(within(apps).getAllByRole("checkbox")).toHaveLength(3);
    expect(within(keys).getAllByRole("checkbox")).toHaveLength(3);
    expect(apps.compareDocumentPosition(keys) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("says which are ready, and what is missing for the rest, in words for each kind", async () => {
    fakeEngine();
    await openDialog();
    await screen.findByRole("group", { name: "AI apps on this computer" });
    expect(within(group("AI apps on this computer")).getAllByText("Ready")).toHaveLength(2);
    expect(within(group("AI apps on this computer")).getByText("Not set up yet")).toBeInTheDocument();
    expect(within(group("AI keys you saved")).getByText("No key added yet")).toBeInTheDocument();
    expect(boxOf(/^Codex/)).toBeDisabled();
    expect(boxOf(/^Anthropic/)).toBeDisabled();
  });

  it("ticks up to three ready AIs at first, apps ahead of keys, as before", async () => {
    fakeEngine();
    await openDialog();
    await screen.findAllByRole("checkbox");
    const ticked = screen.getAllByRole("checkbox").map((box) => (box as HTMLInputElement).checked);
    expect(ticked).toEqual([true, false, true, false, true, false]);
  });

  it("sends an app's own id, unchanged, with the keys that were ticked", async () => {
    fakeEngine();
    await openDialog();
    await screen.findAllByRole("checkbox");
    fireEvent.click(boxOf(/^Gemini CLI/));
    fireEvent.click(boxOf(/^Groq/));
    fireEvent.click(screen.getByRole("button", { name: "Ask the models" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/copilot/verify")).toHaveLength(1));
    expect(callsTo("POST", "/api/v2/copilot/verify")[0]?.[2]).toMatchObject({
      symbol: "TCS",
      providers: ["cli:claude", "openai", "groq"],
    });
  });

  it("shows only the keys group when the engine lists no apps", async () => {
    fakeEngine(MODELS.slice(3));
    await openDialog();
    await screen.findByRole("group", { name: "AI keys you saved" });
    expect(screen.queryByRole("group", { name: "AI apps on this computer" })).toBeNull();
  });

  it("sends a person with nothing ready to Settings, then AI assistants", async () => {
    fakeEngine(MODELS.map((m) => ({ ...m, ready: false })));
    await openDialog();
    expect(await screen.findByText("Set up an AI first: choose Settings, then AI assistants.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Choose an AI" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/ai"));
    expect(document.body.textContent).not.toMatch(/Add an AI key|Accounts and keys/);
  });
});
