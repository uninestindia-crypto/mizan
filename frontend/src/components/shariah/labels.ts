// The words and colours the Shariah screens use for a result. One place, so the list and the result card agree.

import type { ShariahCompliance } from "../../lib/types";

export type ScreenStatus = ShariahCompliance["compliance_status"];

export const STATUS_TONE: Record<ScreenStatus, "up" | "warn" | "down"> = {
  COMPLIANT: "up",
  QUESTIONABLE: "warn",
  NON_COMPLIANT: "down",
};

export const STATUS_LABEL: Record<ScreenStatus, string> = {
  COMPLIANT: "Compliant",
  QUESTIONABLE: "Questionable",
  NON_COMPLIANT: "Non-Compliant",
};

export const STANDARD_TONE: Record<ScreenStatus, "up" | "warn" | "neutral"> = {
  COMPLIANT: "up",
  QUESTIONABLE: "warn",
  NON_COMPLIANT: "neutral",
};

export const STANDARD_LABEL: Record<ScreenStatus, string> = {
  COMPLIANT: "Passed",
  QUESTIONABLE: "Questionable",
  NON_COMPLIANT: "Failed",
};
