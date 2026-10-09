import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";
import { callsTo } from "./agents/testHarness";
import {
  AI_STATUS,
  AI_TEST,
  app,
  buttonsIn,
  cardOf,
  job,
  LAUNCH,
  RECHECK,
  shown,
  startsJob,
  STATUS,
  WithCopilotCheck,
} from "./aiapps/appFixtures";

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return { ...original, api: vi.fn() };
});

const click = (element: HTMLElement) => fireEvent.click(element);
const sent = (method: string, path: string) => callsTo(method, path);
const INPUT = "/api/v2/cli/jobs/claude/input";

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

describe("installing", () => {
  const installing = job({ action: "install", message: "Installing Codex...", seconds: 12.4 });

  it("starts a background install and shows what it is doing", async () => {
    await shown([app("codex", "NOT_INSTALLED")], startsJob("codex", installing));
    click(cardOf("Codex").getByRole("button", { name: "Install Codex" }));
    expect(await cardOf("Codex").findByText("Installing Codex...")).toBeInTheDocument();
    expect(cardOf("Codex").getByText("Installing")).toBeInTheDocument();
    expect(cardOf("Codex").getByText("12s")).toBeInTheDocument();
    expect(sent("POST", LAUNCH)).toEqual([{ agent_id: "codex", action: "install" }]);
  });

  it("cannot be pressed again while it runs", async () => {
    await shown([app("codex", "NOT_INSTALLED", { job: installing })]);
    expect(await cardOf("Codex").findByRole("button", { name: "Install Codex" })).toBeDisabled();
  });
});

describe("signing in", () => {
  const withPage = job({ url: "https://example.test/sign-in", accepts_code: true });

  it("starts a background sign-in and offers the sign-in page if the browser did not open", async () => {
    await shown([app("claude", "NEEDS_SIGN_IN")], startsJob("claude", withPage));
    click(cardOf("Claude Code").getByRole("button", { name: "Sign in to Claude Code" }));
    const link = await cardOf("Claude Code").findByRole("link", { name: /Open the sign-in page/ });
    expect(link).toHaveAttribute("href", "https://example.test/sign-in");
    expect(link).toHaveAttribute("target", "_blank");
    expect(cardOf("Claude Code").getByText(withPage.message)).toBeInTheDocument();
    expect(sent("POST", LAUNCH)).toEqual([{ agent_id: "claude", action: "signin" }]);
  });

  it("passes a pasted sign-in code on without its spaces and clears the box", async () => {
    await shown([app("claude", "NEEDS_SIGN_IN", { job: withPage })], () => ({ [`POST ${INPUT}`]: { sent: true } }));
    const box = await screen.findByLabelText("Sign-in code");
    fireEvent.change(box, { target: { value: "  abc-123  " } });
    click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(sent("POST", INPUT)).toEqual([{ text: "abc-123" }]));
    await waitFor(() => expect(box).toHaveValue(""));
  });

  it("offers no code box when this sign-in takes no code", async () => {
    await shown([app("codex", "NEEDS_SIGN_IN", { job: job({ url: "https://example.test/x" }) })]);
    await screen.findByRole("link", { name: /Open the sign-in page/ });
    expect(screen.queryByLabelText("Sign-in code")).toBeNull();
  });

  it("tells a person what to do in the window that opened, and looks again on request", async () => {
    await shown([app("gemini", "UNKNOWN")], () => ({ [`POST ${LAUNCH}`]: { success: true, message: "Opened." } }));
    expect(buttonsIn(cardOf("Gemini"))).toEqual(["Sign in to Gemini", "Check again", "Test this AI"]);
    click(cardOf("Gemini").getByRole("button", { name: "Sign in to Gemini" }));
    expect(await screen.findByText(/A sign-in window opened\. Choose “Login with Google” there/)).toBeInTheDocument();
    click(cardOf("Gemini").getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(sent("GET", RECHECK)).toHaveLength(1));
  });
});

describe("when something goes wrong", () => {
  it("says in plain words that it failed, with the details tucked away", async () => {
    const message = "Sign-in was not completed. You can try again.";
    const failed = job({ state: "FAILED", message, output: ["one", "two"] });
    await shown([app("claude", "NEEDS_SIGN_IN", { job: failed })]);
    const alert = await cardOf("Claude Code").findByRole("alert");
    expect(alert).toHaveTextContent("Sign-in was not completed. You can try again.");
    expect(within(alert).getByText("Show details")).toBeInTheDocument();
    expect(alert.querySelector("pre")).toHaveTextContent("one two");
    expect(cardOf("Claude Code").getByRole("button", { name: "Sign in to Claude Code" })).toBeEnabled();
  });

  it("shows the engine's own words when it refuses to start", async () => {
    const refuse = () => {
      throw new ApiError("CLI_LAUNCH_FAILED", "QuantOS could not start the sign-in.", 400);
    };
    await shown([app("codex", "NEEDS_SIGN_IN")], () => ({ [`POST ${LAUNCH}`]: refuse }));
    click(cardOf("Codex").getByRole("button", { name: "Sign in to Codex" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("QuantOS could not start the sign-in.");
  });
});

const RUNNING = [app("codex", "NEEDS_SIGN_IN", { job: job() })];
const ENDED = job({ state: "DONE", message: "Codex CLI is connected." });
const SIGNED_IN = [app("codex", "CONNECTED", { job: ENDED })];
function copilotChecks(): number {
  return sent("GET", AI_STATUS).length;
}

describe("keeping the AI choice above in step", () => {
  it("makes the Copilot look again at once when a sign-in ends", async () => {
    const { state } = await shown(RUNNING, undefined, <WithCopilotCheck />);
    await waitFor(() => expect(copilotChecks()).toBe(1));
    state.apps = SIGNED_IN;
    click(screen.getByRole("button", { name: "Check status" }));
    expect(await cardOf("Codex").findByText("Signed in")).toBeInTheDocument();
    await waitFor(() => expect(copilotChecks()).toBe(2));
  });

  it("does the same when an install ends", async () => {
    const running = [app("codex", "NOT_INSTALLED", { job: job({ action: "install" }) })];
    const { state } = await shown(running, undefined, <WithCopilotCheck />);
    await waitFor(() => expect(copilotChecks()).toBe(1));
    state.apps = [app("codex", "NEEDS_SIGN_IN", { job: job({ action: "install", state: "DONE" }) })];
    click(screen.getByRole("button", { name: "Check status" }));
    await waitFor(() => expect(copilotChecks()).toBe(2));
  });

  it("also does it for a job that failed", async () => {
    const { state } = await shown(RUNNING, undefined, <WithCopilotCheck />);
    await waitFor(() => expect(copilotChecks()).toBe(1));
    state.apps = [app("codex", "NEEDS_SIGN_IN", { job: job({ state: "FAILED", message: "Not finished." }) })];
    click(screen.getByRole("button", { name: "Check status" }));
    await waitFor(() => expect(copilotChecks()).toBe(2));
  });

  it("does not look again while the job is still running", async () => {
    const { state } = await shown(RUNNING, undefined, <WithCopilotCheck />);
    await waitFor(() => expect(copilotChecks()).toBe(1));
    state.apps = [app("codex", "NEEDS_SIGN_IN", { job: job({ seconds: 9 }) })];
    click(screen.getByRole("button", { name: "Check status" }));
    await screen.findByText("9s");
    expect(copilotChecks()).toBe(1);
  });

  it("does not look again for a job that had already ended when the screen opened", async () => {
    await shown(SIGNED_IN, undefined, <WithCopilotCheck />);
    await waitFor(() => expect(copilotChecks()).toBe(1));
    act(() => click(screen.getByRole("button", { name: "Check status" })));
    await waitFor(() => expect(sent("GET", RECHECK)).toHaveLength(1));
    expect(copilotChecks()).toBe(1);
  });

  it("adds no polling of its own: the apps are asked for once when the card opens", async () => {
    await shown(RUNNING, undefined, <WithCopilotCheck />);
    await waitFor(() => expect(copilotChecks()).toBe(1));
    expect(sent("GET", STATUS)).toHaveLength(1);
  });
});

describe("Test this AI on an app's own card", () => {
  const answers = [
    ["works", { ok: true, who: "Codex", message: "Codex answered, so it is ready to use." }],
    ["does not work", { ok: false, who: "Codex", message: "Codex did not answer. Try signing in again." }],
  ] as const;

  it.each(answers)("asks that one app and shows the answer here when it %s", async (_how, reply) => {
    await shown([app("codex"), app("claude")], () => ({ [`POST ${AI_TEST}`]: reply }));
    click(cardOf("Codex").getByRole("button", { name: "Test this AI" }));
    expect(await cardOf("Codex").findByText(reply.message)).toBeInTheDocument();
    expect(sent("POST", AI_TEST)).toEqual([{ model: "cli:codex" }]);
    expect(cardOf("Claude Code").queryByText(reply.message)).toBeNull();
  });

  it("makes the card look at the apps again, as the AI choice above already does", async () => {
    const reply = { ok: true, who: "Codex", message: "Codex answered, so it is ready to use." };
    await shown([app("codex")], () => ({ [`POST ${AI_TEST}`]: reply }));
    const before = sent("GET", STATUS).length;
    click(cardOf("Codex").getByRole("button", { name: "Test this AI" }));
    await waitFor(() => expect(sent("GET", STATUS).length).toBeGreaterThan(before));
  });
});
