import { describe, expect, it } from "vitest";
import { overallStatus, toCompliance } from "./shariah";

type Status = "COMPLIANT" | "QUESTIONABLE" | "NON_COMPLIANT";

describe("combining the two Shariah standards", () => {
  it("passes a share only when both standards pass", () => {
    expect(overallStatus("COMPLIANT", "COMPLIANT")).toBe("COMPLIANT");
  });

  it("fails a share only when both standards fail it", () => {
    expect(overallStatus("NON_COMPLIANT", "NON_COMPLIANT")).toBe("NON_COMPLIANT");
  });

  // The engine's proof says Questionable when the two standards disagree, and the badge beside every symbol shows
  // the proof's word. The screener must show the same word for the same stock.
  const SPLITS: [Status, Status][] = [
    ["COMPLIANT", "NON_COMPLIANT"],
    ["NON_COMPLIANT", "COMPLIANT"],
    ["NON_COMPLIANT", "QUESTIONABLE"],
    ["QUESTIONABLE", "NON_COMPLIANT"],
  ];

  it.each(SPLITS)("leaves a share questionable when AAOIFI says %s and TASIS says %s", (aaoifi, tasis) => {
    expect(overallStatus(aaoifi, tasis)).toBe("QUESTIONABLE");
  });

  it("leaves a share questionable when either standard is in doubt and neither fails it", () => {
    expect(overallStatus("QUESTIONABLE", "COMPLIANT")).toBe("QUESTIONABLE");
    expect(overallStatus("COMPLIANT", "QUESTIONABLE")).toBe("QUESTIONABLE");
    expect(overallStatus("QUESTIONABLE", "QUESTIONABLE")).toBe("QUESTIONABLE");
  });

  const ALL: Status[] = ["COMPLIANT", "QUESTIONABLE", "NON_COMPLIANT"];
  const EVERY_PAIR = ALL.flatMap((a) => ALL.map((b): [Status, Status] => [a, b]));

  it.each(EVERY_PAIR)("gives the same answer whichever standard says what: %s and %s", (a, b) => {
    expect(overallStatus(a, b)).toBe(overallStatus(b, a));
  });

  it("keeps a business that fails both standards as not compliant, so a bank with no figures reads as before", () => {
    expect(overallStatus("NON_COMPLIANT", "NON_COMPLIANT", null)).toBe("NON_COMPLIANT");
  });
});

describe("a verdict the engine already worked out for the row", () => {
  it("stands, even where the two statuses alone would say something else", () => {
    // A business the engine could not confirm: both standards pass, yet the engine says questionable.
    expect(overallStatus("COMPLIANT", "COMPLIANT", "QUESTIONABLE")).toBe("QUESTIONABLE");
    // A standard the engine could not work out, so it shows as questionable, beside one that fails.
    expect(overallStatus("QUESTIONABLE", "NON_COMPLIANT", "NON_COMPLIANT")).toBe("NON_COMPLIANT");
    expect(overallStatus("NON_COMPLIANT", "COMPLIANT", "NON_COMPLIANT")).toBe("NON_COMPLIANT");
  });

  it.each([undefined, null, "", "NOT_SCREENED", "compliant", "Fine", "constructor"])(
    "is ignored when it is %j, which this app does not know or the engine did not send",
    (engine) => {
      expect(overallStatus("COMPLIANT", "NON_COMPLIANT", engine)).toBe("QUESTIONABLE");
      expect(overallStatus("COMPLIANT", "COMPLIANT", engine)).toBe("COMPLIANT");
    },
  );
});

describe("the screener's listing rows", () => {
  it("maps a listing row to the screener row without inventing numbers", () => {
    const row = toCompliance({
      ticker: "BHARTIARTL.NS",
      symbol: "BHARTIARTL",
      company_name: "Bharti Airtel Limited",
      aaoifi_status: "COMPLIANT",
      tasis_status: "NON_COMPLIANT",
      aaoifi_debt_ratio: 0.2,
      aaoifi_cash_ratio: 0.1,
      purification_ratio: 0.004,
    });
    expect(row.is_compliant).toBe(false);
    expect(row.aaoifi_compliant).toBe(true);
    expect(row.tasis_compliant).toBe(false);
    expect(row.compliance_status).toBe("QUESTIONABLE");
    expect(row.debt_ratio).toBe(0.2);
    expect(row.purification_ratio).toBe(0.004);
  });

  it("carries the data status of a row through, and leaves it empty when the list does not say", () => {
    const base = {
      ticker: "TCS.NS",
      symbol: "TCS",
      company_name: "Tata Consultancy Services Limited",
      aaoifi_status: "COMPLIANT" as const,
      tasis_status: "COMPLIANT" as const,
      aaoifi_debt_ratio: 0.01,
      aaoifi_cash_ratio: 0.02,
      purification_ratio: 0.005,
    };
    expect(toCompliance({ ...base, data_status: "UNVERIFIED_SAMPLE" }).data_status).toBe("UNVERIFIED_SAMPLE");
    expect(toCompliance(base).data_status).toBeNull();
  });

  describe("the verdict on a listing row", () => {
    const base = {
      ticker: "INFY.NS",
      symbol: "INFY",
      company_name: "Infosys Limited",
      aaoifi_debt_ratio: 0.02,
      aaoifi_cash_ratio: 0.03,
      purification_ratio: 0.003,
    };

    it("is questionable where one standard passes and the other fails, as the badge says", () => {
      const row = toCompliance({ ...base, aaoifi_status: "NON_COMPLIANT", tasis_status: "COMPLIANT" });
      expect(row.compliance_status).toBe("QUESTIONABLE");
      expect(row.is_compliant).toBe(false);
      expect(row.aaoifi_status).toBe("NON_COMPLIANT");
      expect(row.tasis_status).toBe("COMPLIANT");
    });

    it("is the engine's own when the row carries one", () => {
      const row = toCompliance({
        ...base,
        aaoifi_status: "COMPLIANT",
        tasis_status: "COMPLIANT",
        overall_status: "QUESTIONABLE",
      });
      expect(row.compliance_status).toBe("QUESTIONABLE");
      expect(row.is_compliant).toBe(false);
    });

    it("is not compliant when the engine says so, even though one standard shows doubt", () => {
      const row = toCompliance({
        ...base,
        aaoifi_status: "QUESTIONABLE",
        tasis_status: "NON_COMPLIANT",
        overall_status: "NON_COMPLIANT",
      });
      expect(row.compliance_status).toBe("NON_COMPLIANT");
    });

    it("falls back to the two standards when the engine sends something this app does not know", () => {
      const row = toCompliance({
        ...base,
        aaoifi_status: "COMPLIANT",
        tasis_status: "COMPLIANT",
        overall_status: "NOT_SCREENED",
      });
      expect(row.compliance_status).toBe("COMPLIANT");
    });
  });
});
