import { describe, expect, it } from "vitest";
import type { Status, UpdateInfo } from "../../lib/types";
import type { InstallStatus } from "../update/updateInstall";
import { attentionLabels, buildStatusItems, headline, type StatusInputs, type StatusItem } from "./statusItems";

const WED_MORNING = new Date("2026-10-07T05:00:00Z"); // 10:30 in India: inside trading hours
const WED_NIGHT = new Date("2026-10-07T16:30:00Z"); // 22:00 in India: closed

const IDLE_INDEX = { ready: true, latest_session: "2026-10-06", job: { state: "IDLE" } };
const IDLE_DOWNLOAD = { state: "IDLE", done: 0, total: 0 };

function status(over: Partial<Status["index"]> = {}, download: Partial<Status["download"]> = {}): Status {
  const index = { ...IDLE_INDEX, ...over };
  return { index, download: { ...IDLE_DOWNLOAD, ...download } } as unknown as Status;
}

const NEWER: UpdateInfo = {
  current: "2.5.0",
  latest: "2.6.0",
  update_available: true,
  url: "https://example.test/r",
  notes: "",
  published_at: null,
  installer: null,
  checked: true,
};
const SAME: UpdateInfo = { ...NEWER, latest: "2.5.0", update_available: false };
const LIVE = { ready: true, message: null };

const QUIET: StatusInputs = { now: WED_MORNING, status: status(), live: LIVE, update: SAME, install: undefined };

type Items = StatusItem[];

function items(over: Partial<StatusInputs> = {}): Items {
  return buildStatusItems({ ...QUIET, ...over });
}
function ids(list: Items): string[] {
  return list.map((item) => item.id);
}

function labelOf(list: Items, id: string): string | undefined {
  return list.find((item) => item.id === id)?.label;
}

describe("what the top bar has to say", () => {
  it("says the market, the prices and live prices, and nothing about an update when there is none", () => {
    expect(ids(items())).toEqual(["market", "prices", "live"]);
  });

  it("leaves out what it cannot know yet instead of showing an empty chip", () => {
    expect(ids(items({ status: undefined, live: undefined }))).toEqual(["market"]);
  });

  it("adds the update chip, worded with the version, when a newer version is out", () => {
    const list = items({ update: NEWER });
    expect(ids(list)).toEqual(["market", "prices", "live", "update"]);
    expect(labelOf(list, "update")).toBe("Update available: v2.6.0");
  });

  it("shows no update chip when the check could not reach the release page", () => {
    expect(ids(items({ update: { ...SAME, latest: null, checked: false } }))).not.toContain("update");
  });

  it("opens the update window from the update chip rather than going to a screen", () => {
    const chip = items({ update: NEWER }).find((item) => item.id === "update");
    expect([chip?.action, chip?.to]).toEqual(["update", undefined]);
  });
});

describe("the prices chip", () => {
  it("reads as of the newest day when prices are current", () => {
    expect(labelOf(items(), "prices")).toBe("Prices as of 6 Oct");
  });

  it("reads out of date, and asks for attention, when prices are old", () => {
    const list = items({ status: status({ latest_session: "2026-09-29" }) });
    const prices = list.find((item) => item.id === "prices");
    expect([prices?.label, prices?.tone, prices?.attention]).toEqual(["Out of date, 29 Sep", "warn", true]);
  });

  it("says there are no prices yet when none are on the computer", () => {
    expect(labelOf(items({ status: status({ ready: false }) }), "prices")).toBe("No prices yet");
  });

  it("shows the download as it goes", () => {
    const list = items({ status: status({}, { state: "RUNNING", done: 12, total: 400 }) });
    expect(labelOf(list, "prices")).toBe("Getting prices, 12 of 400");
  });

  it("says the prices are being prepared while the index builds", () => {
    expect(labelOf(items({ status: status({ job: { state: "RUNNING" } as Status["index"]["job"] }) }), "prices")).toBe(
      "Preparing prices",
    );
  });

  it("links to Settings, then Market data", () => {
    expect(items().find((item) => item.id === "prices")?.to).toBe("/settings/data");
  });
});

describe("the live prices chip", () => {
  it("says on during market hours", () => {
    expect(labelOf(items(), "live")).toBe("Live prices on");
  });

  it("says last close when the market is shut, because that is the price a person will see", () => {
    expect(labelOf(items({ now: WED_NIGHT }), "live")).toBe("Prices: last close");
  });

  it("says off, with the engine's own sentence, and links to Accounts and keys when no key works", () => {
    const message = "Add your Upstox key in Settings, then Accounts and keys.";
    const chip = items({ live: { ready: false, message } }).find((item) => item.id === "live");
    expect([chip?.label, chip?.detail, chip?.to]).toEqual(["Live prices off", message, "/settings/accounts"]);
  });

  it("gives its own sentence when the engine sent none", () => {
    const chip = items({ live: { ready: false, message: null } }).find((item) => item.id === "live");
    expect(chip?.detail).toMatch(/Accounts and keys/);
  });
});

describe("an update that is under way", () => {
  const working = (state: InstallStatus["state"], percent: number | null = null): InstallStatus => ({
    state,
    percent,
    message: "",
    version: "2.6.0",
  });

  const ROWS_1: [InstallStatus, string][] = [
    [working("downloading", 42), "Updating 42%"],
    [working("downloading"), "Updating"],
    [working("checking"), "Checking the update"],
    [working("installing"), "Installing the update"],
    [working("failed"), "Update stopped"],
  ];

  it.each(ROWS_1)("the chip reads %j as %s", (install, words) => {
    expect(labelOf(items({ update: NEWER, install }), "update")).toBe(words);
  });

  it("keeps the chip while installing even if the release notice no longer says an update is waiting", () => {
    expect(labelOf(items({ update: SAME, install: working("installing") }), "update")).toBe("Installing the update");
  });

  it("marks a stopped update as needing attention in a warning tone", () => {
    const chip = items({ update: NEWER, install: working("failed") }).find((item) => item.id === "update");
    expect([chip?.tone, chip?.attention]).toEqual(["warn", true]);
  });
});

describe("the one item the narrow button speaks for", () => {
  it("is the update when there is one", () => {
    expect(headline(items({ update: NEWER }))?.id).toBe("update");
  });

  it("is out-of-date prices when there is no update", () => {
    expect(headline(items({ status: status({ latest_session: "2026-09-29" }) }))?.id).toBe("prices");
  });

  it("is the market when nothing needs attention", () => {
    expect(headline(items())?.id).toBe("market");
  });

  it("is nothing when there is nothing to say", () => {
    expect(headline([])).toBeUndefined();
  });

  it("lists in words everything that may need doing", () => {
    const list = items({ update: NEWER, status: status({ latest_session: "2026-09-29" }) });
    expect(attentionLabels(list)).toEqual(["Out of date, 29 Sep", "Update available: v2.6.0"]);
  });

  it("lists nothing when nothing needs doing", () => {
    expect(attentionLabels(items())).toEqual([]);
  });
});
