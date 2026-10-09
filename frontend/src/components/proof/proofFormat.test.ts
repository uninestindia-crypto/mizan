import { describe, expect, it } from "vitest";
import { proofOf } from "./proofFixtures";
import {
  croreText,
  limitPercent,
  percent,
  readingsDiffer,
  ruleName,
  rupeeText,
  shortHash,
  sumText,
} from "./proofFormat";

describe("how the proof writes figures", () => {
  const CASES_1 = [
    [0, "0%"],
    [0.05, "0.05%"],
    [4.45, "4.5%"],
    [32.7785, "32.8%"],
    [54, "54.0%"],
    [null, "not available"],
  ] as const;

  it.each(CASES_1)("writes the percentage %s as %s", (value, text) => {
    expect(percent(value)).toBe(text);
  });

  const CASES_2 = [
    [33, "33%"],
    [5, "5%"],
    [4.5, "4.5%"],
    [null, "not available"],
  ] as const;

  it.each(CASES_2)("writes the limit %s as %s", (value, text) => {
    expect(limitPercent(value)).toBe(text);
  });

  const CASES_3 = [
    [8155, "₹8,155 crore"],
    [161124, "₹1,61,124 crore"],
    [0.5, "₹0.50 crore"],
    [null, "not available"],
  ] as const;

  it.each(CASES_3)("writes %s crore as %s", (value, text) => {
    expect(croreText(value)).toBe(text);
  });

  it("writes a filed rupee amount the Indian way, exactly", () => {
    expect(rupeeText("81550000000")).toBe("₹81,55,00,00,000");
    expect(rupeeText(null)).toBe("not available");
  });

  it("shows the first 12 characters of a fingerprint", () => {
    expect(shortHash("fingerprint-of-the-filing")).toBe("fingerprint-");
  });

  it("writes the sum behind a figure so it can be redone", () => {
    const figure = { pct: 10.3852, numerator_cr: 16733, denominator_cr: 161124 };
    expect(sumText(figure)).toBe("₹16,733 crore ÷ ₹1,61,124 crore = 10.4%");
  });
});

describe("rule names", () => {
  const CASES_4 = [
    ["tobacco", "Tobacco"],
    ["interest_based_finance", "Interest-based finance"],
    ["cinema", "Cinemas"],
    ["some_new_rule", "Some new rule"],
  ] as const;

  it.each(CASES_4)("writes %s as %s", (rule, name) => {
    expect(ruleName(rule)).toBe(name);
  });
});

describe("readings", () => {
  it("differ when the filing does not break a figure down, and not when it is exact", () => {
    const tests = proofOf("depends").standards.flatMap((s) => s.tests);
    const cash = tests.find((t) => t.result === "DEPENDS");
    const debt = tests.find((t) => t.key === "debt");
    expect(readingsDiffer(cash!)).toBe(true);
    expect(readingsDiffer(debt!)).toBe(false);
  });
});
