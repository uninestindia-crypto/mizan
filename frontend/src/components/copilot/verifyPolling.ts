// Asking for a run's progress every two seconds, politely: never in a hidden tab, never after it is over, and with a
// little patience for a hiccup before giving up.

import { useEffect } from "react";
import { ApiError } from "../../lib/api";
import { copilotApi, type VerifyPoll } from "../../lib/copilot";
import type { RunAction } from "./verifyState";

export const POLL_MS = 2000;
export const MAX_FAILURES = 3;

export const LOST_CONTACT = "QuantOS lost contact with this check. Start it again to get the answers.";
export const CHECK_GONE = "This check is no longer available. Start it again.";

export interface PollerOptions {
  fetch: () => Promise<VerifyPoll>;
  onPoll: (poll: VerifyPoll) => void;
  /** Called once, when polling gives up. The message is a plain sentence. */
  onGiveUp: (message: string) => void;
  intervalMs?: number;
  isHidden?: () => boolean;
}

/** A missing run will never come back; anything else may be a passing hiccup. */
export function describeFailure(error: unknown): { fatal: boolean; message: string } {
  if (error instanceof ApiError && error.status === 404) return { fatal: true, message: CHECK_GONE };
  return { fatal: false, message: LOST_CONTACT };
}

class Poller {
  private stopped = false;
  private inFlight = false;
  private failures = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private readonly interval: number;
  private readonly hidden: () => boolean;

  constructor(private readonly options: PollerOptions) {
    this.interval = options.intervalMs ?? POLL_MS;
    this.hidden = options.isHidden ?? (() => document.hidden);
  }

  start(): void {
    document.addEventListener("visibilitychange", this.onVisible);
    void this.tick();
  }

  /** Stops for good. An answer still on its way is dropped when it arrives. */
  stop = (): void => {
    this.stopped = true;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    document.removeEventListener("visibilitychange", this.onVisible);
  };

  // A hidden tab pauses the loop; coming back to it picks the loop up again.
  private onVisible = (): void => {
    if (!this.stopped && this.timer === null && !this.hidden()) void this.tick();
  };

  private later(): void {
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.tick();
    }, this.interval);
  }

  private async tick(): Promise<void> {
    if (this.stopped || this.inFlight || this.hidden()) return;
    this.inFlight = true;
    try {
      const poll = await this.options.fetch();
      if (!this.stopped) this.succeeded(poll);
    } catch (error) {
      if (!this.stopped) this.failed(error);
    } finally {
      this.inFlight = false;
    }
  }

  private succeeded(poll: VerifyPoll): void {
    this.failures = 0;
    this.options.onPoll(poll);
    if (poll.status === "running") this.later();
    else this.stop();
  }

  private failed(error: unknown): void {
    this.failures += 1;
    const { fatal, message } = describeFailure(error);
    if (!fatal && this.failures < MAX_FAILURES) {
      this.later();
      return;
    }
    this.stop();
    this.options.onGiveUp(message);
  }
}

/** Starts polling now and returns the function that stops it. */
export function startPoller(options: PollerOptions): () => void {
  const poller = new Poller(options);
  poller.start();
  return poller.stop;
}

function optionsFor(jobId: string, report: (action: RunAction) => void): PollerOptions {
  return {
    fetch: () => copilotApi.pollVerify(jobId),
    onPoll: (poll) => report({ type: "polled", jobId, poll }),
    onGiveUp: (message) => report({ type: "pollFailed", jobId, message }),
  };
}

/** Polls a run while `active`, reporting each answer as a run action. Leaving the screen stops it. */
export function useVerifyPolling(active: boolean, jobId: string | null, report: (action: RunAction) => void): void {
  useEffect(() => {
    if (!active || !jobId) return undefined;
    return startPoller(optionsFor(jobId, report));
  }, [active, jobId, report]);
}
