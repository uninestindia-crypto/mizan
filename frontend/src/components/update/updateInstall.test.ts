import { describe, expect, it } from "vitest";
import {
  chipWords,
  IDLE,
  INSTALLING_WORDS,
  type InstallStatus,
  isPolling,
  isWorking,
  NOTES_LIMIT,
  percentOf,
  plainNotes,
  stepWords,
  WINDOWS_NOTE,
} from "./updateInstall";

const at = (state: InstallStatus["state"], over: Partial<InstallStatus> = {}): InstallStatus => ({
  ...IDLE,
  state,
  ...over,
});

describe("which steps are looked at again", () => {
  const ROWS_1 = [
    ["idle", false, false],
    ["downloading", true, true],
    ["checking", true, true],
    ["installing", false, true],
    ["failed", false, false],
  ] as const;

  it.each(ROWS_1)("%s: polling %s, working %s", (state, polling, working) => {
    expect([isPolling(at(state)), isWorking(at(state))]).toEqual([polling, working]);
  });

  it("treats no answer yet as neither", () => {
    expect([isPolling(undefined), isWorking(undefined)]).toEqual([false, false]);
  });
});

describe("the percentage", () => {
  const ROWS_2 = [
    [0, 0],
    [41.6, 42],
    [100, 100],
    [140, 100],
    [-5, 0],
    [null, null],
    [Number.NaN, null],
  ];

  it.each(ROWS_2)("%s reads %s", (percent, shown) => {
    expect(percentOf(at("downloading", { percent }))).toBe(shown);
  });
});

describe("the words for a step", () => {
  it("shows the engine's own sentence as it is", () => {
    expect(stepWords(at("failed", { message: "The update could not be downloaded." }))).toBe(
      "The update could not be downloaded.",
    );
  });

  it("says installing in the words the engine gives, and has the same words ready if it gives none", () => {
    expect([stepWords(at("installing", { message: "Custom words." })), stepWords(at("installing"))]).toEqual([
      "Custom words.",
      INSTALLING_WORDS,
    ]);
  });

  it("names the version while downloading, and leaves the percentage to the bar", () => {
    expect(stepWords(at("downloading", { version: "2.6.0", percent: 42 }))).toBe("Downloading QuantOS 2.6.0.");
  });

  it("says what the checking step does in plain words", () => {
    expect(stepWords(at("checking"))).toBe("Checking that the download is genuine.");
  });

  it("tells a person about the Windows prompt in one plain sentence", () => {
    expect(WINDOWS_NOTE).toBe("Windows may ask you to confirm. That is expected.");
  });
});

describe("the update chip's words", () => {
  const ROWS_3: [InstallStatus | undefined, string | null, string][] = [
    [undefined, "2.6.0", "Update available: v2.6.0"],
    [at("idle"), "2.6.0", "Update available: v2.6.0"],
    [at("idle"), null, "Update available"],
    [at("downloading", { percent: 7 }), "2.6.0", "Updating 7%"],
  ];

  it.each(ROWS_3)("%j with the latest %s reads %s", (install, latest, words) => {
    expect(chipWords(install, latest)).toBe(words);
  });
});

describe("release notes as plain text", () => {
  it("drops the marks of headings, bold and code", () => {
    expect(plainNotes("## Fixes\n\n**Search** now finds `pages`")).toBe("Fixes\n\nSearch now finds pages");
  });

  it("keeps a bullet as a bullet, at any depth", () => {
    expect(plainNotes("- one\n* two\n  - three")).toBe("• one\n• two\n  • three");
  });

  it("keeps the words of a link and drops its address", () => {
    expect(plainNotes("See [the release page](https://example.test/x) now")).toBe("See the release page now");
  });

  it("drops html tags", () => {
    expect(plainNotes("a <b>bold</b> <img src=x> word")).toBe("a bold  word");
  });

  it("shrinks long gaps to one blank line and trims the ends", () => {
    expect(plainNotes("\n\none\n\n\n\n\ntwo\n\n")).toBe("one\n\ntwo");
  });

  it("reads Windows line endings", () => {
    expect(plainNotes("one\r\ntwo\r\n- three")).toBe("one\ntwo\n• three");
  });

  it.each([[null], [undefined], [""]])("gives nothing for %s", (notes) => {
    expect(plainNotes(notes)).toBe("");
  });
});

describe("the notes of a real release", () => {
  const DOWNLOAD = "## Install\n\nDownload `QuantOS_v2.6.0_Setup.exe` and run it.\n\n";
  const FOOTER = `${DOWNLOAD}## Checksums (SHA-256)\n\n\`\`\`\nabc123  Setup.exe\n\`\`\`\n`;
  const REAL = `# QuantOS v2.6.0\n\n## What's new\n- Search finds pages\n\n## Fixes\n- Prices show once\n\n${FOOTER}`;

  it("keeps the changes and group names, and leaves out the title and heading the dialog shows", () => {
    expect(plainNotes(REAL)).toBe("• Search finds pages\n\nFixes\n• Prices show once");
  });

  it("leaves out the install and checksum part that every release ends with", () => {
    expect(plainNotes(REAL)).not.toMatch(/Download|abc123|Checksums|Install/);
  });

  it("drops a What is new heading written with a curly apostrophe or in words", () => {
    expect(plainNotes("## What\u2019s new\n- one\n## What is new\n- two")).toBe("• one\n• two");
  });

  it("drops the half line a cut-off set of notes ends in, and says there is more", () => {
    const cutOff = `- one\n- two\n- ${"x".repeat(NOTES_LIMIT)}`.slice(0, NOTES_LIMIT);
    expect(plainNotes(cutOff)).toBe("• one\n• two\n…");
  });

  it("does not touch notes that fit", () => {
    expect(plainNotes("- one\n- two")).toBe("• one\n• two");
  });
});
