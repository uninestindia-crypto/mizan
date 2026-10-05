import { describe, expect, it } from "vitest";
import { overallStatus, toCompliance } from "./shariah";

describe("combining the two Shariah standards", () => {
  it("passes a share only when both standards pass", () => {
    expect(overallStatus("COMPLIANT", "COMPLIANT")).toBe("COMPLIANT");
  });

  it("fails a share that fails either standard, even if the other has doubts", () => {
    expect(overallStatus("COMPLIANT", "NON_COMPLIANT")).toBe("NON_COMPLIANT");
    expect(overallStatus("NON_COMPLIANT", "QUESTIONABLE")).toBe("NON_COMPLIANT");
  });

  it("leaves a share questionable when either standard is in doubt and neither fails", () => {
    expect(overallStatus("QUESTIONABLE", "COMPLIANT")).toBe("QUESTIONABLE");
    expect(overallStatus("COMPLIANT", "QUESTIONABLE")).toBe("QUESTIONABLE");
  });

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
    expect(row.compliance_status).toBe("NON_COMPLIANT");
    expect(row.debt_ratio).toBe(0.2);
    expect(row.purification_ratio).toBe(0.004);
  });
});
