import { describe, expect, it } from "vitest";
import { ageLabel, DASH, daysSince, inr, inrCompact, inrSigned, int, num, pct, plural, tone } from "./format";

describe("rupee formatting", () => {
  it("groups digits the Indian way", () => {
    expect(inr(1234567.5)).toBe("₹12,34,567.50");
    expect(inr(1000000, 0)).toBe("₹10,00,000");
    expect(inr(-2500.4)).toBe("-₹2,500.40");
  });

  it("shortens large amounts to lakh and crore", () => {
    expect(inrCompact(8450)).toBe("₹8,450");
    expect(inrCompact(100_000)).toBe("₹1.00 L");
    expect(inrCompact(1_234_567)).toBe("₹12.35 L");
    expect(inrCompact(25_000_000)).toBe("₹2.50 Cr");
    expect(inrCompact(-25_000_000)).toBe("−₹2.50 Cr");
  });

  it("signs gains and losses with a real minus", () => {
    expect(inrSigned(1234)).toBe("+₹1,234");
    expect(inrSigned(-560)).toBe("−₹560");
    expect(inrSigned(0)).toBe("₹0");
  });

  it("shows a dash instead of NaN, null or undefined", () => {
    for (const bad of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(inr(bad)).toBe(DASH);
      expect(inrCompact(bad)).toBe(DASH);
      expect(pct(bad)).toBe(DASH);
      expect(num(bad)).toBe(DASH);
      expect(int(bad)).toBe(DASH);
      expect(inrSigned(bad)).toBe(DASH);
    }
  });
});

describe("percentages", () => {
  it("multiplies fractions and signs them", () => {
    expect(pct(0.1234)).toBe("+12.3%");
    expect(pct(-0.0456, 2)).toBe("−4.56%");
    expect(pct(0)).toBe("0.0%");
  });

  it("can omit the plus sign", () => {
    expect(pct(0.5, 0, false)).toBe("50%");
  });
});

describe("tone", () => {
  it("colours by sign and treats zero and missing as flat", () => {
    expect(tone(1)).toBe("up");
    expect(tone(-1)).toBe("down");
    expect(tone(0)).toBe("flat");
    expect(tone(null)).toBe("flat");
  });
});

describe("dates and ages", () => {
  const today = new Date(2026, 8, 30);

  it("counts calendar days", () => {
    expect(daysSince("2026-09-30", today)).toBe(0);
    expect(daysSince("2026-09-23", today)).toBe(7);
    expect(daysSince("nonsense", today)).toBeNull();
    expect(daysSince(null, today)).toBeNull();
  });

  it("describes age in human units", () => {
    expect(ageLabel(1)).toBe("1 day old");
    expect(ageLabel(12)).toBe("12 days old");
    expect(ageLabel(90)).toBe("3 months old");
    expect(ageLabel(2016)).toBe("6 years old");
  });

  it("pluralises", () => {
    expect(plural(1, "test")).toBe("1 test");
    expect(plural(1200, "test")).toBe("1,200 tests");
  });
});
