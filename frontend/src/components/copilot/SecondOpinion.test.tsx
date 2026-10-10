import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../lib/api";
import { openSecondOpinion, OFFLINE_MESSAGE, SOMETHING_WRONG } from "../../lib/copilot";
import { sampleResult } from "./fixtures";
import { SecondOpinionHost } from "./SecondOpinionHost";
import { SecondOpinionReady } from "./SecondOpinionReady";
import { callsTo, renderApp, routeApi } from "./testHarness";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return { ...original, api: vi.fn() };
});

const READY = [
  { id: "openai", label: "OpenAI", ready: true },
  { id: "anthropic", label: "Anthropic", ready: true },
  { id: "gemini", label: "Gemini", ready: true },
  { id: "mistral", label: "Mistral", ready: true },
  { id: "groq", label: "Groq", ready: false },
];
const POLL = "/api/v2/copilot/verify/job1";

const running = (done: number, total: number) => ({
  status: "running",
  progress: { done, total },
  result: null,
  error: null,
});

function fakeEngine(models = READY, polls: unknown[] = [], cancel: () => unknown = () => ({ cancelled: true })) {
  const queue = [...polls];
  const nextPoll = () => queue.shift() ?? running(1, 8);
  routeApi({
    "GET /api/v2/copilot/models": () => ({ models }),
    "POST /api/v2/copilot/verify": () => ({ job_id: "job1" }),
    [`GET ${POLL}`]: nextPoll,
    [`DELETE ${POLL}`]: cancel,
  });
}

const finished = { status: "done", progress: { done: 8, total: 8 }, result: sampleResult(), error: null };

const sectionOf = (heading: string) => screen.getByRole("heading", { name: heading }).closest("section") as HTMLElement;

const MIXED = "2 of 3 models that answered read the evidence as mixed.";

async function openDialog(symbol = "TCS", pickNote?: string) {
  renderApp(
    <>
      <SecondOpinionHost />
      <SecondOpinionReady />
    </>,
  );
  act(() => openSecondOpinion(symbol, pickNote));
  await screen.findByRole("dialog");
}

describe("the Second opinion window", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  it("always says, at the top, what the opinions are and are not", async () => {
    fakeEngine();
    await openDialog();
    expect(screen.getByRole("heading", { name: "Second opinion on TCS" })).toBeInTheDocument();
    const intro =
      "Several AI models each read the same facts on their own and never see each other's answers. " +
      "Their opinions are not evidence that a stock will do well.";
    expect(screen.getByText(intro)).toBeInTheDocument();
  });

  it("offers no way to start, and a way to choose an AI, when no model is ready", async () => {
    fakeEngine([{ id: "openai", label: "OpenAI", ready: false }]);
    await openDialog();
    expect(await screen.findByText("Set up an AI first: choose Settings, then AI assistants.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask the models" })).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Choose an AI" }));
    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/ai"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("ticks up to three ready models, cannot tick one without a key, and gives the cross-check advice", async () => {
    fakeEngine();
    await openDialog();
    const boxes = await screen.findAllByRole("checkbox");
    expect(boxes.map((b) => (b as HTMLInputElement).checked)).toEqual([true, true, true, false, false]);
    expect(boxes[4]).toBeDisabled();
    const advice = "Models from different companies give a better cross-check than several from one company.";
    expect(screen.getByText(advice)).toBeInTheDocument();
    expect(screen.queryByText(/Also test whether the platform's own pick sways the models/)).toBeNull();
  });

  it("cannot start with nothing ticked", async () => {
    fakeEngine();
    await openDialog();
    const boxes = (await screen.findAllByRole("checkbox")) as HTMLInputElement[];
    for (const box of boxes.filter((b) => b.checked)) fireEvent.click(box);
    expect(screen.getByRole("button", { name: "Ask the models" })).toBeDisabled();
  });

  it("offers the pick test only when the opener passed a pick note, and sends it only when ticked", async () => {
    fakeEngine();
    await openDialog("TCS", "Ranked 3rd of 40 by the model.");
    const pick = await screen.findByLabelText(/Also test whether the platform's own pick sways the models/);
    expect(pick).not.toBeChecked();
    fireEvent.click(pick);
    fireEvent.click(screen.getByRole("button", { name: "Ask the models" }));
    await waitFor(() => expect(callsTo("POST", "/api/v2/copilot/verify")).toHaveLength(1));
    expect(callsTo("POST", "/api/v2/copilot/verify")[0]?.[2]).toEqual({
      symbol: "TCS",
      providers: ["openai", "anthropic", "gemini"],
      recheck: true,
      pick_note: "Ranked 3rd of 40 by the model.",
    });
  });
});

describe("a run in the Second opinion window", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  async function start() {
    await openDialog();
    fireEvent.click(await screen.findByRole("button", { name: "Ask the models" }));
  }

  it("shows how many answers are in, then the whole result", async () => {
    fakeEngine(READY, [running(3, 8), finished]);
    await start();
    expect(await screen.findByText("3 of 8 answers in")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText(MIXED)).toBeInTheDocument();
    expect(callsTo("GET", POLL)).toHaveLength(2);
  });

  it("shows the result in full: models, dissent, notes, disclosure, the screener and the facts", async () => {
    fakeEngine(READY, [finished]);
    await start();
    await screen.findByText(MIXED);

    expect(screen.getByText("Most of the models agree")).toBeInTheDocument();
    expect(screen.getByText("3 of 4 models answered.")).toBeInTheDocument();

    const models = within(sectionOf("Each model's own reading"));
    expect(models.getAllByRole("listitem").length).toBeGreaterThanOrEqual(4);
    expect(models.getByText("Mistral")).toBeInTheDocument();
    expect(models.getByText("Could not answer")).toBeInTheDocument();
    expect(models.getByText(/The key was not accepted/)).toBeInTheDocument();
    expect(models.getAllByText("Steady earnings history").length).toBeGreaterThan(0);
    expect(models.getAllByText("Slowing demand abroad").length).toBeGreaterThan(0);
    expect(models.getAllByText("No recent filing in the facts").length).toBeGreaterThan(0);
    expect(models.getByText(/Changed its mind when the same facts were shown/)).toBeInTheDocument();
    expect(models.getByText(/more favourably after being told the platform's own pick/)).toBeInTheDocument();

    const dissent = within(sectionOf("Models that read it differently, and why"));
    expect(dissent.getAllByText("Strong order book").length).toBeGreaterThan(0);

    for (const note of sampleResult().notes) expect(screen.getByText(note)).toBeInTheDocument();

    const disclosure = screen.getByText("These are opinions from AI models. They are not independent evidence.");
    expect(disclosure).toBeVisible();
    expect(disclosure.closest("details")).toBeNull();

    const halalHeading = "Halal screening (from the platform's screener, not from the AI models)";
    expect(screen.getByRole("heading", { name: halalHeading })).toBeInTheDocument();
    expect(screen.getByText("Unverified sample data")).toBeInTheDocument();
    expect(screen.getByText("12.35%, limit 30%")).toBeInTheDocument();

    const shown = screen.getByText("What the models were shown").closest("details") as HTMLDetailsElement;
    expect(shown.open).toBe(false);
    expect(within(shown).getByText("Price history facts")).toBeInTheDocument();
  });

  it("never offers anything to buy or sell, and never scores a reading", async () => {
    fakeEngine(READY, [finished]);
    await start();
    await screen.findByText(MIXED);
    const dialog = screen.getByRole("dialog");
    const buttons = within(dialog).getAllByRole("button").map((b) => b.textContent ?? "");
    expect(buttons.join("|")).not.toMatch(/\b(buy|sell|add to cart|invest|trade now)\b/i);
    expect(dialog.textContent).not.toMatch(/\b\d+(\.\d+)?\s?(\/\s?10|stars?|%\s+confidence)\b/i);
    expect(within(dialog).queryAllByRole("img", { name: /star/i })).toEqual([]);
  });

  it("does not colour a reading as go or stop", async () => {
    fakeEngine(READY, [finished]);
    await start();
    await screen.findByText(MIXED);
    const dialog = screen.getByRole("dialog");
    const readings = within(dialog).getAllByText(/^(Looks positive|Mixed|Looks negative|Not clear)$/);
    expect(readings.length).toBeGreaterThan(0);
    for (const word of readings) expect(word.className).not.toMatch(/text-(up|down)|bg-(up|down)|green|red/);
  });

  it("stops asking for answers when the person cancels, and offers to start again", async () => {
    fakeEngine(READY, [running(1, 8)]);
    await start();
    await screen.findByText("1 of 8 answers in");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    const asked = callsTo("GET", POLL).length;
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(callsTo("GET", POLL)).toHaveLength(asked);
    expect(await screen.findByText(/You stopped the last check/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask the models" })).toBeInTheDocument();
  });

  it("tells the engine to stop the run when the person cancels", async () => {
    fakeEngine(READY, [running(1, 8)]);
    await start();
    await screen.findByText("1 of 8 answers in");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(callsTo("DELETE", POLL)).toHaveLength(1));
    expect(callsTo("DELETE", POLL)).toHaveLength(1);
  });

  it("goes back to set-up even when the engine could not be told to stop", async () => {
    fakeEngine(READY, [running(1, 8)], () => {
      throw new ApiError("INTERNAL_ERROR", "Traceback", 500);
    });
    await start();
    await screen.findByText("1 of 8 answers in");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText(/You stopped the last check/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask the models" })).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).toBeNull();
  });

  it("treats a run the engine reports as stopped like a Cancel", async () => {
    const stopped = { status: "cancelled", progress: null, result: null, error: "You stopped this check." };
    fakeEngine(READY, [running(1, 8), stopped]);
    await start();
    await screen.findByText("1 of 8 answers in");
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText(/You stopped the last check/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask the models" })).toBeInTheDocument();
    expect(callsTo("DELETE", POLL)).toHaveLength(0);
  });

  it("keeps asking after the window is closed, and offers to reopen it when the result is ready", async () => {
    fakeEngine(READY, [running(1, 8), finished]);
    await start();
    await screen.findByText("1 of 8 answers in");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByRole("button", { name: /Second opinion on TCS is ready/ })).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(2000));
    const ready = await screen.findByRole("button", { name: "Second opinion on TCS is ready. Open it." });
    expect(ready).toHaveAttribute("title", "Second opinion on TCS is ready. Open it.");
    const announced = screen.getAllByRole("status").map((node) => node.textContent);
    expect(announced).toContain("Second opinion on TCS is ready. Open it.");
    expect(callsTo("DELETE", POLL)).toHaveLength(0);
    fireEvent.click(ready);
    expect(await screen.findByText(MIXED)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Second opinion on TCS is ready/ })).toBeNull();
    expect(callsTo("POST", "/api/v2/copilot/verify")).toHaveLength(1);
  });

  it("says nothing about a run that finished while its window was open", async () => {
    fakeEngine(READY, [finished]);
    await start();
    await screen.findByText(MIXED);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByRole("button", { name: /Second opinion on TCS/ })).toBeNull();
  });

  it("says when a run did not finish while the window was closed", async () => {
    const failed = { status: "failed", progress: null, result: null, error: "No AI model could be reached." };
    fakeEngine(READY, [running(1, 8), failed]);
    await start();
    await screen.findByText("1 of 8 answers in");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await act(() => vi.advanceTimersByTimeAsync(2000));
    const unfinished = "Second opinion on TCS did not finish. Open it to see why.";
    const chip = await screen.findByRole("button", { name: unfinished });
    fireEvent.click(chip);
    expect(await screen.findByText("No AI model could be reached.")).toBeInTheDocument();
  });

  it("stops asking, and tells the engine to stop, when a run is cancelled while the window is closed", async () => {
    fakeEngine(READY, [running(1, 8)]);
    await start();
    await screen.findByText("1 of 8 answers in");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    const asked = callsTo("GET", POLL).length;
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(callsTo("GET", POLL)).toHaveLength(asked);
  });

  it("shows the same finished result again when the window is reopened for the same stock", async () => {
    fakeEngine(READY, [finished]);
    await start();
    await screen.findByText(MIXED);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    act(() => openSecondOpinion("TCS"));
    expect(await screen.findByText(MIXED)).toBeInTheDocument();
    expect(callsTo("POST", "/api/v2/copilot/verify")).toHaveLength(1);
  });

  it("starts fresh on Run again", async () => {
    fakeEngine(READY, [finished]);
    await start();
    await screen.findByText(MIXED);
    fireEvent.click(screen.getByRole("button", { name: "Run again" }));
    expect(await screen.findByRole("button", { name: "Ask the models" })).toBeInTheDocument();
    expect(screen.queryByText(MIXED)).toBeNull();
  });

  it("says in plain words when the run fails, with a way to try again", async () => {
    fakeEngine(READY, [{ status: "failed", progress: null, result: null, error: "No AI model could be reached." }]);
    await start();
    expect(await screen.findByText("No AI model could be reached.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("never shows a server error's own words when the run cannot start", async () => {
    routeApi({
      "GET /api/v2/copilot/models": () => ({ models: READY }),
      "POST /api/v2/copilot/verify": () => {
        throw new ApiError("INTERNAL_ERROR", "Internal Server Error: KeyError 'x'", 500);
      },
    });
    await start();
    expect(await screen.findByText(SOMETHING_WRONG)).toBeInTheDocument();
    expect(screen.queryByText(/Internal Server Error|KeyError/)).toBeNull();
    expect(screen.getByRole("button", { name: "Ask the models" })).toBeInTheDocument();
  });

  it("says in plain words when QuantOS is not answering at all", async () => {
    routeApi({
      "GET /api/v2/copilot/models": () => ({ models: READY }),
      "POST /api/v2/copilot/verify": () => {
        throw new ApiError("ENGINE_OFFLINE", "The QuantOS engine is not responding.", 0);
      },
    });
    await start();
    expect(await screen.findByText(OFFLINE_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByText(/engine/i)).toBeNull();
  });

  it("returns to the set-up with the reason when the run cannot start", async () => {
    fakeEngine();
    routeApi({
      "GET /api/v2/copilot/models": () => ({ models: READY }),
      "POST /api/v2/copilot/verify": () => {
        throw new ApiError("VALIDATION", "Pick at least one AI model.", 422);
      },
    });
    await start();
    expect(await screen.findByText("Pick at least one AI model.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask the models" })).toBeInTheDocument();
  });
});

describe("the result of a second opinion", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  async function resultFor(result: ReturnType<typeof sampleResult>, symbol = "TCS") {
    fakeEngine(READY, [{ status: "done", progress: { done: 1, total: 1 }, result, error: null }]);
    await openDialog(symbol);
    fireEvent.click(await screen.findByRole("button", { name: "Ask the models" }));
  }

  it("says the reading in the headline the way the badges say it", async () => {
    await resultFor(sampleResult({ headline: "2 of 3 models read the facts as MIXED." }));
    expect(await screen.findByText("2 of 3 models read the facts as mixed.")).toBeInTheDocument();
    expect(screen.queryByText(/read the facts as MIXED/)).toBeNull();
  });

  it("calls the reading its own, not shared, when only one model answered", async () => {
    await resultFor(sampleResult({ consensus: "SINGLE", answered: 1, asked: 1, counts: { MIXED: 1 } }));
    expect(await screen.findByText("Its reading: Mixed")).toBeInTheDocument();
    expect(screen.queryByText(/Shared reading/)).toBeNull();
  });

  it("calls it the shared reading when several answered", async () => {
    await resultFor(sampleResult());
    expect(await screen.findByText("Shared reading: Mixed")).toBeInTheDocument();
  });

  describe("for a stock QuantOS has no data for", () => {
    const none = () =>
      sampleResult({
        symbol: "ZZZ",
        headline: "QuantOS has no market data for ZZZ yet, so no AI model was asked.",
        consensus: "NONE",
        reading: null,
        asked: 0,
        answered: 0,
        counts: {},
        news_tones: {},
        verdicts: [],
        dissent: [],
        notes: [],
        halal: null,
        facts: null,
      });

    it("shows only the headline and the disclosure, with no empty counts or headings", async () => {
      await resultFor(none(), "ZZZ");
      expect(await screen.findByText(/no market data for ZZZ yet/)).toBeInTheDocument();
      expect(screen.getByText("These are opinions from AI models. They are not independent evidence.")).toBeVisible();
      expect(screen.queryByText(/0 of 0/)).toBeNull();
      expect(screen.queryByText(/answered\./)).toBeNull();
      expect(screen.queryByRole("heading", { name: "Each model's own reading" })).toBeNull();
      expect(screen.queryByText("No model could answer")).toBeNull();
      expect(screen.queryByText("What the models were shown")).toBeNull();
    });

    it("leaves out the screener's 'cannot screen it' line but keeps a real screener result", async () => {
      const uncovered = { covered: false, message: "QuantOS cannot screen ZZZ.", data_status: "UNVERIFIED_SAMPLE" };
      await resultFor(sampleResult({ ...none(), halal: uncovered }), "ZZZ");
      await screen.findByText(/no market data for ZZZ yet/);
      expect(screen.queryByText(/cannot screen ZZZ/)).toBeNull();
      cleanup();
      vi.mocked(api).mockReset();
      await resultFor(sampleResult({ ...none(), halal: sampleResult().halal }), "ZZZ");
      const heading = "Halal screening (from the platform's screener, not from the AI models)";
      expect(await screen.findByText(heading)).toBeInTheDocument();
    });

    it("offers one button that opens Settings at Market data", async () => {
      await resultFor(none(), "ZZZ");
      fireEvent.click(await screen.findByRole("button", { name: "Open Settings, then Market data" }));
      await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/settings/data"));
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    });

    it("does not offer that button for an ordinary result", async () => {
      await resultFor(sampleResult());
      await screen.findByText("Shared reading: Mixed");
      expect(screen.queryByRole("button", { name: /Market data/ })).toBeNull();
    });
  });
});
