import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../lib/api";
import type { ResearchAnswer, ResearchSetup, ResearchStatus } from "../../lib/research";
import { callsTo, renderApp, routeApi } from "../agents/testHarness";
import { ResearchScreen } from "./ResearchScreen";

vi.mock("../../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/api")>();
  return { ...real, api: vi.fn() };
});

const STATUS = "GET /api/v2/research/status";
const SEARCH = "POST /api/v2/research/search";
const SETUP = "POST /api/v2/research/setup";
const CANCEL = "POST /api/v2/research/setup/cancel";

const IDLE: ResearchSetup = { state: "IDLE", percent: 0, mb_done: 0, mb_total: 330.3, message: "", error: null };

function status(overrides: Partial<ResearchStatus["engine"]> = {}, setup: Partial<ResearchSetup> = {}): ResearchStatus {
  return {
    engine: {
      state: "NEEDS_DOWNLOAD",
      by_meaning: false,
      label: "Built-in keyword matching (EmbeddingGemma 2 has not been downloaded yet)",
      download_mb: 330,
      ...overrides,
    },
    library: { papers: 5 },
    setup: { ...IDLE, ...setup },
  };
}

const PAPER = {
  id: "1404.1448",
  title: "The Deflated Sharpe Ratio: Correcting for Selection Bias",
  authors: ["David H. Bailey", "Marcos Lopez de Prado"],
  more_authors: 0,
  year: 2014,
  field: "Statistical finance",
  summary: "We propose a deflated Sharpe ratio that corrects for selection bias, backtest overfitting and non-normal returns.",
  link: "https://arxiv.org/pdf/1404.1448.pdf",
  match_percent: 74,
};

function answer(overrides: Partial<ResearchAnswer> = {}): ResearchAnswer {
  return {
    question: "avoid overfitting",
    results: [PAPER],
    engine: { by_meaning: false, label: "Built-in keyword matching (EmbeddingGemma 2 has not been downloaded yet)" },
    library: { papers: 5 },
    notes: [],
    ...overrides,
  };
}

function ask(text: string) {
  fireEvent.change(screen.getByLabelText("Your question"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
}

describe("Research screen", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  it("explains plainly how matching works before the model is downloaded, and offers the one button", async () => {
    routeApi({ [STATUS]: status() });
    renderApp(<ResearchScreen />);
    expect(await screen.findByText("Matching by keywords")).toBeInTheDocument();
    expect(screen.getByText(/about 330 MB/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing you type is sent anywhere/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Turn on smarter search/ })).toBeInTheDocument();
    expect(screen.getByText(/Your library holds 5 papers on this computer/)).toBeInTheDocument();
  });

  it("cannot search with an empty question", async () => {
    routeApi({ [STATUS]: status() });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
  });

  it("searches, and shows each paper with its link, field, year and match", async () => {
    routeApi({ [STATUS]: status(), [SEARCH]: answer({ notes: ["Added 1 new paper from arXiv to your library."] }) });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    ask("  avoid overfitting  ");
    const link = await screen.findByRole("link", { name: /The Deflated Sharpe Ratio/ });
    expect(link).toHaveAttribute("href", "https://arxiv.org/pdf/1404.1448.pdf");
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.getByText("Match 74%")).toBeInTheDocument();
    expect(screen.getByText("Statistical finance")).toBeInTheDocument();
    expect(screen.getByText("2014")).toBeInTheDocument();
    expect(screen.getByText("David H. Bailey, Marcos Lopez de Prado")).toBeInTheDocument();
    expect(screen.getByText("Added 1 new paper from arXiv to your library.")).toBeInTheDocument();
    expect(screen.getByText(/1 paper for "avoid overfitting"/)).toBeInTheDocument();
    expect(screen.getByText(/shares none of your words scores near 0%/)).toBeInTheDocument();
    expect(callsTo("POST", "/api/v2/research/search")).toEqual([{ question: "avoid overfitting", top_k: 5, online: false }]);
  });

  it("warns that a by-meaning match number has a floor, so a low-looking fit is not mistaken for a good one", async () => {
    routeApi({
      [STATUS]: status({ state: "READY", by_meaning: true }),
      [SEARCH]: answer({ engine: { by_meaning: true, label: "EmbeddingGemma 2 (running on this computer)" } }),
    });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by meaning");
    ask("avoid overfitting");
    expect(await screen.findByText(/even an unrelated paper can score around 40%/)).toBeInTheDocument();
    expect(screen.queryByText(/near 0%/)).toBeNull();
  });

  it("runs an example question with one click", async () => {
    routeApi({ [STATUS]: status(), [SEARCH]: answer() });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    fireEvent.click(screen.getByRole("button", { name: "What is a deflated Sharpe ratio?" }));
    await screen.findByRole("link", { name: /The Deflated Sharpe Ratio/ });
    expect(callsTo("POST", "/api/v2/research/search")).toEqual([
      { question: "What is a deflated Sharpe ratio?", top_k: 5, online: false },
    ]);
  });

  it("looks on arXiv only when asked to", async () => {
    routeApi({ [STATUS]: status(), [SEARCH]: answer() });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    fireEvent.click(screen.getByRole("switch", { name: /Also look for new papers on arXiv/ }));
    ask("option hedging costs");
    await screen.findByRole("link", { name: /The Deflated Sharpe Ratio/ });
    expect(callsTo("POST", "/api/v2/research/search")).toEqual([{ question: "option hedging costs", top_k: 5, online: true }]);
  });

  it("says so when nothing matched", async () => {
    routeApi({ [STATUS]: status(), [SEARCH]: answer({ results: [] }) });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    ask("zzzz");
    expect(await screen.findByText("No papers matched")).toBeInTheDocument();
    expect(screen.getByText("Nothing close to that")).toBeInTheDocument();
  });

  it("shows a failed search in plain words", async () => {
    routeApi({
      [STATUS]: status(),
      [SEARCH]: () => {
        throw new ApiError("QUESTION_TOO_LONG", "Shorten the question to 500 letters or fewer.", 422);
      },
    });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    ask("long");
    expect(await screen.findByText("Shorten the question to 500 letters or fewer.")).toBeInTheDocument();
    expect(screen.getByText("The search did not work")).toBeInTheDocument();
  });

  it("shows more of a long summary on request", async () => {
    const long = { ...PAPER, summary: "Word ".repeat(120).trim() };
    routeApi({ [STATUS]: status(), [SEARCH]: answer({ results: [long] }) });
    renderApp(<ResearchScreen />);
    await screen.findByText("Matching by keywords");
    ask("words");
    const more = await screen.findByRole("button", { name: "Show more" });
    fireEvent.click(more);
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });

  describe("turning on smarter search", () => {
    it("starts the download with one click", async () => {
      routeApi({ [STATUS]: status(), [SETUP]: { ...IDLE, state: "DOWNLOADING", message: "Starting the download..." } });
      renderApp(<ResearchScreen />);
      fireEvent.click(await screen.findByRole("button", { name: /Turn on smarter search/ }));
      await waitFor(() => expect(callsTo("POST", "/api/v2/research/setup")).toHaveLength(1));
    });

    it("shows the progress and lets the person cancel", async () => {
      routeApi({
        [STATUS]: status({}, { state: "DOWNLOADING", percent: 30, mb_done: 100, message: "Downloading EmbeddingGemma 2: 100 of 330 MB" }),
        [CANCEL]: { ...IDLE, state: "CANCELLED" },
      });
      renderApp(<ResearchScreen />);
      const bar = await screen.findByRole("progressbar", { name: "Download progress" });
      expect(bar).toHaveAttribute("aria-valuenow", "30");
      expect(screen.getByText("Downloading EmbeddingGemma 2: 100 of 330 MB")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Turn on smarter search/ })).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: "Cancel the download" }));
      await waitFor(() => expect(callsTo("POST", "/api/v2/research/setup/cancel")).toHaveLength(1));
    });

    it("shows the last step while the library is made ready", async () => {
      routeApi({ [STATUS]: status({}, { state: "PREPARING", percent: 100, message: "Getting the research library ready..." }) });
      renderApp(<ResearchScreen />);
      expect(await screen.findByText("Getting the research library ready...")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Cancel the download" })).toBeNull();
    });

    it("explains a failure in plain words and offers to try again", async () => {
      const message = "Could not reach the download site. Check your internet connection and try again.";
      routeApi({
        [STATUS]: status({}, { state: "FAILED", message, error: { code: "NO_INTERNET", message } }),
        [SETUP]: { ...IDLE, state: "DOWNLOADING" },
      });
      renderApp(<ResearchScreen />);
      const alert = await screen.findByRole("alert");
      expect(within(alert).getByText(message)).toBeInTheDocument();
      expect(within(alert).queryByText("NO_INTERNET")).toBeNull();
      fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
      await waitFor(() => expect(callsTo("POST", "/api/v2/research/setup")).toHaveLength(1));
    });

    it("says a cancelled download keeps what it fetched", async () => {
      routeApi({ [STATUS]: status({}, { state: "CANCELLED" }) });
      renderApp(<ResearchScreen />);
      expect(await screen.findByText("Download cancelled")).toBeInTheDocument();
      expect(screen.getByText(/starting again carries on from there/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Start again" })).toBeInTheDocument();
    });

    it("confirms when it is on, and says what that means for privacy", async () => {
      routeApi({
        [STATUS]: status(
          { state: "READY", by_meaning: true, label: "EmbeddingGemma 2 (running on this computer)" },
          { state: "DONE", percent: 100, message: "EmbeddingGemma 2 is ready. Search now matches by meaning." },
        ),
      });
      renderApp(<ResearchScreen />);
      expect(await screen.findByText("Matching by meaning")).toBeInTheDocument();
      expect(screen.getByText(/What you type stays here and the search works without internet/)).toBeInTheDocument();
      expect(screen.getByText("Smarter search is on")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Turn on smarter search/ })).toBeNull();
    });

    it("offers no button when this copy cannot run it, and gives no instructions", async () => {
      routeApi({ [STATUS]: status({ state: "NOT_INSTALLED" }) });
      renderApp(<ResearchScreen />);
      expect(await screen.findByText(/not available in this copy of QuantOS/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Turn on smarter search/ })).toBeNull();
      expect(screen.queryByText(/terminal|command|pip|install/i)).toBeNull();
    });
  });
});
