import { describe, expect, it } from "vitest";
import { basketPickNote, paperBookPickNote } from "./picks";

describe("paperBookPickNote", () => {
  it("says a holding is currently held by the book", () => {
    const note = paperBookPickNote("XS Monthly", "tcs", "holding");
    expect(note).toContain('TCS is currently held by the paper book "XS Monthly"');
  });

  it("says a queued buy is queued to be bought, and a queued sell to be sold", () => {
    expect(paperBookPickNote("Book", "TCS", "queued_buy")).toContain("is queued to be bought by the paper book");
    expect(paperBookPickNote("Book", "TCS", "queued_sell")).toContain("is queued to be sold by the paper book");
  });

  it("always says the pick is not evidence the stock will do well", () => {
    expect(paperBookPickNote("Book", "TCS", "holding")).toContain("not evidence the stock will do well");
  });

  it.each(["recommend", "guarantee", "should buy", "target", "sure"])("never uses the word '%s'", (word) => {
    expect(paperBookPickNote("Book", "INFY", "queued_buy").toLowerCase()).not.toContain(word);
    expect(basketPickNote("Basket", "INFY").toLowerCase().replace("not a recommendation", "")).not.toContain(word);
  });

  it("tidies spaces and falls back when the book has no name", () => {
    expect(paperBookPickNote("  ", "TCS", "holding")).toContain('"this paper book"');
    expect(paperBookPickNote("My\n  book", "TCS", "holding")).toContain('"My book"');
  });

  it("stays within 300 characters", () => {
    const note = paperBookPickNote("x".repeat(900), "TCS", "holding");
    expect(note.length).toBeLessThanOrEqual(300);
    expect(note.endsWith("…")).toBe(true);
  });
});

describe("basketPickNote", () => {
  it("never says the listed stocks passed the screener, because some of them do not", () => {
    const note = basketPickNote("Tech Leaders", "tcs").toLowerCase();
    expect(note).not.toContain("passed");
    expect(note).toContain("not necessarily");
  });

  it("names the basket and says it is not a recommendation", () => {
    const note = basketPickNote("Tech Leaders", "tcs");
    expect(note).toContain('TCS is listed in the "Tech Leaders" basket');
    expect(note).toContain("not a recommendation");
  });

  it("stays within 300 characters", () => {
    expect(basketPickNote("y".repeat(900), "TCS").length).toBeLessThanOrEqual(300);
  });
});
