import { describe, expect, it } from "vitest";
import { readSizeWords, releasedWords, thinkingWords, versionNumber } from "./thinking";

describe("thinking levels in plain words", () => {
  it("names every level a person may meet", () => {
    expect(["low", "medium", "high", "xhigh", "max", "ultra"].map(thinkingWords)).toEqual([
      "Low",
      "Medium",
      "High",
      "Extra high",
      "Maximum",
      "Ultra",
    ]);
  });

  it("shows a level it does not know rather than hiding it", () => {
    expect(thinkingWords("deep")).toBe("Deep");
  });
});

describe("how much a model can read", () => {
  it("says words, not tokens, rounded to the nearest thousand", () => {
    expect(readSizeWords(272000)).toBe("Reads about 2,04,000 words at once");
    expect(readSizeWords(1_000_000)).toBe("Reads about 7,50,000 words at once");
  });

  it("says nothing when the size is not known", () => {
    expect(readSizeWords(null)).toBeNull();
    expect(readSizeWords(0)).toBeNull();
    expect(readSizeWords(Number.NaN)).toBeNull();
  });
});

describe("when a model came out", () => {
  it("writes the day out", () => {
    expect(releasedWords("2026-10-09")).toBe("Released 9 Oct 2026");
  });

  it("says nothing for a day it cannot read", () => {
    expect(releasedWords(null)).toBeNull();
    expect(releasedWords("yesterday")).toBeNull();
    expect(releasedWords("2026-13-45")).toBeNull();
  });
});

describe("an app's version", () => {
  it("keeps the number a person recognises", () => {
    expect(versionNumber("codex-cli 0.162.1")).toBe("0.162.1");
    expect(versionNumber("2.1.296 (Claude Code)")).toBe("2.1.296");
    expect(versionNumber("1.3.3")).toBe("1.3.3");
  });

  it("returns nothing when there is no number", () => {
    expect(versionNumber(null)).toBeNull();
    expect(versionNumber("unknown")).toBeNull();
  });
});
