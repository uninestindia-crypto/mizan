import { describe, expect, it } from "vitest";
import { proofOf, rawProof } from "../components/proof/proofFixtures";
import { ApiError } from "./api";
import { parseProof, plainSegments, proofProblem, safeNseUrl } from "./proof";

describe("parseProof", () => {
  it("reads the engine's own output for a compliant stock", () => {
    const proof = proofOf("compliant");
    expect(proof.verdict).toBe("COMPLIANT");
    expect(proof.standards.map((s) => s.standard)).toEqual(["AAOIFI", "TASIS"]);
    expect(proof.standards[0]?.tests).toHaveLength(4);
    expect(proof.filing?.sha256).toHaveLength(64);
  });

  const CASES_1 = [
    ["a verdict it does not know", { verdict: "HALAL" }, "NOT_SCREENED"],
    ["no verdict", {}, "NOT_SCREENED"],
  ] as const;

  it.each(CASES_1)("reads %s as not screened", (_what, raw, verdict) => {
    expect(parseProof(raw).verdict).toBe(verdict);
  });

  it("gives a result and a data status it does not know the safe default", () => {
    const raw = rawProof("compliant");
    const proof = parseProof({ ...raw, data_status: "GOLD" });
    expect(proof.data_status).toBe("NOT_SCREENED");
  });

  it("never fails on a missing list", () => {
    const proof = parseProof({ symbol: "X", verdict: "NOT_SCREENED" });
    expect(proof.standards).toEqual([]);
    expect(proof.not_covered).toEqual([]);
    expect(proof.what_would_change_it).toEqual([]);
    expect(proof.filing).toBeNull();
  });

  it("keeps a sample figure that has no field name and no filing", () => {
    const proof = proofOf("sample");
    const inputs = proof.standards.flatMap((s) => s.tests.flatMap((t) => t.inputs));
    expect(proof.filing).toBeNull();
    expect(inputs.length).toBeGreaterThan(0);
    expect(inputs.every((i) => i.xbrl_tag === null)).toBe(true);
  });

  it("has no figures for a test that could not be worked out", () => {
    const test = proofOf("no_price").standards[0]?.tests[0];
    expect(test?.result).toBe("NOT_COMPUTED");
    expect(test?.low).toBeNull();
    expect(test?.high).toBeNull();
  });
});

describe("the business test", () => {
  const CASES_2 = [
    ["PASS", true],
    ["FAIL", false],
    ["NOT_CONFIRMED", null],
  ] as const;

  it.each(CASES_2)("reads status %s whatever the older yes/no says", (status, compliant) => {
    const proof = parseProof({ verdict: "QUESTIONABLE", sector: { status, compliant: !compliant } });
    expect(proof.sector?.status).toBe(status);
  });

  const CASES_3 = [
    [true, "PASS"],
    [false, "FAIL"],
    [null, "NOT_CONFIRMED"],
  ] as const;

  it.each(CASES_3)("falls back on the older yes/no %s only when there is no status (%s)", (compliant, status) => {
    expect(parseProof({ verdict: "QUESTIONABLE", sector: { compliant } }).sector?.status).toBe(status);
  });

  it("keeps the basis, the industry group and the segments of a real result", () => {
    const sector = proofOf("sector_segment").sector;
    expect(sector?.status).toBe("FAIL");
    expect(sector?.basis).toBe("the filing's segments");
    expect(sector?.matched_keyword).toBe("cigarette");
    expect(sector?.matched_in).toBe("segment");
    expect(sector?.segments).toContain("Cigarettes");
  });

  it("keeps text from outside the app as plain text: no angle brackets, no control characters, bounded", () => {
    const long = "x".repeat(300);
    const odd = ["<img src=x onerror=alert(1)>Cigarettes", "A\u0000B\tC", "Foods", "Foods", 7, long];
    const segments = plainSegments(odd);
    expect(segments[0]).toBe("img src=x onerror=alert(1) Cigarettes");
    expect(segments).toContain("A B C");
    expect(segments.filter((s) => s === "Foods")).toHaveLength(1);
    expect(segments.filter((s) => s.includes("<") || s.includes(">") || s.length > 120)).toEqual([]);
  });

  it("keeps at most 20 segments", () => {
    expect(plainSegments(Array.from({ length: 50 }, (_, i) => `Segment ${i}`))).toHaveLength(20);
  });
});

describe("safeNseUrl", () => {
  const CASES_4 = [
    "https://www.nseindia.com/get-quotes/equity?symbol=TCS",
    "https://nsearchives.nseindia.com/corporate/xbrl/file.xml",
  ] as const;

  it.each(CASES_4)("allows %s", (url) => {
    expect(safeNseUrl(url)).toBe(url);
  });

  const CASES_5 = [
    "http://www.nseindia.com/page",
    "https://www.nseindia.com.evil.example/page",
    "https://evil.example/?u=https://www.nseindia.com/",
    "https://www.nseindia.com@evil.example/page",
    ["https://", "someone", ":", "word", "@www.nseindia.com/page"].join(""),
    "https://www.nseindia.com:8443/page",
    "https://evilnseindia.com/page",
    "https://archives.nseindia.com/page",
    "javascript:alert(1)",
    "data:text/html,hello",
    "//www.nseindia.com/page",
    "not a url",
    "",
  ] as const;

  it.each(CASES_5)("refuses %s", (url) => {
    expect(safeNseUrl(url)).toBeNull();
  });

  it("refuses nothing at all", () => {
    expect(safeNseUrl(null)).toBeNull();
  });
});

describe("proofProblem", () => {
  const CASES_6 = [
    [new ApiError("HTTP_404", "Not Found", 404), "missing"],
    [new ApiError("ENGINE_OFFLINE", "offline", 0), "offline"],
    [new ApiError("HTTP_500", "broken", 500), "other"],
    [new Error("odd"), "other"],
  ] as const;

  it.each(CASES_6)("sorts %s as %s", (error, problem) => {
    expect(proofProblem(error)).toBe(problem);
  });
});
