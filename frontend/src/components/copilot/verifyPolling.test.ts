import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/api";
import type { VerifyPoll } from "../../lib/copilot";
import { CHECK_GONE, describeFailure, LOST_CONTACT, MAX_FAILURES, POLL_MS, startPoller } from "./verifyPolling";

const running: VerifyPoll = { status: "running", progress: { done: 1, total: 6 }, result: null, error: null };
const done: VerifyPoll = { status: "done", progress: { done: 6, total: 6 }, result: null, error: null };

function setup(responses: (VerifyPoll | Error)[], hidden = () => false) {
  const queue = [...responses];
  const fetch = vi.fn(async () => {
    const next = queue.shift() ?? running;
    if (next instanceof Error) throw next;
    return next;
  });
  const onPoll = vi.fn();
  const onGiveUp = vi.fn();
  const stop = startPoller({ fetch, onPoll, onGiveUp, isHidden: hidden });
  return { fetch, onPoll, onGiveUp, stop };
}

function tick(ms = POLL_MS) {
  return vi.advanceTimersByTimeAsync(ms);
}

describe("polling a run", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks at once, then every two seconds while the run is going", async () => {
    const { fetch, stop } = setup([running, running, running]);
    await tick(0);
    expect(fetch).toHaveBeenCalledTimes(1);
    await tick(POLL_MS - 1);
    expect(fetch).toHaveBeenCalledTimes(1);
    await tick(1);
    expect(fetch).toHaveBeenCalledTimes(2);
    await tick();
    expect(fetch).toHaveBeenCalledTimes(3);
    stop();
  });

  it("stops when the run is done", async () => {
    const { fetch, onPoll } = setup([running, done]);
    await tick(0);
    await tick();
    expect(onPoll).toHaveBeenLastCalledWith(done);
    await tick(POLL_MS * 5);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("stops when the run has failed", async () => {
    const failed: VerifyPoll = { status: "failed", progress: null, result: null, error: "No model answered." };
    const { fetch } = setup([failed]);
    await tick(0);
    await tick(POLL_MS * 5);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("stops the moment the screen goes away, and drops an answer still on its way", async () => {
    const { fetch, onPoll, stop } = setup([running, running]);
    await tick(0);
    expect(onPoll).toHaveBeenCalledTimes(1);
    stop();
    await tick(POLL_MS * 5);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(onPoll).toHaveBeenCalledTimes(1);

    let release: (poll: VerifyPoll) => void = () => undefined;
    const slow = vi.fn(() => new Promise<VerifyPoll>((resolve) => (release = resolve)));
    const late = vi.fn();
    const stopSlow = startPoller({ fetch: slow, onPoll: late, onGiveUp: vi.fn(), isHidden: () => false });
    await tick(0);
    stopSlow();
    release(running);
    await tick(POLL_MS * 2);
    expect(late).not.toHaveBeenCalled();
    expect(slow).toHaveBeenCalledTimes(1);
  });

  it("puts up with a hiccup and keeps going", async () => {
    const { fetch, onPoll, onGiveUp, stop } = setup([new Error("offline"), new Error("offline"), running]);
    await tick(0);
    await tick();
    await tick();
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(onPoll).toHaveBeenCalledTimes(1);
    expect(onGiveUp).not.toHaveBeenCalled();
    stop();
  });

  it("gives up after several misses in a row, in plain words, and stops", async () => {
    const { fetch, onGiveUp } = setup(Array.from({ length: 10 }, () => new Error("offline")));
    for (let i = 0; i < MAX_FAILURES; i += 1) await tick(i === 0 ? 0 : POLL_MS);
    expect(onGiveUp).toHaveBeenCalledExactlyOnceWith(LOST_CONTACT);
    await tick(POLL_MS * 5);
    expect(fetch).toHaveBeenCalledTimes(MAX_FAILURES);
  });

  it("counts only misses in a row", async () => {
    const miss = new Error("offline");
    const { onGiveUp, stop } = setup([miss, miss, running, miss, miss, running]);
    for (let i = 0; i < 6; i += 1) await tick(i === 0 ? 0 : POLL_MS);
    expect(onGiveUp).not.toHaveBeenCalled();
    stop();
  });

  it("gives up at once when the run no longer exists", async () => {
    const { fetch, onGiveUp } = setup([new ApiError("NOT_FOUND", "x", 404)]);
    await tick(0);
    expect(onGiveUp).toHaveBeenCalledExactlyOnceWith(CHECK_GONE);
    await tick(POLL_MS * 3);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("does not ask while the tab is hidden, and picks up again when it is shown", async () => {
    let hidden = true;
    const { fetch, stop } = setup([running, running, running], () => hidden);
    await tick(POLL_MS * 4);
    expect(fetch).not.toHaveBeenCalled();
    hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    await tick(0);
    expect(fetch).toHaveBeenCalledTimes(1);
    await tick();
    expect(fetch).toHaveBeenCalledTimes(2);
    stop();
  });

  it("pauses when the tab is hidden between two asks", async () => {
    let hidden = false;
    const { fetch, stop } = setup([running, running, running], () => hidden);
    await tick(0);
    expect(fetch).toHaveBeenCalledTimes(1);
    hidden = true;
    await tick(POLL_MS * 3);
    expect(fetch).toHaveBeenCalledTimes(1);
    hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    await tick(0);
    expect(fetch).toHaveBeenCalledTimes(2);
    stop();
  });
});

describe("what a failed ask means", () => {
  it("treats a missing run as final and anything else as a passing hiccup", () => {
    expect(describeFailure(new ApiError("NOT_FOUND", "x", 404))).toEqual({ fatal: true, message: CHECK_GONE });
    expect(describeFailure(new ApiError("ENGINE_OFFLINE", "x", 0))).toEqual({ fatal: false, message: LOST_CONTACT });
    expect(describeFailure(new Error("x"))).toEqual({ fatal: false, message: LOST_CONTACT });
  });
});
