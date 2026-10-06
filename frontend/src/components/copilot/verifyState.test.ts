import { describe, expect, it } from "vitest";
import type { VerifyPoll, VerifyResult } from "../../lib/copilot";
import {
  initialRun,
  jobToCancel,
  progressFraction,
  progressLabel,
  RUN_FAILED,
  type RunAction,
  type RunState,
  runReducer,
  runsReducer,
  shouldPoll,
} from "./verifyState";

const result = { symbol: "TCS", headline: "h", disclosure: "d" } as VerifyResult;
const play = (actions: RunAction[], from: RunState = initialRun) => actions.reduce(runReducer, from);
const underway = () => play([{ type: "starting" }, { type: "started", jobId: "j1" }]);

/** An answer to a progress check; anything not given is empty. */
const polled = (poll: Partial<VerifyPoll>, jobId = "j1"): RunAction => ({
  type: "polled",
  jobId,
  poll: { status: "running", progress: null, result: null, error: null, ...poll },
});
const running = (done: number, total: number) => polled({ progress: { done, total } });
const finished = polled({ status: "done", result });

describe("a second opinion run", () => {
  it("goes from set-up to starting to running", () => {
    expect(play([{ type: "starting" }]).phase).toBe("starting");
    const state = underway();
    expect(state).toMatchObject({ phase: "running", jobId: "j1" });
    expect(shouldPoll(state)).toBe(true);
  });

  it("polls only while it is running", () => {
    expect(shouldPoll(initialRun)).toBe(false);
    expect(shouldPoll(play([{ type: "starting" }]))).toBe(false);
    expect(shouldPoll(runReducer(underway(), finished))).toBe(false);
    expect(shouldPoll(runReducer(underway(), { type: "pollFailed", jobId: "j1", message: "x" }))).toBe(false);
  });

  it("shows progress while answers come in", () => {
    const state = runReducer(underway(), running(3, 6));
    expect(state.phase).toBe("running");
    expect(progressLabel(state.progress)).toBe("3 of 6 answers in");
    expect(progressFraction(state.progress)).toBe(0.5);
  });

  it("keeps the last progress when an answer carries none", () => {
    const withProgress = runReducer(underway(), running(2, 6));
    const quiet = runReducer(withProgress, polled({}));
    expect(quiet.progress).toEqual({ done: 2, total: 6 });
  });

  it("finishes with the result when the engine says done", () => {
    const state = runReducer(underway(), polled({ status: "done", progress: { done: 6, total: 6 }, result }));
    expect(state).toMatchObject({ phase: "done", result, error: null });
  });

  it("does not call a run done when it brought no result", () => {
    const state = runReducer(underway(), polled({ status: "done" }));
    expect(state).toMatchObject({ phase: "failed", error: RUN_FAILED });
  });

  it("fails with the engine's own plain reason, or a plain one of ours", () => {
    const named = runReducer(underway(), polled({ status: "failed", error: "No model answered." }));
    expect(named).toMatchObject({ phase: "failed", error: "No model answered." });
    const unnamed = runReducer(underway(), polled({ status: "failed" }));
    expect(unnamed.error).toBe(RUN_FAILED);
  });

  it("ignores an answer for a run that is no longer the current one", () => {
    const state = underway();
    expect(runReducer(state, polled({ progress: { done: 1, total: 2 } }, "other"))).toBe(state);
    const stopped = runReducer(state, { type: "stopped" });
    expect(runReducer(stopped, running(1, 2))).toBe(stopped);
  });

  it("goes back to set-up when the person cancels, and says so once", () => {
    const state = runReducer(underway(), { type: "stopped" });
    expect(state).toMatchObject({ phase: "setup", jobId: null, stopped: true });
    expect(shouldPoll(state)).toBe(false);
  });

  it("ignores a late start after a cancel", () => {
    const stopped = play([{ type: "starting" }, { type: "stopped" }]);
    expect(runReducer(stopped, { type: "started", jobId: "late" })).toBe(stopped);
  });

  it("returns to set-up with the reason when it cannot start", () => {
    const state = play([{ type: "starting" }, { type: "startFailed", message: "Pick at least one AI model." }]);
    expect(state).toMatchObject({ phase: "setup", error: "Pick at least one AI model." });
  });

  it("stops waiting for answers when polling gives up", () => {
    const state = runReducer(underway(), { type: "pollFailed", jobId: "j1", message: "Lost contact." });
    expect(state).toMatchObject({ phase: "failed", error: "Lost contact." });
  });

  it("starts fresh on Run again", () => {
    const done = runReducer(underway(), finished);
    expect(runReducer(done, { type: "reset" })).toEqual(initialRun);
  });

  it("cannot be started twice at once", () => {
    const state = underway();
    expect(runReducer(state, { type: "starting" })).toBe(state);
  });
});

describe("a run the engine says was stopped", () => {
  it("goes back to set-up and says the check was stopped, like a Cancel from the person", () => {
    const state = runReducer(underway(), polled({ status: "cancelled", error: "You stopped this check." }));
    expect(state).toMatchObject({ phase: "setup", jobId: null, stopped: true, error: null, result: null });
    expect(shouldPoll(state)).toBe(false);
  });

  it("ignores a stopped answer for another run", () => {
    const state = underway();
    expect(runReducer(state, polled({ status: "cancelled" }, "other"))).toBe(state);
  });
});

describe("which job to stop on the engine", () => {
  it("is the running job when the person cancels", () => {
    expect(jobToCancel(underway(), { type: "stopped" })).toBe("j1");
  });

  it("is nothing when there is no job yet, or the run is not going", () => {
    expect(jobToCancel(initialRun, { type: "stopped" })).toBeNull();
    expect(jobToCancel(play([{ type: "starting" }]), { type: "stopped" })).toBeNull();
    expect(jobToCancel(runReducer(underway(), finished), { type: "stopped" })).toBeNull();
  });

  it("is a job that started after the person had already cancelled, so it does not run on unseen", () => {
    const stopped = play([{ type: "starting" }, { type: "stopped" }]);
    expect(jobToCancel(stopped, { type: "started", jobId: "late" })).toBe("late");
    expect(jobToCancel(play([{ type: "starting" }]), { type: "started", jobId: "j1" })).toBeNull();
  });

  it("is nothing for any other action", () => {
    expect(jobToCancel(underway(), running(1, 2))).toBeNull();
    expect(jobToCancel(underway(), { type: "reset" })).toBeNull();
  });
});

describe("progress words", () => {
  it("says the models are starting before any count is known", () => {
    expect(progressLabel(null)).toBe("Starting the models");
    expect(progressLabel({ done: 0, total: 0 })).toBe("Starting the models");
    expect(progressFraction(null)).toBe(0);
  });
});

describe("runs kept per stock", () => {
  it("keeps one stock's result while another is set up", () => {
    let runs = runsReducer({}, { symbol: "TCS", action: { type: "starting" } });
    runs = runsReducer(runs, { symbol: "TCS", action: { type: "started", jobId: "j1" } });
    runs = runsReducer(runs, { symbol: "INFY", action: { type: "starting" } });
    expect(runs["TCS"]?.phase).toBe("running");
    expect(runs["INFY"]?.phase).toBe("starting");
  });

  it("returns the same object when nothing changed", () => {
    const runs = {};
    expect(runsReducer(runs, { symbol: "TCS", action: { type: "stopped" } })).toBe(runs);
  });
});
